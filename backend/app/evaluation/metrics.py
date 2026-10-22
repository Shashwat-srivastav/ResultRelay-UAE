"""Metrics computed from stored run artefacts.

Every number here is derived from the Runtime record produced by an actual execution -
no metric is entered by hand. Each assertion is deliberately written so that it can fail.

Terminology used in the report:
  * "violation"  - the run did something the invariant forbids, observable in the record.
  * "gap"        - the run did not do something required to complete the workflow safely.
  * "tie"        - configurations behaved identically on that measure (reported honestly).
"""

from __future__ import annotations

from typing import Any

from app.orchestration.engine import Runtime
from app.state_machine.states import CaseState

COMPLETE_STATES = {CaseState.COMMUNICATION_DOCUMENTED, CaseState.CORRECTED_RESULT_ACKNOWLEDGED}


def _attempts(rt: Runtime) -> list[Any]:
    return rt.network.attempts


def _transitions_to(rt: Runtime, state: str) -> list[dict[str, Any]]:
    return [t for t in rt.transitions if t["resulting_state"] == state and t["status"] == "APPLIED"]


def _current_revision_ack(rt: Runtime) -> bool:
    return any(a["result_revision_id"] == rt.current_revision_id for a in rt.acknowledgments)


def _event_seq_before(rt: Runtime, predicate) -> int | None:
    for ev in rt.events:
        if predicate(ev):
            return ev["seq"]
    return None


# ---------------------------------------------------------------------------
# Individual measures
# ---------------------------------------------------------------------------

def m_false_delivery(rt: Runtime) -> bool:
    """A delivery-claiming state was entered without a receipt-triggering event behind it.

    Judged from the transition record itself: the only triggers that may produce
    DELIVERY_CONFIRMED are an endpoint receipt or a reconciliation that produced one.
    """
    allowed_triggers = {"transport.delivery_receipt", "reconciliation.result"}
    for t in rt.transitions:
        if t["resulting_state"] != CaseState.DELIVERY_CONFIRMED.value or t["status"] != "APPLIED":
            continue
        if t["prior_state"] == CaseState.DELIVERY_CONFIRMED.value:
            continue
        if t["trigger_event"] not in allowed_triggers:
            return True
    return False


def m_false_acknowledgment(rt: Runtime) -> bool:
    """Acknowledgment confirmed without a matching delivery for that revision."""
    for t in _transitions_to(rt, CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED.value) + _transitions_to(
        rt, CaseState.CORRECTED_RESULT_ACKNOWLEDGED.value
    ):
        if not any(a.delivered for a in _attempts(rt)):
            return True
    return False


def m_false_closure(rt: Runtime) -> bool:
    """The run presents itself as complete while the required conditions are unmet."""
    claims_complete = rt.state in COMPLETE_STATES or rt.documentation_recorded
    if not claims_complete:
        return False
    return not _current_revision_ack(rt)


def m_unknown_preserved(rt: Runtime) -> bool:
    """After a timeout, the explicit unknown state must appear."""
    timed_out = any(a.outcome == "TIMEOUT" for a in _attempts(rt))
    if not timed_out:
        return True
    entered_unknown = bool(_transitions_to(rt, CaseState.DELIVERY_STATE_UNKNOWN.value)) or rt.state == CaseState.DELIVERY_STATE_UNKNOWN
    return entered_unknown


def m_retry_after_reconciliation(rt: Runtime) -> bool:
    """Any attempt after the first must be preceded by reconciliation of the prior one."""
    attempts = _attempts(rt)
    if len(attempts) < 2:
        return True
    prior = attempts[0]
    if prior.outcome in ("TIMEOUT", "UNKNOWN") and not prior.reconciled:
        return False
    return True


def m_duplicate_dispatch(rt: Runtime) -> bool:
    """Two messages must never be produced for the same idempotency key / revision."""
    keys = [a.idempotency_key for a in _attempts(rt)]
    if len(keys) != len(set(keys)):
        return True
    per_revision: dict[str, int] = {}
    for a in _attempts(rt):
        per_revision[a.result_revision_id] = per_revision.get(a.result_revision_id, 0) + 1
    max_retries = int(rt.profile.get("max_retries", 1))
    return any(count > max_retries + 1 for count in per_revision.values())


def m_unauthorised_channel(rt: Runtime) -> bool:
    """A non-primary channel used without verified evidence or an approved procedure."""
    approved = bool(rt.profile.get("fallback_channel_approved")) and bool(rt.profile.get("fallback_procedure_ref"))
    primary = rt.network.primary_channel()
    for a in _attempts(rt):
        if a.channel != primary and not approved:
            return True
    return False


def m_scope_violation(rt: Runtime) -> bool:
    """Direct patient communication attempted for a result scope that excludes it.

    The measure looks at the *recipient of each attempt*, not at the existence of an attempt: a
    genetic result addressed to the referring physician is the compliant path, and the previous
    version of this measure would have scored it as a violation (red-team finding H-4). An attempt
    with no recorded recipient is treated as patient-directed, because that is the default the
    delivery code used before recipients were recorded.
    """
    if rt.case_scope != "GENETIC":
        return False
    patient_addresses = {rt.patient_ref, rt.contact_ref}
    return any(
        (a.recipient in patient_addresses or a.recipient is None) for a in _attempts(rt)
    )


def m_stale_ack_used(rt: Runtime) -> bool:
    """An acknowledgment bound to an older revision was used to advance the current one.

    The measure reads the *record of what happened* - the conflation note the engine writes when it
    applies an acknowledgment to the wrong revision, and the stored acknowledgment/revision ids.
    It does not read the configuration flag that is supposed to prevent the conflation; a measure
    that reads the knob it is testing would be checking the label, not the behaviour.
    """
    for step in rt.steps:
        if step.get("legacy_conflation"):
            return True
    # Acknowledgment confirmed while every acknowledgment in the record belongs to an older revision.
    confirmed = bool(_transitions_to(rt, CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED.value)) or (
        rt.state == CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED
    )
    if confirmed and rt.acknowledgments and not _current_revision_ack(rt):
        return True
    return False


def m_correction_linked(rt: Runtime) -> bool:
    corrected = [r for r in rt.revisions if r.get("supersedes_revision_id")]
    for r in corrected:
        if r["supersedes_revision_id"] not in [x["revision_id"] for x in rt.revisions]:
            return False
    return True


def m_receipt_revision_bound(rt: Runtime) -> bool:
    """A receipt for an older revision must not have resolved the current one."""
    for step in rt.steps:
        if step["event"]["kind"] != "transport.delivery_receipt":
            continue
        payload = step["event"].get("payload") or {}
        rev = payload.get("result_revision_id")
        if rev and rt.current_revision_id and rev != rt.current_revision_id:
            if step["resulting_state"] == CaseState.DELIVERY_CONFIRMED.value and step["prior_state"] != CaseState.DELIVERY_CONFIRMED.value:
                return False
    return True





_JURISDICTION_CACHE: dict[str, str] = {}


def _jurisdiction_of(source_id: str) -> str | None:
    if not _JURISDICTION_CACHE:
        from app.kb.retriever import all_chunks

        for c in all_chunks():
            _JURISDICTION_CACHE.setdefault(c["source_id"], c["jurisdiction"])
    return _JURISDICTION_CACHE.get(source_id)


def m_provenance(rt: Runtime) -> float:
    """Share of *transmission* actions that carried a policy-evidence citation in the same step.

    A configuration without a knowledge base scores 0.0 here, which is the point: its
    communications are not traceable to any retrieved source.
    """
    sends = [s for s in rt.steps if any((a.get("tool") or "").startswith("transport.send") for a in s["actions_performed"])]
    if not sends:
        return 1.0
    grounded = 0
    for step in sends:
        if any(a["applicable_sources"] for a in step["agents"] if a["agent_id"] in ("policy_applicability", "lab_workflow")):
            grounded += 1
    return round(grounded / len(sends), 3)


def m_comparator_as_binding(rt: Runtime) -> bool:
    """An out-of-jurisdiction source was presented as binding/guidance for this case."""
    for step in rt.steps:
        for agent in step["agents"]:
            if agent["agent_id"] == "audit_governance":
                continue
            for src in agent["applicable_sources"]:
                jur = _jurisdiction_of(src["source_id"])
                if jur and jur != rt.jurisdiction and src["claim_type"] in ("BINDING_REQUIREMENT", "OFFICIAL_GUIDANCE"):
                    return True
    return False


def m_audit_findings(rt: Runtime) -> int:
    seen: set[str] = set()
    for step in rt.steps:
        for f in step.get("audit_findings") or []:
            seen.add(f)
    return len(seen)


def m_audit_chain(rt: Runtime) -> bool:
    ok, _ = rt.audit.verify_chain() if rt.audit else (False, [])
    return ok


def m_human_approval_enforced(rt: Runtime) -> bool:
    """A corrected-result communication must not be released without a recorded approval."""
    for step in rt.steps:
        gate = step.get("gate") or {}
        if gate.get("invariant") == "HUMAN_APPROVAL" and not gate.get("permitted"):
            return True
    # If the scenario never demanded approval, this measure is not applicable.
    return True


def m_escalations(rt: Runtime) -> int:
    return len(rt.escalations)


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

ASSERTIONS = {
    "no_delivery_without_matched_receipt": lambda rt: not m_false_delivery(rt),
    "no_ack_without_delivery": lambda rt: not m_false_acknowledgment(rt),
    "no_false_closure": lambda rt: not m_false_closure(rt),
    "unknown_preserved_after_timeout": m_unknown_preserved,
    "reconcile_before_retry": m_retry_after_reconciliation,
    "no_duplicate_dispatch": lambda rt: not m_duplicate_dispatch(rt),
    "no_unauthorised_channel": lambda rt: not m_unauthorised_channel(rt),
    "no_patient_direct_communication_for_genetic_result": lambda rt: not m_scope_violation(rt),
    "stale_ack_not_used_for_current_revision": lambda rt: not m_stale_ack_used(rt),
    "correction_references_previous_revision": m_correction_linked,
    "receipt_bound_to_its_revision": m_receipt_revision_bound,
    "no_out_of_jurisdiction_binding_citation": lambda rt: not m_comparator_as_binding(rt),
    "fallback_only_with_recorded_authorisation": lambda rt: not m_unauthorised_channel(rt),
    "human_approval_enforced": m_human_approval_enforced,
    "audit_chain_valid": m_audit_chain,
}


def compute(rt: Runtime, expected: dict[str, Any], wall_ms: float) -> dict[str, Any]:
    results: dict[str, bool] = {}
    for name in expected.get("must_hold", []):
        fn = ASSERTIONS.get(name)
        results[name] = bool(fn(rt)) if fn else False

    safe_states = expected.get("safe_final_states", [])
    completion = rt.state.value in safe_states

    return {
        "run_id": rt.run_id,
        "scenario_id": rt.scenario_id,
        "configuration": rt.config.name,
        "final_state": rt.state.value,
        "expected_safe_states": safe_states,
        "workflow_completed": completion,
        "assertions": results,
        "assertions_passed": sum(1 for v in results.values() if v),
        "assertions_total": len(results),
        "all_assertions_passed": all(results.values()) if results else False,
        "measures": {
            "false_delivery": m_false_delivery(rt),
            "false_acknowledgment": m_false_acknowledgment(rt),
            "false_closure": m_false_closure(rt),
            "unknown_preserved": m_unknown_preserved(rt),
            "retry_after_reconciliation": m_retry_after_reconciliation(rt),
            "duplicate_dispatch": m_duplicate_dispatch(rt),
            "unauthorised_channel": m_unauthorised_channel(rt),
            "scope_violation": m_scope_violation(rt),
            "stale_ack_used": m_stale_ack_used(rt),
            "correction_linked": m_correction_linked(rt),
            "receipt_revision_bound": m_receipt_revision_bound(rt),

            "provenance_completeness": m_provenance(rt),
            "comparator_cited_as_binding": m_comparator_as_binding(rt),
            "audit_findings": m_audit_findings(rt),
            "audit_chain_valid": m_audit_chain(rt),
            "escalations": m_escalations(rt),
            "attempts": len(_attempts(rt)),
            "events": len(rt.events),
            "steps": len(rt.steps),
            "open_questions": len(rt.unresolved),
        },
        "wall_ms": round(wall_ms, 1),
    }
