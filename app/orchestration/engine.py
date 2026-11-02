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
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.audit_governance import AuditGovernanceAgent
from app.agents.base import Agent
from app.agents.escalation import EscalationCoordinator
from app.agents.lab_workflow import LabWorkflowAgent
from app.core.config import settings
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

REPO_ROOT = Path(__file__).resolve().parents[2]


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
    #: When False, every agent is handed the whole snapshot and the declared-scope filter is
    #: bypassed. Ablating this is the only way to measure whether declared asymmetry does anything.
    asymmetric_context: bool = True
    #: Set on one-flag ablations: the configuration they differ from by exactly one input. A
    #: benchmark that changes six things at once cannot attribute a difference to any of them
    #: (red-team finding H-4).
    ablation_of: str | None = None
    #: A conventional rules engine would hard-code the genetic-results rule (ST-28 §13.4) rather than
    #: retrieve it. Without it the baseline lost the genetic scenarios by construction (critic RT-08).
    hardcoded_genetic_rule: bool = False


CONFIGS: dict[str, RuntimeConfig] = {
    "resultrelay": RuntimeConfig(
        name="resultrelay",
        label="ResultRelay (policy-gated assessors, deterministic)",
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

    # --- one-flag ablations -------------------------------------------------
    #
    # Each differs from ``resultrelay`` in exactly one input, so the table can attribute a
    # difference to a variable. The compound baselines above are kept because they answer a
    # different question ("what does a system without any of this look like?"), but they are not
    # evidence for any single claim and are labelled as compound.
    "ablate_no_kb": RuntimeConfig(
        name="ablate_no_kb",
        label="Ablation: knowledge base off (one flag)",
        use_kb=False,
        applicability_filter=True,
        use_invariants=True,
        use_audit_agent=True,
        acknowledgement_scope="revision",
        transport_semantics="strict",
        agents=("lab_workflow", "policy_applicability", "network_delivery", "escalation_coordinator", "audit_governance"),
        description="ResultRelay with the gate's evidence requirement removed; retrieval still runs.",
        ablation_of="resultrelay",
    ),
    "ablate_no_applicability_filter": RuntimeConfig(
        name="ablate_no_applicability_filter",
        label="Ablation: jurisdiction filter off (one flag)",
        use_kb=True,
        applicability_filter=False,
        use_invariants=True,
        use_audit_agent=True,
        acknowledgement_scope="revision",
        transport_semantics="strict",
        agents=("lab_workflow", "policy_applicability", "network_delivery", "escalation_coordinator", "audit_governance"),
        description="Retrieves across jurisdictions and presents the highest-scoring clause as governing.",
        ablation_of="resultrelay",
    ),
    "ablate_no_invariants": RuntimeConfig(
        name="ablate_no_invariants",
        label="Ablation: invariant gate off (one flag)",
        use_kb=True,
        applicability_filter=True,
        use_invariants=False,
        use_audit_agent=True,
        acknowledgement_scope="revision",
        transport_semantics="strict",
        agents=("lab_workflow", "policy_applicability", "network_delivery", "escalation_coordinator", "audit_governance"),
        description="Proposals are executed as proposed: the deterministic gate is replaced by a naive one.",
        ablation_of="resultrelay",
    ),
    "ablate_no_audit_agent": RuntimeConfig(
        name="ablate_no_audit_agent",
        label="Ablation: audit assessor off (one flag)",
        use_kb=True,
        applicability_filter=True,
        use_invariants=True,
        use_audit_agent=False,
        acknowledgement_scope="revision",
        transport_semantics="strict",
        agents=("lab_workflow", "policy_applicability", "network_delivery", "escalation_coordinator", "audit_governance"),
        description="The fifth assessor is skipped (the engine already gates it on this flag).",
        ablation_of="resultrelay",
    ),
    "ablate_full_context": RuntimeConfig(
        name="ablate_full_context",
        label="Ablation: full context to every assessor (one flag)",
        use_kb=True,
        applicability_filter=True,
        use_invariants=True,
        use_audit_agent=True,
        acknowledgement_scope="revision",
        transport_semantics="strict",
        agents=("lab_workflow", "policy_applicability", "network_delivery", "escalation_coordinator", "audit_governance"),
        description="Every assessor sees the whole case snapshot, so no assessor has to work from less information than another.",
        ablation_of="resultrelay",
        asymmetric_context=False,
    ),
    "ablate_ack_any": RuntimeConfig(
        name="ablate_ack_any",
        label="Ablation: acknowledgement scope any revision (one flag)",
        use_kb=True,
        applicability_filter=True,
        use_invariants=True,
        use_audit_agent=True,
        acknowledgement_scope="any",
        transport_semantics="strict",
        agents=("lab_workflow", "policy_applicability", "network_delivery", "escalation_coordinator", "audit_governance"),
        description="Any acknowledgment closes the case, including one for a superseded revision.",
        ablation_of="resultrelay",
    ),
    "ablate_optimistic_transport": RuntimeConfig(
        name="ablate_optimistic_transport",
        label="Ablation: optimistic transport semantics (one flag)",
        use_kb=True,
        applicability_filter=True,
        use_invariants=True,
        use_audit_agent=True,
        acknowledgement_scope="revision",
        transport_semantics="optimistic",
        agents=("lab_workflow", "policy_applicability", "network_delivery", "escalation_coordinator", "audit_governance"),
        description="A provider acceptance is treated as delivery; the unknown state is never entered.",
        ablation_of="resultrelay",
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
            "The same state machine and invariants, with no policy knowledge base but the genetic-results "
            "rule hard-coded, as a competent rules engine would have it. Strong on transport semantics; "
            "no clause-level provenance and no jurisdiction filter."
        ),
        hardcoded_genetic_rule=True,
    ),
}

# The full system with the multi-agent council in the loop (recorded answers by default). It differs from
# "resultrelay" in one input, the council, so the pair measures what the agents add (critic finding N-02).
import dataclasses as _dc  # noqa: E402

CONFIGS["resultrelay_council"] = _dc.replace(
    CONFIGS["resultrelay"], name="resultrelay_council",
    label="ResultRelay + agent council (policy analyst, TDRA-lens analyst, adversarial reviewer, deterministic assurance)",
    description=("The full system with the council deliberating at every decision point; a corroborated council "
                 "finding opens an escalation. Model answers are replayed from evaluation/agent_runs/."),
    ablation_of=None)


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
    #: Human sign-offs on completion (the documentation record): not escalations, never left open.
    signoffs: list[dict[str, Any]] = field(default_factory=list)
    documentation_recorded: bool = False
    pending_action: GateDecision | None = None
    at_minutes_current: float = 0.0
    #: action -> {by, at}. Only a recorded human approval unlocks an approval-gated transition.
    approvals: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit: AuditLog | None = None
    patient_ref: str = "SYN-PATIENT-001"
    contact_ref: str = "SYN-CONTACT-001"
    #: Where a physician-addressed message goes. Only used when a retrieved clause declares that
    #: routing; the recipient is never inferred from the case (red-team finding H-4).
    physician_contact_ref: str = "SYN-PHYSICIAN-001"
    #: The recipient the policy evidence selected for this step ("PATIENT" or "PHYSICIAN").
    recipient: str = "PATIENT"
    recipient_basis: dict[str, Any] | None = None

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
                receipt_recorded=a.receipt_recorded,
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


def configure_adviser() -> Any:
    """Return the configured adviser, or None.

    Off unless ``RESULTRELAY_ADVISE_URL`` names an endpoint inside the State. The client applies the
    Article 13 residency check in its constructor, so a misconfigured deployment fails at start-up
    rather than at the first patient.
    """
    if os.environ.get("RESULTRELAY_ADVISE_PROVIDER", "").lower() == "jev":
        from app.advisers.jev import JevAdviser

        return JevAdviser()
    url = os.environ.get("RESULTRELAY_ADVISE_URL")
    if not url:
        return None
    from app.advisers.llm import HttpTransport, OpenAICompatibleAdviser

    return OpenAICompatibleAdviser(
        base_url=url,
        model=os.environ.get("RESULTRELAY_ADVISE_MODEL", "local-model"),
        transport=HttpTransport(),
        resolution_ref=os.environ.get("RESULTRELAY_RESIDENCY_RESOLUTION") or None,
    )


def _scenario_minutes(at: Any, default: float) -> float:
    """Minutes since the simulated clock's start (BASE_TIME) for an ISO timestamp; ``default`` if unparseable."""
    from app.transport.simulator import BASE_TIME

    try:
        when = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        return round((when - BASE_TIME).total_seconds() / 60.0, 1)
    except (TypeError, ValueError):
        return default


def _parse_minutes(at: Any) -> float | None:
    """Parse a simulated timestamp (``HH:MM`` or ISO) back to minutes since day start."""
    if at is None:
        return None
    text = str(at)
    if "T" in text:
        text = text.split("T", 1)[1][:5]
    try:
        hh, mm = text.split(":")[:2]
        return int(hh) * 60 + int(mm)
    except (ValueError, AttributeError):
        return None


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
        # Accepted by the provider, never delivered: the case that looks finished on a dashboard.
        undelivered = [a for a in rt.network.attempts
                       if a.accepted and not a.delivered and not a.failed and a.accepted_at_minutes is not None]
        elapsed_since_acceptance = (
            round(rt.at_minutes_current - min(a.accepted_at_minutes for a in undelivered), 1) if undelivered else None
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
                "elapsed_minutes_since_acceptance_without_delivery": elapsed_since_acceptance,
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
    def _council(self):
        """The multi-agent council, for the full system only (baselines and ablations never call a model)."""
        if not hasattr(self, "_council_obj"):
            self._council_obj = None
            name = self.rt.config.name
            if name == "resultrelay_council":  # never the council-off configurations, so the comparison stays clean
                from app.multiagent.council import configured_council

                self._council_obj = configured_council(default_replay=(name == "resultrelay_council"))
        return self._council_obj

    def run_agents(self, event: dict[str, Any], visible_to: list[str] | None = None) -> list[AgentAssessment]:
        rt = self.rt
        allowed = [a for a in rt.config.agents if a in self.agents]
        if visible_to:
            allowed = [a for a in allowed if a in visible_to]
        snap = self.snapshot(event)
        if not rt.config.asymmetric_context:
            from app.agents.base import UNRESTRICTED

            snap[UNRESTRICTED] = True
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
        if result.applied and evt_type is EventType.TRANSPORT_DELIVERY_RECEIPT:
            attempt = next(
                (a for a in self.rt.network.attempts if a.attempt_id == event.get("attempt_id")), None
            )
            if attempt is not None and not attempt.receipt_recorded:
                attempt.receipt_recorded = True
                attempt.delivered = True
                attempt.accepted = True
                attempt.outcome = "DELIVERED"
                attempt.delivered_at = event.get("at")
                # Minutes since the scenario's clock start - the same clock as at_minutes_current. Parsing the
                # wall-clock time gave minutes since midnight (~540 for 09:00), so "time since delivery" was always
                # negative and the delivered-but-never-acknowledged escalation could never fire (found by S11).
                attempt.delivered_at_minutes = _scenario_minutes(event.get("at"), self.rt.at_minutes_current)
                self.rt.network.ledger.append({
                    "at": event.get("at"),
                    "event": "ENDPOINT_DELIVERY_RECEIPT",
                    "attempt_id": attempt.attempt_id,
                    "channel": attempt.channel,
                    "note": "applied after the transition guard verified the attempt and revision",
                })
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
    def escalate(self, reason: str, triggered_by: str, step: int, at_minutes: float) -> dict[str, Any]:
        """Open a named escalation and move the case to ESCALATION_REQUIRED (if the state allows it)."""
        rt = self.rt
        esc = {
            "escalation_id": f"ESC-{len(rt.escalations) + 1:03d}",
            "role": rt.profile.get("escalation_role", "SUPERVISOR"),
            "reason": reason[:300],
            "triggered_by": triggered_by,
            "status": "OPEN",
            "at": sim_time(at_minutes),
            "at_minutes": at_minutes,
            # The obligation keeps an owner and a deadline: an escalation nobody picks up is itself escalated.
            "due_by_minutes": at_minutes + float(rt.profile.get("escalation_response_minutes", 30)),
            "tier": 1,
        }
        rt.escalations.append(esc)
        applied = self.apply_event(
            {"type": "escalation.requested", "actor": "SYSTEM", "at": sim_time(at_minutes)}, step=step)
        return {"tool": "escalation.create", "escalation": esc, "transitions": [applied]}

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
            recipient = rt.physician_contact_ref if rt.recipient == "PHYSICIAN" else rt.contact_ref
            if rt.recipient == "PHYSICIAN":
                # A physician-addressed message may not travel over a patient-facing channel.
                channel_meta = rt.network.channels.get(authorised_channel, {})
                endpoint_class = str(channel_meta.get("endpoint_class", ""))
                if not endpoint_class.startswith("physician"):
                    return {
                        "tool": "transport.send", "attempt_id": None,
                        "outcome": "NO_PHYSICIAN_CHANNEL", "transitions": [],
                        "note": (
                            f"the evidence routes this result to the referring physician, but the "
                            f"authorised channel {authorised_channel!r} is {endpoint_class or 'unclassified'} "
                            "and cannot carry it; a physician-facing channel is required"
                        ),
                    }
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

            # The key identifies the *message*, not the send. Including an attempt counter made every
            # send unique by construction, so the transport's duplicate suppression could never fire
            # (audit finding H-4). A retry of the same message on the same channel reuses this key,
            # which is what lets a provider suppress a duplicate; the state machine, not the key,
            # decides whether a retry is allowed at all.
            supersedes = any(r.get("supersedes_revision_id") for r in rt.revisions)
            purpose = "CORRECTED_RESULT" if supersedes else "RESULT_NOTIFICATION"
            key = f"{rt.case_id}:{rt.current_revision_id}:{channel}:{purpose}"
            attempt = rt.network.send(
                channel=channel,
                result_revision_id=rt.current_revision_id or "",
                idempotency_key=key,
                at_minutes=at_minutes,
                content_digest=_content_digest(rt.current_revision_id or ""),
                recipient=recipient,
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
                # The baseline this configuration is supposed to represent records acceptance as
                # delivery. Until now the flag only wrote an audit note and changed no state, so the
                # "optimistic" rows of the comparison produced identical behaviour to the strict ones
                # and the ablation proved nothing (audit finding H-4). The conflation is now applied
                # to the ledger and then to the state machine, exactly as a naive adapter would.
                conflated = rt.network.record_acceptance_as_delivery(attempt.attempt_id, at_minutes)
                if conflated.get("conflated"):
                    applied.append(self.apply_event(
                        {"type": "transport.delivery_receipt", "attempt_id": attempt.attempt_id,
                         "result_revision_id": rt.current_revision_id, "actor": "NETWORK",
                         "_establishes_receipt": True,
                         "at": sim_time(at_minutes)}, step=step))
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
            return self.escalate("; ".join(rt.unresolved[:3]) or "deterministic gate requires a human decision",
                                 "deterministic_gate", step, at_minutes)

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
            # Recording "delivered" here would pre-empt the transition guard, which is the only
            # component allowed to decide whether this receipt is news. The side effect is applied
            # in apply_event, after the guard has run against the attempt's stored state.
            attempt = next((a for a in rt.network.attempts if a.attempt_id == event.get("attempt_id")), None)
            notes["receipt"] = (
                "unmatched: no attempt with that id" if attempt is None
                else f"pending guard: attempt {attempt.attempt_id}"
            )

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

        # Escalation follow-through: an open escalation past its deadline goes to the next tier, audited.
        for esc in [e for e in rt.escalations if e.get("status") == "OPEN" and e.get("due_by_minutes") is not None]:
            if at_minutes > esc["due_by_minutes"] and not esc.get("overdue_handled"):
                esc["overdue_handled"] = True
                nxt = {"escalation_id": f"ESC-{len(rt.escalations) + 1:03d}",
                       "role": rt.profile.get("escalation_role_tier2", "CLINICAL_LEAD"),
                       "reason": f"{esc['escalation_id']} unanswered past its deadline ({esc['due_by_minutes']:.0f} min): {esc['reason']}"[:300],
                       "triggered_by": "escalation_overdue", "status": "OPEN", "at": event["at"], "at_minutes": at_minutes,
                       "due_by_minutes": at_minutes + float(rt.profile.get("escalation_response_minutes", 30)),
                       "tier": esc.get("tier", 1) + 1}
                rt.escalations.append(nxt)
                rt.audit.append(event="escalation.overdue", actor="ORCHESTRATOR(deterministic)",
                                summary=f"{esc['escalation_id']} overdue; raised {nxt['escalation_id']} to {nxt['role']}",
                                payload={"overdue": esc["escalation_id"], "raised": nxt}, at=event["at"])

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
        proposal, trace, resolution = resolve_proposals(assessments)
        result["proposal_trace"] = trace
        result["proposal_resolution"] = resolution
        result["proposed_action"] = proposal.value
        if resolution["conflict"]:
            # A contested step is a fact worth keeping: it is the only place where the agents'
            # different information shows up as a disagreement rather than as corroboration.
            rt.audit.append(
                event="proposal.contested",
                actor="ORCHESTRATOR",
                summary=(
                    "assessors proposed different actions; "
                    f"chosen {resolution['chosen']} by safety-first precedence"
                ),
                payload=resolution,
                at=event.get("at"),
            )

        # The recipient is an evidence output, not a property of the case: the delivery code reads it
        # from here rather than deciding for itself who is allowed to receive the result.
        rt.recipient = (policy.data.get("recipient") if policy else "PATIENT") or "PATIENT"
        rt.recipient_basis = (policy.data.get("recipient_basis") if policy else None)
        hard_genetic = policy is None and rt.config.hardcoded_genetic_rule and rt.case_scope == "GENETIC"
        if hard_genetic:
            rt.recipient, rt.recipient_basis = "PHYSICIAN", "hard-coded rule (no clause retrieved)"
        evidence = {
            "scope_permitted": (policy.data.get("scope_permitted") if policy else (not hard_genetic)),
            "recipient": rt.recipient,
            "fallback_authorised": (policy.data.get("fallback_authorised") if policy else False),
            "fallback_evidence_refs": (policy.data.get("fallback_evidence_refs") if policy else []),
            "fallback_authorisation_basis": (policy.data.get("fallback_authorisation_basis") if policy else None),
        }
        gate_cfg = GateConfig(
            enforce_invariants=rt.config.use_invariants,
            acknowledgement_scope=rt.config.acknowledgement_scope,
            transport_semantics=rt.config.transport_semantics,
            require_evidence_for_high_risk=rt.config.use_kb,
            block_on_jurisdiction_violation=rt.config.applicability_filter,
        )
        # 3b. Multi-agent deliberation (Policy Evidence Analyst, conditional TDRA-lens analyst, adversarial
        #     reviewer, deterministic assurance and orchestrator), when configured. It runs before the gate and
        #     is logged into the hash chain; the gate never reads it. Its only possible effect on the case is a
        #     named escalation to a person.
        council = self._council()
        if council is not None and _council_enabled_for(spec):
            delib = council.deliberate(rt, event, proposal.value, _case_view(rt, event))
            result["agent_deliberation"] = delib
            for role, msg in delib["messages"].items():
                rt.audit.append(event="agent.message", actor=f"AGENT:{role}",
                                summary=f"{role} {msg.get('status')}: " + json.dumps(msg.get("answers", {}), default=str)[:240],
                                payload={"role": role, **msg}, at=event.get("at"))
            for call in delib["tool_calls"]:
                rt.audit.append(event="agent.tool_call", actor=f"AGENT:{call['agent']}",
                                summary=f"{call['agent']} used read-only tool {call['tool']}", payload=call, at=event.get("at"))
            for role, rv in delib["reviews"].items():
                rt.audit.append(event="assurance.review", actor="ASSURANCE(code)+AGENT:reviewer",
                                summary=(f"{role}: {rv.get('outcome')}; checks {rv.get('checks') or 'clean'}"
                                         + (f"; reviewer issue {rv.get('reviewer_issue')} (p supported {rv.get('reviewer_supported')})"
                                            if role != "reviewer" else ""))[:300],
                                payload={"role": role, **rv}, at=event.get("at"))
            rt.audit.append(event="orchestrator.decision", actor="ORCHESTRATOR(deterministic)",
                            summary=f"{delib['decision']}; conflicts {delib['conflicts'] or 'none'}"[:300],
                            payload={"decision": delib["decision"], "reason": delib["escalation"],
                                     "conflicts": delib["conflicts"], "provider": delib["provider"]}, at=event.get("at"))
            down = [r for r, m in delib["messages"].items() if m.get("status") in ("UNAVAILABLE", "REFUSED_RESIDENCY")]
            if down:
                note = f"agent council unavailable at step {step_no} ({', '.join(down)}): the step was decided by rules alone"
                if note not in rt.unresolved:
                    rt.unresolved.append(note)
            gaps = {m.get("answers", {}).get("gap", {}).get("choice") for m in delib["messages"].values()} - {None, "NONE"}
            for g in sorted(gaps):
                note = f"policy gap surfaced at step {step_no}: {g}"
                if note not in rt.unresolved:
                    rt.unresolved.append(note)
            if delib["decision"] == "ESCALATE" and rt.state.value not in COUNCIL_NO_ESCALATE_STATES:
                reason = f"council at step {step_no}: {delib['escalation']}"
                if reason not in rt.unresolved:
                    rt.unresolved.insert(0, reason[:300])
                rt.audit.append(event="council.escalation", actor="ORCHESTRATOR(deterministic)", summary=reason[:300],
                                payload={"step": step_no, "replaces_proposal": proposal.value}, at=event.get("at"))
                if spec.get("kind") == "action":
                    proposal = RecommendedAction.ESCALATE_HUMAN
                    result["proposed_action"] = proposal.value
                    result["proposal_overridden_by_council"] = True
                else:
                    esc = self.escalate(reason, "council", step_no, at_minutes)
                    result["actions_performed"].append(esc)
                    result["transitions"].extend(esc.get("transitions", []))
                    result["human_intervention"] = esc["escalation"]

        advisory = None
        if settings.enable_llm:
            from app.advisers import advise

            adviser = configure_adviser()
            advisory = advise(
                jurisdiction=rt.jurisdiction,
                situation=json.dumps({
                    "action_under_review": proposal.value,
                    "case_scope": rt.case_scope,
                    "current_state": rt.state.value,
                    "this_step_event": _event_summary(event) if event else None,
                    "current_result_revision": rt.current_revision_id,
                    "attempts": [{"channel": a.channel, "revision": a.result_revision_id,
                                  "transport_accepted": a.transport_accepted, "delivery_receipt": a.delivery_receipt}
                                 for a in rt.machine_attempts()][-4:],
                    "acknowledgments_for_current_revision": sum(
                        1 for k in rt.acknowledgments if k.get("revision_id") == rt.current_revision_id),
                    "approvals_on_record": sorted(rt.approvals),
                    "escalations_open": len(rt.escalations),
                }, default=str),
                evidence=_adviser_evidence(rt, event, assessments),
                adviser=adviser,
                endpoint=getattr(adviser, "endpoint", None) or os.environ.get("RESULTRELAY_ADVISE_URL"),
                resolution_ref=os.environ.get("RESULTRELAY_RESIDENCY_RESOLUTION") or None,
                enabled=settings.enable_llm,
                data_class=("SYNTHETIC" if all(str(v).startswith("SYN-")
                                               for v in (rt.case_id, rt.patient_ref, rt.contact_ref)) else "HEALTH"),
            )
            result["advisory"] = advisory.as_dict()
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
                advisory=advisory,
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
            outcome = tool_result.get("outcome")
            failed = outcome in FAILED_TOOL_OUTCOMES
            # What happened, not only what the gate allowed: every executed action is in the chain.
            rt.audit.append(
                event="action.failed" if failed else "action.performed", actor="SYSTEM",
                summary=(f"{gate.enforced_action.value} -> {outcome or tool_result.get('tool')}"
                         + (f": {tool_result.get('note', '')}" if failed else ""))[:300],
                payload={"action": gate.enforced_action.value, "outcome": outcome, "tool": tool_result.get("tool"),
                         "attempt_id": tool_result.get("attempt_id"), "note": tool_result.get("note")},
                at=event["at"],
            )
            if failed:
                # A permitted send that could not be carried out must not end silently: a critical result
                # that reaches nobody is the failure this system exists to prevent (critic finding N-01).
                reason = f"permitted {gate.enforced_action.value} could not be carried out ({outcome}): {tool_result.get('note', '')}"
                if reason not in rt.unresolved:
                    rt.unresolved.append(reason[:300])
                esc = self.escalate(reason, f"action_failed:{outcome}", step_no, at_minutes)
                result["actions_performed"].append(esc)
                result["transitions"].extend(esc.get("transitions", []))
                result["human_intervention"] = esc["escalation"]
        elif not gate.permitted:
            rt.audit.append(
                event="action.blocked",
                actor="DETERMINISTIC_GATE",
                summary=gate.reason[:300],
                payload={"proposal": proposal.value, "invariant": gate.invariant},
                at=event["at"],
            )

        # 5. Human involvement the gate requires. Writing the communication record is a sign-off by the named
        #    role, not an escalation: booking it as one left an OPEN escalation on every completed case.
        if gate.requires_human and gate.enforced_action == RecommendedAction.RECORD_DOCUMENTATION:
            signoff = {"signoff_id": f"SIGN-{len(rt.signoffs) + 1:03d}",
                       "role": rt.profile.get("escalation_role", "SUPERVISOR"),
                       "reason": gate.reason[:300], "status": "RECORDED", "at": event["at"]}
            rt.signoffs.append(signoff)
            result["human_signoff"] = signoff
        elif (gate.requires_human and not rt.escalations
                and rt.state != CaseState.ESCALATION_REQUIRED):
            esc = {
                "escalation_id": f"ESC-{len(rt.escalations) + 1:03d}",
                "role": rt.profile.get("escalation_role", "SUPERVISOR"),
                "reason": gate.reason[:300],
                "triggered_by": "gate.requires_human",
                "status": "OPEN",
                "at": event["at"],
                "at_minutes": at_minutes,
                "due_by_minutes": at_minutes + float(rt.profile.get("escalation_response_minutes", 30)),
                "tier": 1,
            }
            rt.escalations.append(esc)
            result["human_intervention"] = esc
        # A case that reaches completion closes whatever escalations it still carries.
        if rt.state in (CaseState.COMMUNICATION_DOCUMENTED, CaseState.CORRECTED_RESULT_ACKNOWLEDGED):
            for e in rt.escalations:
                if e.get("status") in ("OPEN", "IN_REVIEW"):
                    e["status"] = "CLOSED_ON_COMPLETION"
                    e["closed_at"] = event["at"]

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


def _adviser_evidence(rt: "Runtime", event: dict[str, Any] | None, assessments: list) -> list[dict[str, Any]]:
    """The bounded evidence an adviser is *shown*: chunks the assessors relied on, else a jurisdiction-
    filtered retrieval for this step. The guard rejects any citation outside this list."""
    shown = [c.model_dump() for a in assessments for c in a.applicable_sources if getattr(c, "chunk_id", None)]
    if shown:
        return shown
    from app.kb import retriever

    query = " ".join([_event_summary(event) if event else "", rt.state.value, rt.case_scope,
                      "critical result communication patient delivery acknowledgment record"])
    return [c.model_dump() for c in retriever.search(query, jurisdiction=rt.jurisdiction, scope="applicable", top_k=6).chunks]


#: Tool outcomes meaning "the permitted action was not carried out". Each one is audited and escalated.
#: The council does not escalate a case that is already with a person or already documented.
COUNCIL_NO_ESCALATE_STATES = {"ESCALATION_REQUIRED", "ESCALATION_IN_REVIEW", "COMMUNICATION_DOCUMENTED"}

FAILED_TOOL_OUTCOMES = {"NO_PHYSICIAN_CHANNEL", "CHANNEL_NOT_AUTHORISED", "NOT_AUTHORISED", "NO_FALLBACK_CONFIGURED"}


def _council_enabled_for(spec: dict[str, Any]) -> bool:
    from app.multiagent.council import enabled_for

    return enabled_for(spec)


def _case_view(rt: "Runtime", event: dict[str, Any] | None) -> dict[str, Any]:
    """Facts the agents may see: the case, never the gate's conclusion for this step."""
    current = rt.current_revision_id
    return {
        "case_scope": rt.case_scope,
        "jurisdiction": rt.jurisdiction,
        "state_before_this_step": rt.state.value,
        "this_step_event": _event_summary(event) if event else None,
        "current_result_revision": current,
        "recipient_route": rt.recipient,
        "attempts": [{"channel": a.channel, "revision": a.result_revision_id, "provider_accepted": a.accepted,
                      "delivery_receipt": bool(a.receipt_recorded), "outcome": a.outcome, "failed": a.failed,
                      "reconciled": a.reconciled}
                     for a in rt.network.attempts][-4:],
        # What people actually reported, in their words: the part of the record rules cannot read.
        "recent_events": [{"kind": e["kind"], "actor": e["actor"], "summary": e["summary"]}
                          for e in rt.events[-4:] if e["kind"] != "system.action"],
        "acknowledgments": [{"revision": k.get("result_revision_id"), "role": k.get("role"),
                             "identity_verified": k.get("identity_verified")} for k in rt.acknowledgments][-4:],
        "minutes_elapsed": rt.at_minutes_current,
        "configured_ack_window_minutes": rt.profile.get("acknowledgment_clock_minutes"),
        # Approved, not merely configured: the default profile always names a fallback channel (critic re-check).
        "approved_fallback_procedure": bool(rt.profile.get("fallback_channel_approved")),
    }


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

SCENARIO_DIR = REPO_ROOT / "scenarios"


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
        physician_contact_ref=scenario.get("physician_contact_ref", "SYN-PHYSICIAN-001"),
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
