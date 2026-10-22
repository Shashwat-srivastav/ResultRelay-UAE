"""Orchestration engine.

Responsibilities, in order:
  1. receive a structured event;
  2. append it to the event store (append-only);
  3. hand role-scoped views to the agents that are allowed to see that event;
  4. collect validated structured assessments;
  5. resolve disagreement with a documented rule;
  6. pass the proposal through the deterministic gate;
  7. perform only permitted *simulated* tool actions;
  8. apply state transitions transactionally;
  9. append the audit record;
 10. return the new state plus unresolved questions.

Agents never see future events and never see each other's raw context.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.audit_governance import AuditGovernanceAgent
from app.agents.base import Agent
from app.agents.escalation import EscalationCoordinator
from app.agents.lab_workflow import LabWorkflowAgent
from app.agents.network_delivery import NetworkDeliveryAgent
from app.agents.policy_applicability import PolicyApplicabilityAgent
from app.audit.log import AuditLog
from app.models.schemas import AgentAssessment, GateDecision, RecommendedAction
from app.orchestration.gate import GateConfig, enforce, naive_gate, resolve_proposals
from app.policies.profile import PATIENT_MESSAGE_TEMPLATE, load_profile
from app.state_machine.states import CaseState, STATE_DESCRIPTIONS
from app.state_machine.transitions import (
    Attempt,
    Acknowledgment,
    EventType,
    MachineContext,
    evaluate,
)
from app.transport.simulator import SimulatedNetwork, sim_time

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Configuration (the four benchmarked systems)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuntimeConfig:
    name: str
    label: str
    use_kb: bool
    applicability_filter: bool
    use_invariants: bool
    use_audit_agent: bool
    acknowledgement_scope: str  # revision | any
    transport_semantics: str  # strict | optimistic
    agents: tuple[str, ...]
    description: str


CONFIGS: dict[str, RuntimeConfig] = {
    "resultrelay": RuntimeConfig(
        name="resultrelay",
        label="ResultRelay (policy-governed multi-agent)",
        use_kb=True,
        applicability_filter=True,
        use_invariants=True,
        use_audit_agent=True,
        acknowledgement_scope="revision",
        transport_semantics="strict",
        agents=("lab_workflow", "policy_applicability", "network_delivery", "escalation_coordinator", "audit_governance"),
        description=(
            "Policy retrieval with jurisdiction filtering, revision-bound acknowledgment semantics, "
            "and deterministic invariants that can refuse any proposal."
        ),
    ),
    "policy_blind": RuntimeConfig(
        name="policy_blind",
        label="Policy-blind baseline (no knowledge base)",
        use_kb=False,
        applicability_filter=False,
        use_invariants=False,
        use_audit_agent=False,
        acknowledgement_scope="any",
        transport_semantics="optimistic",
        agents=("lab_workflow", "network_delivery", "escalation_coordinator"),
        description=(
            "Tracks results and sends messages. Treats a provider response as delivery and any "
            "acknowledgment as completion. No policy evidence, no invariant layer."
        ),
    ),
    "retrieval_only": RuntimeConfig(
        name="retrieval_only",
        label="Citation-only RAG baseline",
        use_kb=True,
        applicability_filter=False,
        use_invariants=False,
        use_audit_agent=False,
        acknowledgement_scope="any",
        transport_semantics="optimistic",
        agents=("lab_workflow", "policy_applicability", "network_delivery", "escalation_coordinator"),
        description=(
            "Retrieves policy text and quotes it, but does not filter by jurisdiction or scope and "
            "keeps the naive delivery/acknowledgment conflation."
        ),
    ),
    "static_rules": RuntimeConfig(
        name="static_rules",
        label="Conventional deterministic rules baseline",
        use_kb=False,
        applicability_filter=False,
        use_invariants=True,
        use_audit_agent=False,
        acknowledgement_scope="revision",
        transport_semantics="strict",
        agents=("lab_workflow", "network_delivery", "escalation_coordinator"),
        description=(
            "The same state machine and invariants, with no policy knowledge. Strong on transport "
            "semantics, blind to jurisdiction, scope and evidence provenance."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------

@dataclass
class Runtime:
    run_id: str
    scenario_id: str
    config: RuntimeConfig
    case_id: str
    jurisdiction: str
    facility_type: str
    case_scope: str
    profile: dict[str, Any]
    network: SimulatedNetwork
    state: CaseState = CaseState.RESULT_DRAFT
    revisions: list[dict[str, Any]] = field(default_factory=list)
    current_revision_id: str | None = None
    acknowledgments: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    #: Open questions do not prevent closure; they are recorded for review and for the gap register.
    unresolved: list[str] = field(default_factory=list)
    #: Blocking conditions are workflow defects that must prevent a case being closed (INV-10).
    blocking_conditions: list[str] = field(default_factory=list)
    escalations: list[dict[str, Any]] = field(default_factory=list)
    documentation_recorded: bool = False
    pending_action: GateDecision | None = None
    at_minutes_current: float = 0.0
    #: action -> {by, at}. Only a recorded human approval unlocks an approval-gated transition.
    approvals: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit: AuditLog | None = None
    patient_ref: str = "SYN-PATIENT-001"
    contact_ref: str = "SYN-CONTACT-001"

    def revision_ids(self) -> list[str]:
        return [r["revision_id"] for r in self.revisions]

    def machine_attempts(self) -> list[Attempt]:
        return [
            Attempt(
                attempt_id=a.attempt_id,
                idempotency_key=a.idempotency_key,
                channel=a.channel,
                result_revision_id=a.result_revision_id,
                transport_accepted=a.accepted,
                delivery_receipt=a.delivered,
                last_outcome=a.outcome,
                reconciled=a.reconciled,
                duplicate_suppressed=a.duplicate_suppressed,
            )
            for a in self.network.attempts
        ]

    def machine_acks(self) -> list[Acknowledgment]:
        return [
            Acknowledgment(
                ack_id=a["ack_id"],
                result_revision_id=a["result_revision_id"],
                role=a.get("role", "PATIENT"),
                actor=a.get("actor", "SYN-PATIENT-001"),
                channel=a.get("channel", "SMS-PATIENT"),
                identity_verified=bool(a.get("identity_verified", True)),
            )
            for a in self.acknowledgments
        ]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class Orchestrator:
    def __init__(self, runtime: Runtime):
        self.rt = runtime
        self.agents: dict[str, Agent] = {
            "lab_workflow": LabWorkflowAgent(),
            "policy_applicability": PolicyApplicabilityAgent(),
            "network_delivery": NetworkDeliveryAgent(),
            "escalation_coordinator": EscalationCoordinator(),
            "audit_governance": AuditGovernanceAgent(),
        }
        if runtime.audit is None:
            runtime.audit = AuditLog(runtime.run_id, runtime.case_id)

    # -- context -----------------------------------------------------------
    def snapshot(self, event: dict[str, Any]) -> dict[str, Any]:
        rt = self.rt
        delivered = [a for a in rt.network.attempts if a.delivered and a.delivered_at_minutes is not None]
        elapsed_since_delivery = (
            round(rt.at_minutes_current - max(a.delivered_at_minutes for a in delivered), 1) if delivered else None
        )
        return {
            "case_id": rt.case_id,
            "jurisdiction": rt.jurisdiction,
            "facility_type": rt.facility_type,
            "case_scope": rt.case_scope,
            "current_revision_id": rt.current_revision_id,
            "revisions": rt.revisions,
            "state": rt.state.value,
            "event": event,
            "workflow_stage": _stage_for(event.get("type")),
            "applicability_filter": rt.config.applicability_filter,
            "policy_profile": rt.profile,
            "profile_retry": {
                "retry_enabled": rt.profile.get("retry_enabled"),
                "max_retries": rt.profile.get("max_retries"),
            },
            "profile_timers": {
                "acknowledgment_clock_minutes": rt.profile.get("acknowledgment_clock_minutes"),
                "acknowledgment_clock_basis": rt.profile.get("acknowledgment_clock_basis"),
                "escalation_after_minutes": rt.profile.get("escalation_after_minutes"),
                "escalation_role": rt.profile.get("escalation_role"),
                "elapsed_minutes_current": rt.at_minutes_current,
                "elapsed_minutes_since_delivery": elapsed_since_delivery,
            },
            "attempts": [
                {
                    "attempt_id": a.attempt_id,
                    "channel": a.channel,
                    "result_revision_id": a.result_revision_id,
                    "idempotency_key": a.idempotency_key,
                    "accepted": a.accepted,
                    "delivered": a.delivered,
                    "failed": a.failed,
                    "outcome": a.outcome,
                    "reconciled": a.reconciled,
                    "duplicate_suppressed": a.duplicate_suppressed,
                }
                for a in rt.network.attempts
            ],
            "channels": rt.network.channel_manifest(),
            "acknowledgments": rt.acknowledgments,
            "unresolved_conditions": rt.blocking_conditions,
            "open_questions": rt.unresolved,
            "documentation_recorded": rt.documentation_recorded,
        }

    def machine_context(self, event: dict[str, Any], evidence: dict[str, Any] | None = None,
                        documentation_recorded: bool | None = None) -> MachineContext:
        rt = self.rt
        return MachineContext(
            case_id=rt.case_id,
            state=rt.state,
            current_revision_id=rt.current_revision_id or "",
            revision_ids=rt.revision_ids(),
            attempts=rt.machine_attempts(),
            acknowledgments=rt.machine_acks(),
            event=event,
            profile=rt.profile,
            evidence=evidence or {},
            documentation_recorded=(
                rt.documentation_recorded if documentation_recorded is None else documentation_recorded
            ),
            unresolved_conditions=list(rt.blocking_conditions),
            case_scope=rt.case_scope,
            correction_lineage=any(
                r.get("supersedes_revision_id") for r in rt.revisions
                if r["revision_id"] == rt.current_revision_id
            ),
        )

    # -- agent dispatch ----------------------------------------------------
    def run_agents(self, event: dict[str, Any], visible_to: list[str] | None = None) -> list[AgentAssessment]:
        rt = self.rt
        allowed = [a for a in rt.config.agents if a in self.agents]
        if visible_to:
            allowed = [a for a in allowed if a in visible_to]
        snap = self.snapshot(event)
        results: list[AgentAssessment] = []
        policy_result = None
        for agent_id in allowed:
            agent = self.agents[agent_id]
            if agent_id == "policy_applicability" and not rt.config.use_kb:
                continue
            if agent_id == "audit_governance":
                continue  # runs after the gate
            results.append(agent.assess(snap))
            if agent_id == "policy_applicability":
                policy_result = results[-1]
        # Feed the policy agent's evidence into the network agent's view via the snapshot keys it
        # is allowed to see. (Deliberately not the reverse: policy never sees transport internals.)
        rt._policy_result = policy_result if policy_result else getattr(rt, "_policy_result", None)  # type: ignore[attr-defined]
        return results

    def run_audit(self, event: dict[str, Any], assessments: list[AgentAssessment],
                  gate: GateDecision) -> AgentAssessment | None:
        if not self.rt.config.use_audit_agent:
            return None
        snap = self.snapshot(event)
        snap["assessments"] = assessments
        snap["gate_decision"] = gate.model_dump()
        return self.agents["audit_governance"].assess(snap)

    # -- transitions -------------------------------------------------------
    def apply_event(self, event: dict[str, Any], *, step: int, evidence: dict[str, Any] | None = None,
                    documentation_recorded: bool | None = None) -> dict[str, Any]:
        evt_type = _event_enum(event.get("type"))
        prior = self.rt.state
        if evt_type is None:
            self.rt.transitions.append({
                "step": step, "prior_state": prior.value, "resulting_state": prior.value,
                "trigger_event": str(event.get("type")), "status": "NO_RULE",
                "reason": "unrecognised event type; recorded only", "actor": event.get("actor", "SYSTEM"),
                "at": event.get("at", _now()), "invariant": None, "policy_refs": "",
            })
            return {"status": "NO_RULE", "prior": prior.value, "resulting": prior.value,
                    "reason": "unrecognised event type"}

        ctx = self.machine_context(event, evidence=evidence, documentation_recorded=documentation_recorded)
        result = evaluate(ctx, evt_type)
        if result.applied:
            self.rt.state = result.next_state
        row = {
            "step": step,
            "prior_state": prior.value,
            "resulting_state": self.rt.state.value,
            "trigger_event": evt_type.value,
            "status": result.status,
            "reason": result.reason,
            "actor": event.get("actor", "SYSTEM"),
            "at": event.get("at", _now()),
            "invariant": result.invariant,
            "policy_refs": result.policy_ref or "",
        }
        self.rt.transitions.append(row)
        assert self.rt.audit is not None
        self.rt.audit.append(
            event="state.transition." + result.status.lower(),
            actor=event.get("actor", "SYSTEM"),
            summary=f"{prior.value} -> {self.rt.state.value}: {result.reason[:240]}",
            payload=row,
            at=event.get("at"),
        )
        return {"status": result.status, "prior": prior.value, "resulting": self.rt.state.value,
                "reason": result.reason, "invariant": result.invariant,
                "requires_human": result.requires_human}

    # -- tools -------------------------------------------------------------
    def perform_action(self, action: RecommendedAction, step: int, at_minutes: float,
                       channel: str | None = None, authorised_channel: str | None = None) -> dict[str, Any]:
        """Execute a permitted *simulated* tool action and apply the resulting observations."""
        rt = self.rt
        if action in (RecommendedAction.SEND_PRIMARY, RecommendedAction.RETRY_SAME_CHANNEL):
            # The authorised channel is derived from the action and the case record, never from the
            # caller. A caller asking for a different channel is refused rather than obeyed.
            last = rt.network.attempts[-1] if rt.network.attempts else None
            authorised_channel = authorised_channel or (
                last.channel if (action is RecommendedAction.RETRY_SAME_CHANNEL and last)
                else rt.network.primary_channel()
            )
            if channel and channel != authorised_channel:
                return {
                    "tool": "transport.send",
                    "attempt_id": None,
                    "outcome": "CHANNEL_NOT_AUTHORISED",
                    "transitions": [],
                    "note": (
                        f"requested channel {channel} is not the channel authorised for {action.value} "
                        f"({authorised_channel}); an alternative channel requires verified evidence or an "
                        "approved institutional procedure (INV-9)"
                    ),
                }
            channel = authorised_channel
            applied = []
            # Authorise BEFORE acting. The transition guard is what bounds the retry budget, so it
            # must be evaluated against the attempt count as it stands, not after a new message exists.
            applied.append(self.apply_event(
                {"type": "transmission.requested", "result_revision_id": rt.current_revision_id,
                 "phase": "QUEUE", "actor": "SYSTEM", "at": sim_time(at_minutes)}, step=step))
            # A queued case, or a corrected revision awaiting release, needs a second event to
            # actually reach the transport adapter.
            release_states = {
                CaseState.TRANSMISSION_QUEUED.value,
                CaseState.CORRECTED_RESULT_DELIVERY_PENDING.value,
            }
            if rt.state.value in release_states:
                applied.append(self.apply_event(
                    {"type": "transmission.requested", "result_revision_id": rt.current_revision_id,
                     "phase": "RELEASE", "actor": "SYSTEM", "at": sim_time(at_minutes)}, step=step))
            if rt.state.value not in (CaseState.TRANSMISSION_ATTEMPTED.value,):
                return {"tool": "transport.send", "attempt_id": None,
                        "outcome": "NOT_AUTHORISED", "transitions": applied,
                        "note": "state machine did not authorise a transmission at this point"}

            attempt_index = len(rt.network.attempts)
            key = f"{rt.case_id}:{rt.current_revision_id}:{channel}:{attempt_index}"
            attempt = rt.network.send(
                channel=channel,
                result_revision_id=rt.current_revision_id or "",
                idempotency_key=key,
                at_minutes=at_minutes,
                content_digest=_content_digest(rt.current_revision_id or ""),
            )
            if attempt.accepted:
                applied.append(self.apply_event(
                    {"type": "transport.accepted", "attempt_id": attempt.attempt_id,
                     "actor": "NETWORK", "at": attempt.accepted_at or sim_time(at_minutes)}, step=step))
            if attempt.delivered:
                applied.append(self.apply_event(
                    {"type": "transport.delivery_receipt", "attempt_id": attempt.attempt_id,
                     "result_revision_id": rt.current_revision_id, "actor": "NETWORK",
                     "_establishes_receipt": True,
                     "at": attempt.delivered_at or sim_time(at_minutes)}, step=step))
            elif attempt.outcome == "TIMEOUT":
                applied.append(self.apply_event(
                    {"type": "transport.timeout", "attempt_id": attempt.attempt_id,
                     "result_revision_id": rt.current_revision_id, "actor": "NETWORK",
                     "at": sim_time(at_minutes)}, step=step))
            elif attempt.failed:
                applied.append(self.apply_event(
                    {"type": "transport.delivery_failed", "attempt_id": attempt.attempt_id,
                     "result_revision_id": rt.current_revision_id, "actor": "NETWORK",
                     "at": sim_time(at_minutes)}, step=step))
            if rt.config.transport_semantics == "optimistic" and attempt.accepted and not attempt.delivered:
                if rt.audit:
                    rt.audit.append(
                        event="legacy.conflation",
                        actor="SYSTEM",
                        summary="LEGACY CONFLATION: provider acceptance recorded as delivery in this configuration",
                        payload={"attempt_id": attempt.attempt_id},
                        at=sim_time(at_minutes),
                    )
            return {"tool": "transport.send", "attempt_id": attempt.attempt_id,
                    "outcome": attempt.outcome, "transitions": applied,
                    "duplicate_suppressed": attempt.duplicate_suppressed}

        if action is RecommendedAction.PROPOSE_FALLBACK:
            fallback = rt.profile.get("fallback_channel_id") or next(
                (c["channel_id"] for c in rt.profile.get("channels", []) if not c.get("primary")), None
            )
            if not fallback:
                return {"tool": "transport.send", "attempt_id": None, "outcome": "NO_FALLBACK_CONFIGURED",
                        "transitions": []}
            # The gate has already established that a fallback is authorised; the channel is
            # pinned here so the caller cannot redirect it.
            result = self.perform_action(
                RecommendedAction.RETRY_SAME_CHANNEL, step, at_minutes, fallback, authorised_channel=fallback
            )
            result.update({
                "tool": "transport.send.fallback",
                "fallback_channel": fallback,
                "authorisation": rt.profile.get("fallback_procedure_ref"),
            })
            return result

        if action == RecommendedAction.RECONCILE_ATTEMPT:
            candidates = [a for a in rt.network.attempts if a.outcome in ("TIMEOUT", "UNKNOWN") and not a.reconciled]
            if not candidates:
                return {"tool": "transport.reconcile", "result": "NOTHING_TO_RECONCILE"}
            target = candidates[-1]
            rec = rt.network.reconcile(target.attempt_id, at_minutes)
            applied = self.apply_event(
                {"type": "reconciliation.result", "attempt_id": target.attempt_id,
                 "result": rec["result"], "reconciliation": True,
                 "result_revision_id": rt.current_revision_id, "actor": "NETWORK",
                 "at": sim_time(at_minutes)}, step=step)
            return {"tool": "transport.reconcile", "attempt_id": target.attempt_id,
                    "result": rec["result"], "transitions": [applied]}

        if action == RecommendedAction.ESCALATE_HUMAN:
            esc = {
                "escalation_id": f"ESC-{len(rt.escalations) + 1:03d}",
                "role": rt.profile.get("escalation_role", "SUPERVISOR"),
                "reason": "; ".join(rt.unresolved[:3]) or "deterministic gate requires a human decision",
                "triggered_by": "deterministic_gate",
                "status": "OPEN",
                "at": sim_time(at_minutes),
            }
            rt.escalations.append(esc)
            applied = self.apply_event(
                {"type": "escalation.requested", "actor": "SYSTEM", "at": sim_time(at_minutes)}, step=step)
            return {"tool": "escalation.create", "escalation": esc, "transitions": [applied]}

        if action == RecommendedAction.RECORD_DOCUMENTATION:
            rt.documentation_recorded = True
            applied = self.apply_event(
                {"type": "documentation.recorded", "result_revision_id": rt.current_revision_id,
                 "actor": "SYSTEM", "at": sim_time(at_minutes)},
                step=step, documentation_recorded=True)
            return {"tool": "documentation.record", "transitions": [applied]}

        return {"tool": None, "note": f"action {action.value} has no simulator tool; no action taken"}

    # -- ingestion of externally authored events ----------------------------
    def ingest_external(self, event: dict[str, Any], at_minutes: float) -> dict[str, Any]:
        """Apply the side effects an external event has on the case record.

        These side effects are deliberately explicit: nothing here decides an action, it only
        records what the world reported.
        """
        rt = self.rt
        et = event.get("type")
        notes: dict[str, Any] = {}

        if et == EventType.RESULT_CORRECTED.value:
            rev_id = event.get("result_revision_id")
            prev = event.get("supersedes_revision_id")
            for r in rt.revisions:
                if r["revision_id"] == prev:
                    r["status"] = "SUPERSEDED"
            rt.revisions.append({
                "revision_id": rev_id,
                "version": int(event.get("version", len(rt.revisions) + 1)),
                "status": "CORRECTED",
                "supersedes_revision_id": prev,
                "test_name": event.get("test_name", "Synthetic analyte"),
                "critical_flag_source": event.get("critical_flag_source", "Separate authorised laboratory process"),
                "finalized_at": event.get("at"),
            })
            rt.current_revision_id = rev_id
            notes["revision_created"] = rev_id

        if et == EventType.CLINICAL_ACKNOWLEDGMENT.value:
            ack = {
                "ack_id": f"ACK-{len(rt.acknowledgments) + 1:03d}",
                "result_revision_id": event.get("result_revision_id"),
                "role": event.get("role", "PATIENT"),
                "actor": event.get("actor", rt.patient_ref),
                "channel": event.get("channel", "SMS-PATIENT"),
                "identity_verified": bool(event.get("identity_verified", True)),
                "at": event.get("at"),
            }
            rt.acknowledgments.append(ack)
            notes["acknowledgment"] = ack["ack_id"]

        if et == EventType.TRANSPORT_DELIVERY_RECEIPT.value:
            attempt = next((a for a in rt.network.attempts if a.attempt_id == event.get("attempt_id")), None)
            if attempt is None:
                notes["receipt"] = "unmatched: no attempt with that id"
            else:
                if not attempt.delivered:
                    attempt.delivered = True
                    attempt.accepted = True
                    attempt.outcome = "DELIVERED"
                    attempt.delivered_at = event.get("at")
                    attempt.delivered_at_minutes = at_minutes
                    # This event is the one establishing the receipt, so the duplicate-receipt
                    # guard must not treat it as a repeat.
                    event["_establishes_receipt"] = True
                    rt.network.ledger.append({
                        "at": event.get("at"),
                        "event": "LATE_ENDPOINT_DELIVERY_RECEIPT",
                        "attempt_id": attempt.attempt_id,
                        "channel": attempt.channel,
                        "note": "receipt arrived after the case had already entered an uncertain state",
                    })
                notes["receipt"] = f"matched attempt {attempt.attempt_id}"

        if et == EventType.ESCALATION_RESOLVED.value:
            if rt.escalations:
                rt.escalations[-1]["status"] = "IN_REVIEW"
                rt.escalations[-1]["reviewer"] = event.get("actor", "SYN-SUPERVISOR")
            else:
                # A human decision may arrive without an existing ticket (for example when a
                # withheld action is approved directly). The decision is still recorded.
                rt.escalations.append({
                    "escalation_id": f"ESC-{len(rt.escalations) + 1:03d}",
                    "role": "SUPERVISOR",
                    "reason": "human decision recorded without a prior open ticket",
                    "triggered_by": "human",
                    "status": "IN_REVIEW",
                    "reviewer": event.get("actor", "SYN-SUPERVISOR"),
                    "at": event.get("at"),
                })
            approve = event.get("approve")
            if approve:
                rt.approvals[approve] = {
                    "by": event.get("actor", "SYN-SUPERVISOR"),
                    "at": event.get("at"),
                    "note": event.get("approval_note", ""),
                }
                notes["approval_recorded"] = approve

        return notes

    # -- one step ----------------------------------------------------------
    def step(self, spec: dict[str, Any]) -> dict[str, Any]:
        rt = self.rt
        step_no = int(spec["step"])
        at_minutes = float(spec.get("at_minutes", 0))
        rt.at_minutes_current = at_minutes
        event = {
            "type": spec.get("type"),
            "at": sim_time(at_minutes),
            "actor": spec.get("actor", "SYSTEM"),
            "payload": spec.get("payload", {}),
            **spec.get("payload", {}),
            "seq": len(rt.events) + 1,
        }
        prior_state = rt.state.value
        event_row = {
            "event_id": f"{rt.case_id}-EV{len(rt.events) + 1:03d}",
            "case_id": rt.case_id,
            "run_id": rt.run_id,
            "seq": len(rt.events) + 1,
            "at": event["at"],
            "kind": event["type"],
            "actor": event["actor"],
            "source_layer": _source_layer(event["type"]),
            "summary": spec.get("summary") or _event_summary(event),
            "payload": spec.get("payload", {}),
        }
        rt.events.append(event_row)
        assert rt.audit is not None
        rt.audit.append(
            event="event.received",
            actor=event["actor"],
            summary=event_row["summary"],
            payload={"seq": event_row["seq"], "kind": event["type"], "payload": spec.get("payload", {})},
            at=event["at"],
        )

        result: dict[str, Any] = {
            "step": step_no,
            "event": event_row,
            "at": event["at"],
            "kind": spec.get("kind", "event"),
            "prior_state": prior_state,
            "agents": [],
            "retrieved_evidence": [],
            "proposed_action": None,
            "gate": None,
            "enforced_action": None,
            "resulting_state": prior_state,
            "transitions": [],
            "human_intervention": None,
            "unresolved_questions": [],
            "information_available": {},
            "actions_performed": [],
            "audit_findings": [],
        }

        # Baseline conflation of stale acknowledgments (recorded, not hidden).
        if event["type"] == EventType.CLINICAL_ACKNOWLEDGMENT.value and rt.config.acknowledgement_scope == "any":
            ack_rev = spec.get("payload", {}).get("result_revision_id")
            if ack_rev and rt.current_revision_id and ack_rev != rt.current_revision_id:
                event["result_revision_id"] = rt.current_revision_id
                result["legacy_conflation"] = (
                    f"acknowledgment for {ack_rev} was applied to {rt.current_revision_id} in this configuration"
                )

        # 1. Record what the world reported, then apply it to the state machine.
        #    "action" steps are internal decision points: they carry no external event to apply.
        result["ingest_notes"] = self.ingest_external(event, at_minutes)
        if spec.get("kind") == "action":
            transition = {
                "status": "NO_EVENT",
                "prior": prior_state,
                "resulting": prior_state,
                "reason": "internal decision point; no external event was applied",
            }
        else:
            transition = self.apply_event(event, step=step_no)
            result["transitions"].append(transition)
        result["unresolved_questions"] = list(rt.unresolved)

        # 2. Agents see only what they are allowed to see.
        assessments = self.run_agents(event, visible_to=spec.get("visible_to"))
        result["agents"] = [a.model_dump() for a in assessments]
        result["information_available"] = {
            a.agent_id: {k: snapshot_value(self.snapshot(event).get(k)) for k in a.context_scope}
            for a in assessments
        }
        for a in assessments:
            for chunk_id_src in a.applicable_sources:
                result["retrieved_evidence"].append({
                    "agent_id": a.agent_id,
                    "source_id": chunk_id_src.source_id,
                    "section": chunk_id_src.section,
                    "page": chunk_id_src.page,
                    "claim_type": chunk_id_src.claim_type.value,
                    "quote": chunk_id_src.quote,
                })
        policy = next((a for a in assessments if a.agent_id == "policy_applicability"), None)
        result["policy_retrieval"] = (policy.data if policy else None)

        # 3. Resolve and gate.
        proposal, trace = resolve_proposals(assessments)
        result["proposal_trace"] = trace
        result["proposed_action"] = proposal.value

        evidence = {
            "scope_permitted": (policy.data.get("scope_permitted") if policy else True),
            "fallback_authorised": (policy.data.get("fallback_authorised") if policy else False),
            "fallback_evidence_refs": (policy.data.get("fallback_evidence_refs") if policy else []),
        }
        gate_cfg = GateConfig(
            enforce_invariants=rt.config.use_invariants,
            acknowledgement_scope=rt.config.acknowledgement_scope,
            transport_semantics=rt.config.transport_semantics,
            require_evidence_for_high_risk=rt.config.use_kb,
            block_on_jurisdiction_violation=rt.config.applicability_filter,
        )
        if rt.config.use_invariants:
            gate = enforce(
                proposal=proposal,
                review_revision=rt.current_revision_id or "",
                ctx=self.machine_context(event, evidence=evidence),
                assessments=assessments,
                config=gate_cfg,
                kb_available=rt.config.use_kb,
                documentation_recorded=(rt.documentation_recorded or proposal == RecommendedAction.RECORD_DOCUMENTATION),
                approvals=rt.approvals,
            )
        else:
            gate = naive_gate(proposal, self.machine_context(event, evidence=evidence))
        result["gate"] = gate.model_dump()
        result["enforced_action"] = gate.enforced_action.value

        # 4. Execute, only if permitted.
        if spec.get("kind") == "action" and gate.permitted and gate.enforced_action in (
            RecommendedAction.SEND_PRIMARY, RecommendedAction.RETRY_SAME_CHANNEL,
            RecommendedAction.PROPOSE_FALLBACK, RecommendedAction.RECONCILE_ATTEMPT,
            RecommendedAction.ESCALATE_HUMAN, RecommendedAction.RECORD_DOCUMENTATION,
        ):
            tool_result = self.perform_action(gate.enforced_action, step_no, at_minutes, spec.get("channel"))
            result["actions_performed"].append(tool_result)
            for t in tool_result.get("transitions", []):
                result["transitions"].append(t)
        elif not gate.permitted:
            rt.audit.append(
                event="action.blocked",
                actor="DETERMINISTIC_GATE",
                summary=gate.reason[:300],
                payload={"proposal": proposal.value, "invariant": gate.invariant},
                at=event["at"],
            )

        # 5. Escalation bookkeeping when the gate demands a human.
        if (gate.requires_human and not rt.escalations
                and rt.state != CaseState.ESCALATION_REQUIRED):
            esc = {
                "escalation_id": f"ESC-{len(rt.escalations) + 1:03d}",
                "role": rt.profile.get("escalation_role", "SUPERVISOR"),
                "reason": gate.reason[:300],
                "triggered_by": "gate.requires_human",
                "status": "OPEN",
                "at": event["at"],
            }
            rt.escalations.append(esc)
            result["human_intervention"] = esc

        if rt.escalations and rt.state in (CaseState.ESCALATION_REQUIRED, CaseState.ESCALATION_IN_REVIEW):
            result["human_intervention"] = rt.escalations[-1]

        # 6. Audit agent reviews the whole step.
        audit_assessment = self.run_audit(event, assessments + [gate_to_assessment(gate)], gate)
        if audit_assessment:
            result["agents"].append(audit_assessment.model_dump())
            result["audit_findings"] = audit_assessment.data.get("findings", [])
            if audit_assessment.data.get("findings"):
                rt.unresolved.extend(
                    f for f in audit_assessment.data["findings"] if f not in rt.unresolved
                )

        # 7. Condition classification. Blocking defects are a property of the current step and are
        # recomputed each time (a resolved defect must not keep blocking); open questions accumulate.
        rt.blocking_conditions = []
        for a in assessments:
            blocking = a.data.get("blocking_conditions") if a.data else None
            for cond in (blocking if blocking is not None else []):
                if cond not in rt.blocking_conditions:
                    rt.blocking_conditions.append(cond)
            for cond in a.conditions_unresolved:
                if cond in rt.blocking_conditions:
                    continue
                if cond not in rt.unresolved:
                    rt.unresolved.append(cond)
        # A revision change invalidates any blocking condition that referred to an older revision.
        rt.blocking_conditions = [
            c for c in rt.blocking_conditions
            if not (rt.current_revision_id and "revision" in c and rt.current_revision_id in c and "not the current" in c)
        ]

        rt.audit.append(
            event="step.completed",
            actor="ORCHESTRATOR",
            summary=f"step {step_no} complete in state {rt.state.value}",
            payload={
                "step": step_no,
                "proposal": proposal.value,
                "gate_permitted": gate.permitted,
                "enforced": gate.enforced_action.value,
                "state": rt.state.value,
            },
            at=event["at"],
        )

        result["resulting_state"] = rt.state.value
        result["unresolved_questions"] = list(dict.fromkeys(rt.unresolved))
        result["state_description"] = STATE_DESCRIPTIONS[rt.state]
        rt.pending_action = gate
        rt.steps.append(result)
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def snapshot_value(value: Any) -> Any:
    """Compact projection of a scoped field for display."""
    if isinstance(value, list):
        return f"{len(value)} item(s)"
    if isinstance(value, dict):
        return ", ".join(sorted(value.keys()))[:160]
    return value


def _content_digest(revision_id: str) -> str:
    import hashlib

    return hashlib.sha256(PATIENT_MESSAGE_TEMPLATE.encode() + revision_id.encode()).hexdigest()[:16]


def _stage_for(event_type: str | None) -> str:
    return {
        "result.finalized": "finalize",
        "result.corrected": "correction",
        "result.supersede": "correction",
        "clinical.acknowledgment": "acknowledgment",
        "channel.fallback_proposed": "fallback",
        "documentation.recorded": "acknowledgment",
    }.get(event_type or "", "send")


def _event_enum(name: str | None) -> EventType | None:
    if not name:
        return None
    try:
        return EventType(name)
    except ValueError:
        return None


#: The six layers the case timeline keeps apart. A transport observation may never be filed
#: under the clinical layer, because that is exactly how "accepted" becomes "done".
EVENT_LAYERS: dict[str, str] = {
    "result.finalized": "CLINICAL",
    "result.corrected": "CLINICAL",
    "result.supersede": "CLINICAL",
    "transmission.requested": "WORKFLOW",
    "transport.accepted": "TRANSPORT",
    "transport.timeout": "TRANSPORT",
    "transport.status_unknown": "TRANSPORT",
    "transport.delivery_receipt": "TRANSPORT",
    "transport.delivery_failed": "TRANSPORT",
    "reconciliation.result": "TRANSPORT",
    "clinical.acknowledgment": "HUMAN",
    "patient.callback_no_access": "HUMAN",
    "escalation.requested": "HUMAN",
    "escalation.resolved": "HUMAN",
    "human.approval": "HUMAN",
    "documentation.recorded": "WORKFLOW",
    "channel.fallback_proposed": "POLICY",
    "policy.source_updated": "POLICY",
    "case.opened": "WORKFLOW",
    "audit.check": "AUDIT",
}


def _source_layer(event_type: str | None) -> str:
    et = event_type or ""
    if et in EVENT_LAYERS:
        return EVENT_LAYERS[et]
    if et.startswith("audit."):
        return "AUDIT"
    if et.startswith("policy."):
        return "POLICY"
    if et.startswith("transport.") or et.startswith("transmission.") or et.startswith("reconciliation."):
        return "TRANSPORT"
    if et.startswith("result."):
        return "CLINICAL"
    if et.startswith("clinical.") or et.startswith("patient.") or et.startswith("escalation.") or et.startswith("human."):
        return "HUMAN"
    return "WORKFLOW"


def _event_summary(event: dict[str, Any]) -> str:
    et = event.get("type", "")
    p = event.get("payload", {})
    summaries = {
        "result.finalized": f"Result {p.get('result_revision_id')} finalized by the laboratory",
        "result.corrected": f"Corrected result {p.get('result_revision_id')} issued, supersedes {p.get('supersedes_revision_id')}",
        "clinical.acknowledgment": f"Acknowledgment by {p.get('actor', 'human')} for revision {p.get('result_revision_id')}",
        "transmission.requested": "Transmission released to the transport adapter",
        "transport.accepted": f"Provider accepted message for attempt {p.get('attempt_id')}",
        "transport.timeout": f"Transport timeout on attempt {p.get('attempt_id')}",
        "transport.delivery_receipt": f"Endpoint delivery receipt for attempt {p.get('attempt_id')}",
        "transport.delivery_failed": f"Transport reported definite failure for attempt {p.get('attempt_id')}",
        "reconciliation.result": f"Reconciliation outcome for attempt {p.get('attempt_id')}: {p.get('result')}",
        "patient.callback_no_access": "Patient reports they cannot access the message",
        "channel.fallback_proposed": "An alternative channel was proposed",
        "escalation.requested": "Escalation requested",
        "escalation.resolved": "A reviewer opened the escalation",
        "documentation.recorded": "Communication record recorded",
        "policy.source_updated": "A policy source changed and requires re-evaluation",
    }
    return summaries.get(et, f"{et} ({event.get('actor', 'SYSTEM')})")


def gate_to_assessment(gate: GateDecision) -> AgentAssessment:
    """The gate is not an agent, but its decision is fed to the audit agent as structured input."""
    return AgentAssessment(
        agent_id="deterministic_gate",
        case_id="",
        assessment_status="OK" if gate.permitted else "REQUIRES_HUMAN",
        recommended_action=gate.enforced_action,
        applicable_sources=[],
        conditions_checked=gate.conditions_checked,
        conditions_unresolved=gate.blocked_actions,
        confidence=1.0,
        requires_human_review=gate.requires_human,
        concise_rationale=gate.reason[:400],
        data={"invariant": gate.invariant, "basis": "PRODUCT_DESIGN_CONTROL"},
        context_scope=[],
    )


# ---------------------------------------------------------------------------
# Scenario loading / running
# ---------------------------------------------------------------------------

SCENARIO_DIR = REPO_ROOT / "evaluation" / "scenarios"


def load_scenario(scenario_id: str) -> dict[str, Any]:
    path = SCENARIO_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"scenario {scenario_id} not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_scenarios() -> list[dict[str, Any]]:
    out = []
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out.append({
            "scenario_id": data["scenario_id"],
            "title": data["title"],
            "summary": data.get("summary", ""),
            "case_scope": data.get("case_scope", "WALK_IN"),
            "step_count": len(data.get("steps", [])),
            "variant_of": data.get("variant_of"),
        })
    return out


def build_runtime(
    scenario: dict[str, Any],
    config_name: str,
    run_id: str | None = None,
    case_id: str | None = None,
) -> Runtime:
    config = CONFIGS[config_name]
    scenario_id = scenario["scenario_id"]
    run_id = run_id or f"RUN-{scenario_id}-{config_name}"
    case_id = case_id or scenario.get("case_id") or f"SYN-{scenario_id}"
    network = SimulatedNetwork(
        channels=scenario.get("network", {}).get("channels", {}),
        attempt_plan=scenario.get("network", {}).get("attempts", []),
        reconciliation_plan=scenario.get("network", {}).get("reconciliations", []),
    )
    profile = load_profile(scenario.get("profile_overrides"))
    rt = Runtime(
        run_id=run_id,
        scenario_id=scenario_id,
        config=config,
        case_id=case_id,
        jurisdiction=scenario.get("jurisdiction", "AE-DU"),
        facility_type=scenario.get("facility_type", "DHA-licensed clinical laboratory (simulated)"),
        case_scope=scenario.get("case_scope", "WALK_IN"),
        profile=profile,
        network=network,
        patient_ref=scenario.get("patient_ref", "SYN-PATIENT-001"),
        contact_ref=scenario.get("contact_ref", "SYN-CONTACT-001"),
    )
    rt.audit = AuditLog(run_id, case_id)
    if scenario.get("initial_result"):
        rt.revisions.append(_initial_revision(scenario["initial_result"]))
        rt.current_revision_id = scenario["initial_result"]["revision_id"]
    rt.audit.append(
        event="run.started",
        actor="SYSTEM",
        summary=f"scenario {scenario_id} started in configuration {config_name}",
        payload={"config": config_name, "synthetic": True, "jurisdiction": rt.jurisdiction},
        at=sim_time(0),
    )
    return rt


def _initial_revision(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "revision_id": spec["revision_id"],
        "version": int(spec.get("version", 1)),
        "status": spec.get("status", "DRAFT"),
        "supersedes_revision_id": spec.get("supersedes_revision_id"),
        "test_name": spec.get("test_name", "Synthetic analyte"),
        "critical_flag_source": spec.get("critical_flag_source", "Separate authorised laboratory process"),
        "finalized_at": spec.get("finalized_at"),
    }


def run_scenario(scenario: dict[str, Any], config_name: str, run_id: str | None = None) -> Runtime:
    rt = build_runtime(scenario, config_name, run_id)
    orch = Orchestrator(rt)
    for spec in scenario.get("steps", []):
        orch.step(spec)
    assert rt.audit is not None
    rt.audit.append(
        event="run.completed",
        actor="SYSTEM",
        summary=f"scenario finished in state {rt.state.value}",
        payload={"final_state": rt.state.value, "events": len(rt.events)},
        at=sim_time(float(scenario.get("steps", [{}])[-1].get("at_minutes", 0)) if scenario.get("steps") else 0),
    )
    return rt
