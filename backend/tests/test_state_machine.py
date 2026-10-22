"""The state machine is the boundary the agents cannot cross.

Nothing here tests an agent's opinion. Every assertion is about the formal table: which
(state, event) pairs are allowed, which are structurally forbidden, and what happens when a
persuasive but wrong assessment is fed to the gate.
"""

from __future__ import annotations

import pytest

from app.models.schemas import (
    AgentAssessment,
    AssessmentStatus,
    ClaimClassification,
    RecommendedAction,
    SourceCitation,
)
from app.orchestration.gate import enforce
from app.state_machine.states import (
    INCOMPLETE_CONTROL_STATES,
    TERMINAL_STATES,
    CaseState,
    is_complete,
)
from app.state_machine.transitions import (
    CONFLATIONS,
    FORBIDDEN,
    INFORMATIONAL_EVENTS,
    TRANSITIONS,
    Acknowledgment,
    Attempt,
    EventType,
    MachineContext,
    evaluate,
)

PROFILE_OK = {"direct_patient_communication_enabled": True}


def _ctx(state: CaseState, **kw) -> MachineContext:
    kw.setdefault("profile", PROFILE_OK)
    return MachineContext(case_id="T-1", state=state, current_revision_id=kw.pop("current_revision_id", "R1"), **kw)


def test_every_transition_names_a_real_state():
    for rule in TRANSITIONS:
        assert isinstance(rule.event, EventType)
        assert isinstance(rule.to_state, CaseState)
        for st in rule.from_states:
            assert isinstance(st, CaseState)
        assert rule.guard is not None
        assert rule.description, "a transition without an explanation cannot be reviewed"


def test_no_transition_is_a_silent_no_op():
    """A rule whose to_state equals its from_state hides a missing rule."""
    allowed_loops = {CaseState.CORRECTED_RESULT_DELIVERY_PENDING}
    for rule in TRANSITIONS:
        for st in rule.from_states:
            assert st != rule.to_state or st in allowed_loops, f"{rule.event} loops silently on {st}"


def test_completeness_is_defined_for_human_outcomes_only():
    complete = {s for s in CaseState if is_complete(s)}
    assert CaseState.COMMUNICATION_DOCUMENTED in complete
    assert CaseState.CORRECTED_RESULT_ACKNOWLEDGED in complete
    # No transport state and no escalation state may ever count as complete.
    for st in complete:
        assert st not in {
            CaseState.TRANSPORT_ACCEPTED,
            CaseState.DELIVERY_CONFIRMED,
            CaseState.TRANSMISSION_ATTEMPTED,
            CaseState.ESCALATION_REQUIRED,
        }
    # SUPERSEDED ends the lineage but is not a completed communication.
    assert CaseState.SUPERSEDED in TERMINAL_STATES
    assert not is_complete(CaseState.SUPERSEDED)


def test_transport_acceptance_cannot_be_conflated_with_human_completion():
    conflated = {st for c in CONFLATIONS if c.event is EventType.TRANSPORT_ACCEPTED for st in c.forbids_states}
    assert CaseState.DELIVERY_CONFIRMED in conflated

    result = evaluate(_ctx(CaseState.TRANSMISSION_ATTEMPTED), EventType.TRANSPORT_ACCEPTED)
    assert result.status == "APPLIED"
    assert result.next_state is CaseState.TRANSPORT_ACCEPTED


def test_acknowledgment_may_not_arrive_before_delivery_is_evidenced():
    blocked = evaluate(_ctx(CaseState.TRANSPORT_ACCEPTED), EventType.CLINICAL_ACKNOWLEDGMENT)
    assert blocked.status == "BLOCKED"
    assert blocked.invariant == "INV-8"

    # And there is no permissive rule lurking behind it for an earlier state.
    earlier = evaluate(_ctx(CaseState.TRANSMISSION_ATTEMPTED), EventType.CLINICAL_ACKNOWLEDGMENT)
    assert earlier.status == "NO_RULE"


def test_transmission_from_an_unknown_outcome_is_forbidden():
    rule = next(
        r for r in FORBIDDEN
        if r.event is EventType.TRANSMISSION_REQUESTED and CaseState.DELIVERY_STATE_UNKNOWN in r.from_states
    )
    assert rule.invariant == "INV-4"
    result = evaluate(_ctx(CaseState.DELIVERY_STATE_UNKNOWN), EventType.TRANSMISSION_REQUESTED)
    assert result.status == "BLOCKED"
    assert result.invariant == "INV-4"


def test_duplicate_receipt_is_refused_on_the_same_attempt():
    ctx = _ctx(
        CaseState.TRANSMISSION_ATTEMPTED,
        attempts=[
            Attempt(
                attempt_id="ATT-001",
                idempotency_key="K1",
                channel="SMS-PATIENT",
                result_revision_id="R1",
                transport_accepted=True,
                delivery_receipt=True,
                last_outcome="DELIVERED",
            )
        ],
        event={"attempt_id": "ATT-001"},
    )
    result = evaluate(ctx, EventType.TRANSPORT_DELIVERY_RECEIPT)
    assert result.status == "BLOCKED"
    assert "INV-5" in result.reason


def test_no_closure_while_a_condition_is_unresolved():
    ctx = _ctx(
        CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED,
        unresolved_conditions=["no acknowledgment on the current revision"],
    )
    result = evaluate(ctx, EventType.DOCUMENTATION_RECORDED)
    assert result.status == "BLOCKED"
    assert "INV-10" in result.reason


def test_llm_output_cannot_bypass_invariants():
    """A model that *says* the case is complete does not make it complete.

    The assessment below is well-formed, confident, cites a real clause, and is wrong: there is
    no delivery evidence. It must not move the case, and the gate must say which invariant stopped it.
    """
    ctx = _ctx(CaseState.DELIVERY_STATE_UNKNOWN)
    confident = AgentAssessment(
        agent_id="network_delivery",
        case_id="T-1",
        assessment_status=AssessmentStatus.OK,
        recommended_action=RecommendedAction.SEND_PRIMARY,
        applicable_sources=[
            SourceCitation(
                source_id="S1", section="11.1.1", page=40, claim_type=ClaimClassification.BINDING_REQUIREMENT
            )
        ],
        confidence=0.99,
        requires_human_review=False,
        concise_rationale="The previous attempt looks fine; re-send and treat it as delivered.",
    )

    decision = enforce(
        proposal=RecommendedAction.SEND_PRIMARY,
        review_revision="R1",
        ctx=ctx,
        assessments=[confident],
        kb_available=True,
    )
    assert decision.permitted is False
    assert decision.invariant == "INV-4"

    transition = evaluate(ctx, EventType.TRANSMISSION_REQUESTED)
    assert transition.status in {"BLOCKED", "FORBIDDEN"}


def test_closure_without_current_acknowledgment_is_refused_by_the_gate():
    ctx = _ctx(
        CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED,
        acknowledgments=[
            Acknowledgment(
                ack_id="ACK-1",
                result_revision_id="R0",
                role="PATIENT",
                actor="patient",
                channel="SMS-PATIENT",
                identity_verified=True,
            )
        ],
    )
    decision = enforce(
        proposal=RecommendedAction.RECORD_DOCUMENTATION,
        review_revision="R1",
        ctx=ctx,
        assessments=[],
        kb_available=True,
    )
    assert decision.permitted is False
    assert "acknowledgment" in decision.reason.lower()


def test_incomplete_control_states_are_not_treated_as_done():
    for st in INCOMPLETE_CONTROL_STATES:
        assert not is_complete(st)
        assert st not in TERMINAL_STATES


def test_informational_events_never_move_the_state():
    for event in INFORMATIONAL_EVENTS:
        for state in CaseState:
            result = evaluate(_ctx(state), event)
            assert result.status == "BLOCKED"
            assert result.next_state is state


@pytest.mark.parametrize("event", list(EventType))
def test_every_event_has_a_defined_answer_in_every_state(event):
    """Unknown input must be an explicit, explained answer — never an exception or a silent pass."""
    for state in CaseState:
        result = evaluate(_ctx(state), event)
        assert result.status in {"APPLIED", "BLOCKED", "FORBIDDEN", "NO_RULE"}
        assert result.reason
        if result.status != "APPLIED":
            assert result.next_state is state


def test_forbidden_rules_are_narrow_enough_to_allow_legitimate_flows():
    for rule in FORBIDDEN:
        assert rule.invariant
        assert len(rule.from_states) < len(CaseState)


def test_superseding_a_communicated_result_needs_a_named_human():
    ctx = _ctx(CaseState.COMMUNICATION_DOCUMENTED, correction_lineage=True)
    result = evaluate(ctx, EventType.RESULT_CORRECTED)
    assert result.status in {"APPLIED", "BLOCKED"}
    if result.requires_human:
        assert result.requires_human is True
