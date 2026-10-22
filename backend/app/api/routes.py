"""HTTP API.

The event store is the source of truth: dashboard counters are SQL aggregates over persisted
case rows, never counters held in the frontend.
"""

from __future__ import annotations

import csv
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api import runs as run_registry
from app.audit.log import verify_entries
from app.core.config import describe, settings
from app.evaluation.metrics import compute
from app.kb import retriever
from app.models.db import (
    AcknowledgmentRow,
    AssessmentRow,
    AttemptRow,
    AuditRow,
    CaseRow,
    CitationRow,
    EscalationRow,
    EventRow,
    ReceiptRow,
    RevisionRow,
    TransitionRow,
    get_case,
    list_cases,
    session,
)
from app.orchestration.engine import CONFIGS, Orchestrator, build_runtime, list_scenarios, load_scenario
from app.policies.profile import DEFAULT_PROFILE
from app.state_machine.states import STATE_DESCRIPTIONS, CaseState
from app.state_machine.transitions import transition_table_as_dicts
from app.transport.simulator import REAL_NETWORK_ACCESS

router = APIRouter(prefix="/api")
REPO_ROOT = Path(__file__).resolve().parents[3]
KB_DIR = REPO_ROOT / "knowledge_base"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def serialise_step(step: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(step, default=str))


def serialise_runtime(rt, include_steps: bool = True) -> dict[str, Any]:
    return {
        "run_id": rt.run_id,
        "scenario_id": rt.scenario_id,
        "configuration": rt.config.name,
        "configuration_label": rt.config.label,
        "configuration_description": rt.config.description,
        "case_id": rt.case_id,
        "jurisdiction": rt.jurisdiction,
        "facility_type": rt.facility_type,
        "case_scope": rt.case_scope,
        "state": rt.state.value,
        "state_description": STATE_DESCRIPTIONS[rt.state],
        "current_revision_id": rt.current_revision_id,
        "revisions": rt.revisions,
        "acknowledgments": rt.acknowledgments,
        "escalations": rt.escalations,
        "blocking_conditions": rt.blocking_conditions,
        "open_questions": rt.unresolved,
        "documentation_recorded": rt.documentation_recorded,
        "approvals": rt.approvals,
        "channels": rt.network.channel_manifest(),
        "attempts": [asdict(a) for a in rt.network.attempts],
        "transport_ledger": rt.network.ledger,
        "events": rt.events,
        "transitions": rt.transitions,
        "steps": [serialise_step(s) for s in rt.steps] if include_steps else [],
        "audit": rt.audit.as_list() if rt.audit else [],
        "audit_chain_valid": rt.audit.verify_chain()[0] if rt.audit else False,
        "synthetic": True,
    }


def _persist(rt) -> None:
    """Write the current runtime to SQLite. Called after every step."""
    s = session()
    try:
        case = s.get(CaseRow, rt.case_id)
        payload = {"open_questions": rt.unresolved, "blocking_conditions": rt.blocking_conditions}
        if case is None:
            case = CaseRow(
                case_id=rt.case_id,
                run_id=rt.run_id,
                scenario_id=rt.scenario_id,
                configuration=rt.config.name,
                title=rt.scenario_id,
                jurisdiction=rt.jurisdiction,
                facility_type=rt.facility_type,
                case_scope=rt.case_scope,
                current_state=rt.state.value,
                current_revision_id=rt.current_revision_id,
                patient_ref=rt.patient_ref,
                contact_ref=rt.contact_ref,
                synthetic=True,
                payload=json.dumps(payload),
            )
            s.add(case)
        else:
            case.current_state = rt.state.value
            case.current_revision_id = rt.current_revision_id
            case.run_id = rt.run_id
            case.configuration = rt.config.name
            case.updated_at = datetime.now(timezone.utc).isoformat()
            case.payload = json.dumps(payload)

        for rev in rt.revisions:
            if s.get(RevisionRow, rev["revision_id"]) is None:
                s.add(RevisionRow(
                    revision_id=rev["revision_id"], case_id=rt.case_id, version=rev["version"],
                    status=rev["status"], supersedes_revision_id=rev.get("supersedes_revision_id"),
                    test_name=rev["test_name"], critical_flag_source=rev["critical_flag_source"],
                    finalized_at=rev.get("finalized_at"), payload=json.dumps(rev),
                ))
            else:
                row = s.get(RevisionRow, rev["revision_id"])
                assert row is not None
                row.status = rev["status"]

        existing_events = {r.event_id for r in s.scalars(select(EventRow).where(EventRow.case_id == rt.case_id))}
        for ev in rt.events:
            if ev["event_id"] not in existing_events:
                s.add(EventRow(**{k: ev[k] for k in ("event_id", "case_id", "run_id", "seq", "at", "kind", "actor", "source_layer", "summary")},
                                payload=json.dumps(ev.get("payload", {}), default=str)))

        for tr in rt.transitions:
            key = (rt.case_id, tr.get("step"), tr.get("trigger_event"), tr.get("resulting_state"))
            exists = s.scalar(select(func.count()).select_from(TransitionRow).where(
                TransitionRow.case_id == rt.case_id,
                TransitionRow.step == int(tr.get("step") or 0),
                TransitionRow.trigger_event == str(tr.get("trigger_event")),
                TransitionRow.resulting_state == str(tr.get("resulting_state")),
            ))
            if not exists:
                s.add(TransitionRow(
                    case_id=rt.case_id, run_id=rt.run_id, step=int(tr.get("step") or 0),
                    prior_state=tr["prior_state"], resulting_state=tr["resulting_state"],
                    trigger_event=tr["trigger_event"], status=tr["status"], actor=tr.get("actor", "SYSTEM"),
                    reason=str(tr.get("reason", ""))[:2000], invariant=tr.get("invariant"),
                    policy_refs=str(tr.get("policy_refs", ""))[:250], at=tr.get("at", ""),
                ))

        for a in rt.network.attempts:
            # Runtime attempt ids restart at AT-1 for every run, so the store keys them by run.
            stored_attempt_id = f"{rt.run_id}:{a.attempt_id}"
            row = s.get(AttemptRow, stored_attempt_id)
            if row is None:
                row = AttemptRow(attempt_id=stored_attempt_id, case_id=rt.case_id, channel=a.channel)
                s.add(row)
            # Attempts mutate as the network answers, so every persist must refresh the row:
            # a row written at dispatch time would otherwise keep delivered=False forever.
            row.result_revision_id = a.result_revision_id
            row.idempotency_key = a.idempotency_key
            row.accepted = a.accepted
            row.delivered = a.delivered
            row.failed = a.failed
            row.outcome = a.outcome
            row.reconciled = a.reconciled
            row.duplicate_suppressed = a.duplicate_suppressed
            row.created_at = a.created_at
            row.payload = json.dumps(asdict(a), default=str)
            if a.delivered:
                rid = f"{rt.run_id}:{a.attempt_id}-RECEIPT"
                if s.get(ReceiptRow, rid) is None:
                    s.add(ReceiptRow(receipt_id=rid, case_id=rt.case_id, attempt_id=stored_attempt_id,
                                     result_revision_id=a.result_revision_id, source="TRANSPORT",
                                     at=a.delivered_at or "", payload=json.dumps({"outcome": a.outcome})))

        for ack in rt.acknowledgments:
            # Same reasoning as attempts: ACK-n is only unique inside a run.
            stored_ack_id = f"{rt.run_id}:{ack['ack_id']}"
            if s.get(AcknowledgmentRow, stored_ack_id) is None:
                s.add(AcknowledgmentRow(
                    ack_id=stored_ack_id, case_id=rt.case_id, result_revision_id=ack["result_revision_id"],
                    role=ack.get("role", "PATIENT"), actor=ack.get("actor", ""),
                    channel=ack.get("channel", ""), identity_verified=bool(ack.get("identity_verified", True)),
                    at=ack.get("at", ""), payload=json.dumps(ack, default=str),
                ))

        for esc in rt.escalations:
            stored_escalation_id = f"{rt.run_id}:{esc['escalation_id']}"
            if s.get(EscalationRow, stored_escalation_id) is None:
                s.add(EscalationRow(
                    escalation_id=stored_escalation_id, case_id=rt.case_id, role=esc["role"],
                    reason=esc["reason"], triggered_by=esc["triggered_by"], status=esc["status"],
                    at=esc.get("at", ""), payload=json.dumps(esc, default=str),
                ))

        persisted_steps = {
            (r.agent_id, r.step) for r in s.scalars(select(AssessmentRow).where(AssessmentRow.run_id == rt.run_id))
        }
        for step in rt.steps:
            for agent in step["agents"]:
                if (agent["agent_id"], step["step"]) in persisted_steps:
                    continue
                s.add(AssessmentRow(
                    case_id=rt.case_id, run_id=rt.run_id, step=step["step"], agent_id=agent["agent_id"],
                    assessment_status=agent["assessment_status"], recommended_action=agent["recommended_action"],
                    confidence=float(agent["confidence"]), requires_human_review=bool(agent["requires_human_review"]),
                    payload=json.dumps(agent),
                ))
                for src in agent["applicable_sources"]:
                    s.add(CitationRow(
                        case_id=rt.case_id, run_id=rt.run_id, step=step["step"], agent_id=agent["agent_id"],
                        source_id=src["source_id"], section=src["section"], page=int(src["page"]),
                        claim_type=src["claim_type"],
                        consumed_by_decision=agent["agent_id"] in ("policy_applicability", "lab_workflow"),
                    ))

        existing_audit = s.scalar(select(func.count()).select_from(AuditRow).where(AuditRow.run_id == rt.run_id)) or 0
        for entry in (rt.audit.entries if rt.audit else [])[existing_audit:]:
            s.add(AuditRow(run_id=entry.run_id, case_id=entry.case_id, seq=entry.seq, at=entry.at,
                           event=entry.event, actor=entry.actor, summary=entry.summary,
                           prev_hash=entry.prev_hash, hash=entry.hash,
                           kb_index_sha256=entry.kb_index_sha256,
                           payload=json.dumps(entry.payload, default=str)))
        s.commit()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

@router.get("/health")
def health() -> dict[str, Any]:
    kb = retriever.retrieval_manifest()
    return {
        "status": "ok",
        "synthetic_data_only": settings.synthetic_data_only,
        "real_network_access": REAL_NETWORK_ACCESS,
        "real_ehr_integration": False,
        "llm_provider": "disabled (deterministic mode)",
        "advisory_boundary": {
            "status": "closed" if not settings.enable_llm else "open (advisory only)",
            "can_change_a_decision": False,
            "residency_rule": "Federal Law 2/2019 Art. 13 - out-of-country processing refused without a Health Authority resolution",
            "containment_tests": "backend/tests/test_adviser.py",
        },
        "knowledge_base": kb,
        "settings": describe(),
        "disclaimer": settings.disclaimer,
    }


@router.get("/meta/state-machine")
def state_machine() -> dict[str, Any]:
    return {
        "states": {s.value: STATE_DESCRIPTIONS[s] for s in CaseState},
        "transitions": transition_table_as_dicts(),
        "configurations": {
            name: {
                "label": cfg.label,
                "description": cfg.description,
                "use_kb": cfg.use_kb,
                "applicability_filter": cfg.applicability_filter,
                "use_invariants": cfg.use_invariants,
                "acknowledgement_scope": cfg.acknowledgement_scope,
                "transport_semantics": cfg.transport_semantics,
                "agents": list(cfg.agents),
            }
            for name, cfg in CONFIGS.items()
        },
        "institutional_profile": DEFAULT_PROFILE,
    }


# ---------------------------------------------------------------------------
# Dashboard and cases
# ---------------------------------------------------------------------------

AWAITING = {
    "awaiting_delivery": ["TRANSMISSION_QUEUED", "TRANSMISSION_ATTEMPTED", "TRANSPORT_ACCEPTED"],
    "awaiting_acknowledgment": ["DELIVERY_CONFIRMED", "TRANSMISSION_ATTEMPTED"],
    "uncertain": ["DELIVERY_STATE_UNKNOWN", "RETRY_PENDING"],
    "correction": ["CORRECTION_PENDING", "CORRECTED_RESULT_FINALIZED", "CORRECTED_RESULT_DELIVERY_PENDING"],
    "escalation": ["ESCALATION_REQUIRED", "ESCALATION_IN_REVIEW"],
}


@router.get("/dashboard")
def dashboard() -> dict[str, Any]:
    s = session()
    try:
        rows = list(s.scalars(select(CaseRow)))
        active = [r for r in rows if r.current_state not in ("SUPERSEDED",)]
        counters = {
            "active_cases": len(active),
            "awaiting_delivery": sum(1 for r in active if r.current_state in AWAITING["awaiting_delivery"]),
            "awaiting_acknowledgment": sum(1 for r in active if r.current_state in AWAITING["awaiting_acknowledgment"]),
            "uncertain_delivery": sum(1 for r in active if r.current_state in AWAITING["uncertain"]),
            "corrections_pending": sum(1 for r in active if r.current_state in AWAITING["correction"]),
            "escalations_open": sum(1 for r in active if r.current_state in AWAITING["escalation"]),
            "documented": sum(1 for r in active if r.current_state == "COMMUNICATION_DOCUMENTED"),
        }
        recent = s.scalars(
            select(AuditRow).order_by(AuditRow.id.desc()).limit(18)
        ).all()
        return {
            "counters": counters,
            "filters": {k: v for k, v in AWAITING.items()},
            "recent_audit": [
                {"seq": r.seq, "at": r.at, "event": r.event, "actor": r.actor,
                 "summary": r.summary, "case_id": r.case_id, "hash": r.hash[:12]}
                for r in recent
            ],
            "synthetic": True,
            "note": "Counters are aggregates over stored case rows, not frontend state.",
        }
    finally:
        s.close()


@router.get("/cases")
def cases(
    state: str | None = Query(default=None),
    config: str | None = None,
    group: str | None = Query(default=None, description="awaiting_delivery|awaiting_acknowledgment|uncertain|correction|escalation"),
) -> dict[str, Any]:
    rows = list_cases()
    if group:
        wanted = set(AWAITING.get(group, []))
        rows = [r for r in rows if r["current_state"] in wanted]
    if state:
        wanted = {s.strip().upper() for s in state.split(",") if s.strip()}
        rows = [r for r in rows if r["current_state"] in wanted]
    if config:
        rows = [r for r in rows if r["configuration"] == config]

    s = session()
    try:
        for r in rows:
            cid = r["case_id"]
            r["revision_count"] = s.scalar(
                select(func.count()).select_from(RevisionRow).where(RevisionRow.case_id == cid)
            ) or 0
            r["acknowledgment_count"] = s.scalar(
                select(func.count()).select_from(AcknowledgmentRow).where(AcknowledgmentRow.case_id == cid)
            ) or 0
            r["delivered_attempts"] = s.scalar(
                select(func.count()).select_from(AttemptRow).where(
                    AttemptRow.case_id == cid, AttemptRow.delivered.is_(True)
                )
            ) or 0
            r["escalation_count"] = s.scalar(
                select(func.count()).select_from(EscalationRow).where(EscalationRow.case_id == cid)
            ) or 0
            current = r.get("current_revision_id")
            r["acknowledges_current"] = bool(current) and bool(s.scalar(
                select(func.count()).select_from(AcknowledgmentRow).where(
                    AcknowledgmentRow.case_id == cid, AcknowledgmentRow.result_revision_id == current
                )
            ))
            payload = json.loads(s.get(CaseRow, cid).payload or "{}")
            r["open_questions"] = payload.get("open_questions", [])
            r["blocking_conditions"] = payload.get("blocking_conditions", [])
    finally:
        s.close()
    return {"cases": rows, "count": len(rows)}


@router.get("/cases/{case_id}")
def case_detail(case_id: str) -> dict[str, Any]:
    case = get_case(case_id)
    if case is None:
        raise HTTPException(404, f"case {case_id} not found")
    s = session()
    try:
        events = s.scalars(select(EventRow).where(EventRow.case_id == case_id).order_by(EventRow.seq)).all()
        transitions = s.scalars(
            select(TransitionRow).where(TransitionRow.case_id == case_id).order_by(TransitionRow.id)
        ).all()
        acks = s.scalars(select(AcknowledgmentRow).where(AcknowledgmentRow.case_id == case_id)).all()
        attempts = s.scalars(select(AttemptRow).where(AttemptRow.case_id == case_id)).all()
        escalations = s.scalars(select(EscalationRow).where(EscalationRow.case_id == case_id)).all()
        citations = s.scalars(select(CitationRow).where(CitationRow.case_id == case_id)).all()
        revisions = s.scalars(select(RevisionRow).where(RevisionRow.case_id == case_id)).all()
        return {
            "case": case,
            "revisions": [
                {"revision_id": r.revision_id, "version": r.version, "status": r.status,
                 "supersedes_revision_id": r.supersedes_revision_id, "test_name": r.test_name,
                 "finalized_at": r.finalized_at}
                for r in revisions
            ],
            "events": [
                {"seq": e.seq, "at": e.at, "kind": e.kind, "actor": e.actor,
                 "source_layer": e.source_layer, "summary": e.summary, "payload": json.loads(e.payload or "{}")}
                for e in events
            ],
            "transitions": [
                {"step": t.step, "prior_state": t.prior_state, "resulting_state": t.resulting_state,
                 "trigger_event": t.trigger_event, "status": t.status, "reason": t.reason,
                 "invariant": t.invariant, "at": t.at, "actor": t.actor}
                for t in transitions
            ],
            "acknowledgments": [
                {"ack_id": a.ack_id, "result_revision_id": a.result_revision_id, "role": a.role,
                 "channel": a.channel, "at": a.at, "identity_verified": a.identity_verified}
                for a in acks
            ],
            "attempts": [
                {"attempt_id": a.attempt_id, "channel": a.channel, "result_revision_id": a.result_revision_id,
                 "accepted": a.accepted, "delivered": a.delivered, "failed": a.failed,
                 "outcome": a.outcome, "reconciled": a.reconciled, "duplicate_suppressed": a.duplicate_suppressed}
                for a in attempts
            ],
            "escalations": [
                {"escalation_id": e.escalation_id, "role": e.role, "reason": e.reason, "status": e.status, "at": e.at}
                for e in escalations
            ],
            "citations": [
                {"source_id": c.source_id, "section": c.section, "page": c.page,
                 "claim_type": c.claim_type, "step": c.step, "agent_id": c.agent_id}
                for c in citations
            ],
        }
    finally:
        s.close()


@router.get("/cases/{case_id}/audit")
def case_audit(case_id: str) -> dict[str, Any]:
    """Audit chain for a stored case, re-verified after being read back from the store."""
    case = get_case(case_id)
    if case is None:
        raise HTTPException(404, f"case {case_id} not found")
    s = session()
    try:
        rows = s.scalars(select(AuditRow).where(AuditRow.case_id == case_id).order_by(AuditRow.seq)).all()
        entries = [
            {
                "seq": r.seq, "at": r.at, "run_id": r.run_id, "case_id": r.case_id, "event": r.event,
                "actor": r.actor, "summary": r.summary, "payload": json.loads(r.payload or "{}"),
                "prev_hash": r.prev_hash, "hash": r.hash,
                "kb_index_sha256": r.kb_index_sha256 or "",
                "kb_index_sha256": r.kb_index_sha256 or "",
            }
            for r in rows
        ]
        ok, broken = verify_entries(entries)
        return {
            "case_id": case_id,
            "run_id": case.get("run_id"),
            "entries": entries,
            "count": len(entries),
            "chain_valid": ok,
            "broken_sequences": broken,
            "verification": "Recomputed from stored rows; the writer's claim is not trusted.",
        }
    finally:
        s.close()


def export_case(case_id: str) -> dict[str, Any]:
    detail = case_detail(case_id)
    chain = case_audit(case_id)
    return {
        "bundle_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "synthetic": True,
        "case": detail,
        "audit_log": chain["entries"],
        "audit_chain_valid": chain["chain_valid"],
        "knowledge_base": retriever.retrieval_manifest(),
        "note": (
            "Synthetic demonstration data. Re-executing the same scenario with the same configuration "
            "reproduces the same state signature; see evaluation/report.md."
        ),
    }


@router.get("/cases/{case_id}/bundle")
def case_bundle(case_id: str) -> dict[str, Any]:
    if get_case(case_id) is None:
        raise HTTPException(404, f"case {case_id} not found")
    return export_case(case_id)


# ---------------------------------------------------------------------------
# Scenario runs (progressive simulator)
# ---------------------------------------------------------------------------

class StartRun(BaseModel):
    scenario_id: str
    configuration: str = Field(default="resultrelay")
    reset_case: bool = True


@router.get("/scenarios")
def scenarios() -> dict[str, Any]:
    return {"scenarios": list_scenarios(), "configurations": {
        name: {"label": c.label, "description": c.description} for name, c in CONFIGS.items()
    }}


@router.post("/runs")
def start_run(body: StartRun) -> dict[str, Any]:
    if body.configuration not in CONFIGS:
        raise HTTPException(400, f"unknown configuration {body.configuration}")
    try:
        scenario = load_scenario(body.scenario_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    run_id = f"RUN-{uuid.uuid4().hex[:10]}"
    # The same scenario is meant to be replayed under each configuration and compared, so the
    # case is keyed by scenario *and* configuration rather than letting the last run win.
    base_case_id = scenario.get("case_id") or f"SYN-{scenario['scenario_id']}"
    rt = build_runtime(
        scenario, body.configuration, run_id, case_id=f"{base_case_id}-{body.configuration}"
    )
    orch = Orchestrator(rt)
    run_registry.put(run_id, {"runtime": rt, "orchestrator": orch, "scenario": scenario, "cursor": 0})
    _persist(rt)
    return {"run": serialise_runtime(rt), "events_remaining": len(scenario["steps"])}


@router.post("/runs/{run_id}/step")
def step_run(run_id: str) -> dict[str, Any]:
    entry = run_registry.get(run_id)
    if entry is None:
        raise HTTPException(404, "run not found in this server process; start a new run")
    scenario = entry["scenario"]
    cursor = entry["cursor"]
    if cursor >= len(scenario["steps"]):
        return {"done": True, "run": serialise_runtime(entry["runtime"])}
    spec = scenario["steps"][cursor]
    result = entry["orchestrator"].step(spec)
    entry["cursor"] = cursor + 1
    _persist(entry["runtime"])
    return {
        "done": entry["cursor"] >= len(scenario["steps"]),
        "step": serialise_step(result),
        "run": serialise_runtime(entry["runtime"]),
        "progress": {"released": entry["cursor"], "total": len(scenario["steps"])},
    }


@router.post("/runs/{run_id}/play")
def play_run(run_id: str) -> dict[str, Any]:
    entry = run_registry.get(run_id)
    if entry is None:
        raise HTTPException(404, "run not found")
    while entry["cursor"] < len(entry["scenario"]["steps"]):
        entry["orchestrator"].step(entry["scenario"]["steps"][entry["cursor"]])
        entry["cursor"] += 1
    _persist(entry["runtime"])
    return {"run": serialise_runtime(entry["runtime"])}


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    entry = run_registry.get(run_id)
    if entry is None:
        raise HTTPException(404, "run not found in this server process")
    return serialise_runtime(entry["runtime"])


@router.get("/runs/{run_id}/audit")
def audit_bundle(run_id: str) -> dict[str, Any]:
    """Reproducible audit bundle: scenario, configuration, event stream, decisions, chain."""
    entry = run_registry.get(run_id)
    if entry is None:
        raise HTTPException(404, "run not found in this server process")
    rt = entry["runtime"]
    ok, broken = rt.audit.verify_chain() if rt.audit else (False, [])
    return {
        "bundle_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "synthetic": True,
        "scenario": entry["scenario"],
        "configuration": rt.config.name,
        "configuration_detail": asdict(rt.config),
        "institutional_profile": rt.profile,
        "events": rt.events,
        "steps": [serialise_step(s) for s in rt.steps],
        "transitions": rt.transitions,
        "attempts": [asdict(a) for a in rt.network.attempts],
        "transport_ledger": rt.network.ledger,
        "acknowledgments": rt.acknowledgments,
        "escalations": rt.escalations,
        "revisions": rt.revisions,
        "audit_log": rt.audit.as_list() if rt.audit else [],
        "audit_chain_valid": ok,
        "audit_broken_sequences": broken,
        "knowledge_base": retriever.retrieval_manifest(),
        "note": "Replaying this bundle with the same configuration reproduces the same state signature.",
    }


@router.get("/channels")
def channels(run_id: str | None = None) -> dict[str, Any]:
    if run_id:
        entry = run_registry.get(run_id)
        if entry is None:
            raise HTTPException(404, "run not found")
        return {"channels": entry["runtime"].network.channel_manifest(), "synthetic": True}
    return {
        "channels": [
            {"channel_id": c["channel_id"], "kind": c["kind"], "primary": c["primary"],
             "status": "UP", "note": "template channel; actual status is per-run"}
            for c in DEFAULT_PROFILE["channels"]
        ],
        "synthetic": True,
    }


# ---------------------------------------------------------------------------
# Knowledge base, gaps, mappings, evaluation
# ---------------------------------------------------------------------------

@router.get("/kb/sources")
def kb_sources() -> dict[str, Any]:
    with (KB_DIR / "source_register.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    counts = {}
    for c in retriever.all_chunks():
        counts[c["source_id"]] = counts.get(c["source_id"], 0) + 1
    for r in rows:
        r["chunk_count"] = counts.get(r["source_id"], 0)
    return {"sources": rows, "count": len(rows), "manifest": retriever.retrieval_manifest()}


@router.get("/kb/search")
def kb_search(
    q: str = Query(min_length=2),
    jurisdiction: str | None = None,
    scope: str = Query(default="all", pattern="^(all|applicable|comparator)$"),
    claim: str | None = None,
    top_k: int = Query(default=8, ge=1, le=25),
) -> dict[str, Any]:
    result = retriever.search(
        q,
        jurisdiction=jurisdiction,
        scope=scope,
        claim_classifications=claim.split(",") if claim else None,
        top_k=top_k,
    )
    return result.model_dump()


@router.get("/kb/chunks/{chunk_id}")
def kb_chunk(chunk_id: str) -> dict[str, Any]:
    for c in retriever.all_chunks():
        if c["chunk_id"] == chunk_id:
            return c
    raise HTTPException(404, f"chunk {chunk_id} not found")


@router.get("/gaps")
def gaps(classification: str | None = None, jurisdiction: str | None = None) -> dict[str, Any]:
    with (KB_DIR / "gap_register.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if classification:
        wanted = {c.strip() for c in classification.split(",")}
        rows = [r for r in rows if r["classification"] in wanted]
    if jurisdiction:
        rows = [r for r in rows if jurisdiction in r["jurisdictions_compared"]]
    facets: dict[str, list[str]] = {
        "classification": sorted({r["classification"] for r in rows}),
        "verification_status": sorted({r["verification_status"] for r in rows}),
        "workflow_stage": sorted({r["workflow_stage"] for r in rows}),
        "confidence": sorted({r["confidence"] for r in rows}),
        "jurisdictions": sorted({r["jurisdictions_compared"] for r in rows}),
    }
    return {"gaps": rows, "count": len(rows), "facets": facets}


@router.get("/mappings/{name}")
def mappings(name: str) -> dict[str, Any]:
    files = {"y3172": "itu_y3172_mapping.csv", "readiness": "ai_readiness_mapping.csv"}
    if name not in files:
        raise HTTPException(404, "unknown mapping")
    with (KB_DIR / "mappings" / files[name]).open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return {"mapping": name, "rows": rows, "count": len(rows)}


class EvalRequest(BaseModel):
    configurations: list[str] | None = None


@router.post("/evaluation/run")
def run_evaluation(body: EvalRequest | None = None) -> dict[str, Any]:
    from app.evaluation.runner import run_all, write_markdown

    report = run_all(body.configurations if body else None)
    write_markdown(report, REPO_ROOT / "evaluation" / "report.md")
    return {"summary": report["summary"], "run_count": report["run_count"],
            "run_finished": report["run_finished"]}


@router.get("/evaluation/latest")
def latest_evaluation() -> dict[str, Any]:
    path = REPO_ROOT / "evaluation" / "results" / "latest.json"
    if not path.exists():
        raise HTTPException(404, "no evaluation has been run yet")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/evaluation/scenario/{scenario_id}")
def evaluation_scenario(scenario_id: str) -> dict[str, Any]:
    path = REPO_ROOT / "evaluation" / "results" / "latest.json"
    if not path.exists():
        raise HTTPException(404, "no evaluation has been run yet")
    report = json.loads(path.read_text(encoding="utf-8"))
    runs = [r for r in report["runs"] if r["scenario_id"] == scenario_id]
    if not runs:
        raise HTTPException(404, "scenario not present in the latest evaluation")
    return {"scenario_id": scenario_id, "runs": runs}
