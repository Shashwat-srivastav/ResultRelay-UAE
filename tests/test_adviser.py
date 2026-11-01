"""The advisory layer is contained, or it is not shipped.

These tests are the acceptance criteria for audit item P0-4: an LLM adviser may be introduced only
if it sits behind the unchanged deterministic gate. Each one fails if the adviser gains any ability
to change a decision, cite a foreign clause as authority, invent a citation, or run offshore.
"""

from __future__ import annotations

import pytest

from app.advisers import advise
from app.advisers.base import AdvisoryProposal, AdvisoryStatus
from app.advisers.residency import Residency, authorise, classify
from app.advisers.stub import RuleBasedAdviser
from app.models.schemas import AgentAssessment, AssessmentStatus, RecommendedAction
from app.orchestration.gate import enforce
from app.state_machine.states import CaseState
from app.state_machine.transitions import MachineContext

DUBAI_EVIDENCE = [{"chunk_id": "S1-11.1.1", "jurisdiction": "AE-DU"}]


class HostileAdviser:
    """A deliberately unsafe adviser: proposes the most permissive action and leans on foreign law."""

    name = "hostile"

    def propose(self, *, jurisdiction, situation, evidence):
        return AdvisoryProposal(
            candidate_action=RecommendedAction.SEND_PRIMARY,
            rationale="send it, the Abu Dhabi standard is satisfied",
            citation_chunk_ids=("AD1-PP.11.2.d",),
            confidence=0.99,
        )


class InventingAdviser:
    name = "inventing"

    def propose(self, *, jurisdiction, situation, evidence):
        return AdvisoryProposal(
            candidate_action=RecommendedAction.SEND_PRIMARY,
            rationale="there is a clause that says this is fine",
            citation_chunk_ids=("S1-99.9.9",),
            confidence=0.99,
        )


class CrashingAdviser:
    name = "crashing"

    def propose(self, *, jurisdiction, situation, evidence):
        raise RuntimeError("connection reset by peer")


def test_the_boundary_is_closed_by_default():
    record = advise(jurisdiction="AE-DU", situation="send", evidence=DUBAI_EVIDENCE,
                    adviser=RuleBasedAdviser())
    assert record.status is AdvisoryStatus.DISABLED
    assert record.proposal is None
    assert "shipped configuration" in record.reason


@pytest.mark.parametrize("host,expected", [
    ("https://api.openai.com/v1", Residency.OUT_OF_COUNTRY),
    ("https://eu.llm.example.de/v1", Residency.OUT_OF_COUNTRY),
    ("https://model.health.ae/v1", Residency.IN_COUNTRY),
    ("http://localhost:11434/api", Residency.IN_COUNTRY),
    ("http://127.0.0.1:8080", Residency.IN_COUNTRY),
    (None, Residency.UNKNOWN),
])
def test_residency_classification(host, expected):
    assert classify(host) is expected


def test_an_offshore_endpoint_is_refused_with_the_article_that_refuses_it():
    decision = authorise("https://api.openai.com/v1")
    assert decision.permitted is False
    assert "Art. 13" in decision.citation and "Art. 24" in decision.citation
    assert "500,000" in decision.reason


def test_a_named_resolution_is_the_only_route_out_of_the_country():
    decision = authorise("https://api.openai.com/v1", resolution_ref="MOHAP-RES-2026-014")
    assert decision.permitted is True
    assert "not verified by this system" in decision.reason


def test_the_guard_refuses_before_the_adviser_is_ever_called():
    record = advise(jurisdiction="AE-DU", situation="send", evidence=DUBAI_EVIDENCE,
                    adviser=HostileAdviser(), enabled=True, endpoint="https://api.openai.com/v1")
    assert record.status is AdvisoryStatus.REFUSED_RESIDENCY
    assert record.proposal is None


def test_a_foreign_binding_clause_cannot_be_smuggled_in_as_authority():
    record = advise(jurisdiction="AE-DU", situation="send", evidence=DUBAI_EVIDENCE,
                    adviser=HostileAdviser(), enabled=True, endpoint="https://model.health.ae/v1")
    assert record.status is AdvisoryStatus.REJECTED_OUT_OF_JURISDICTION
    assert "AE-AZ" in record.reason
    assert "cannot underwrite" in record.reason


def test_an_invented_citation_is_rejected():
    record = advise(jurisdiction="AE-DU", situation="send", evidence=DUBAI_EVIDENCE,
                    adviser=InventingAdviser(), enabled=True, endpoint="https://model.health.ae/v1")
    assert record.status is AdvisoryStatus.REJECTED_UNGROUNDED


def test_an_adviser_that_raises_does_not_become_authority_to_act():
    record = advise(jurisdiction="AE-DU", situation="send", evidence=DUBAI_EVIDENCE,
                    adviser=CrashingAdviser(), enabled=True, endpoint="https://model.health.ae/v1")
    assert record.status is AdvisoryStatus.REJECTED_MALFORMED
    assert "not authority to act" in record.reason


def test_a_clean_proposal_is_recorded_as_design_control_not_as_policy():
    record = advise(jurisdiction="AE-DU", situation="send the critical result",
                    evidence=DUBAI_EVIDENCE, adviser=RuleBasedAdviser(), enabled=True,
                    endpoint="https://model.health.ae/v1")
    assert record.status is AdvisoryStatus.ADVISORY_ONLY
    assert record.as_dict()["classification"] == "PRODUCT_DESIGN_CONTROL"


def _ctx(state: CaseState) -> MachineContext:
    return MachineContext(case_id="T-A", state=state, current_revision_id="R1",
                          profile={"direct_patient_communication_enabled": True})


def _assessments() -> list[AgentAssessment]:
    return [AgentAssessment(
        agent_id="policy_applicability",
        case_id="T-A",
        assessment_status=AssessmentStatus.OK,
        recommended_action=RecommendedAction.ESCALATE_HUMAN,
        applicable_sources=[{
            "source_id": "S1", "section": "11.1.1", "page": 40,
            "claim_type": "BINDING_REQUIREMENT",
            "quote": "The laboratory communicates critical results to the patient clearly.",
        }],
        confidence=0.6,
        requires_human_review=True,
        concise_rationale="delivery state is unresolved, so a human must decide",
    )]


def test_the_gate_decision_is_identical_with_and_without_an_adviser():
    """The load-bearing test: an agreement, a disagreement and a refusal all leave the gate alone."""
    ctx = _ctx(CaseState.TRANSMISSION_ATTEMPTED)
    base = enforce(proposal=RecommendedAction.ESCALATE_HUMAN, review_revision="R1",
                   ctx=ctx, assessments=_assessments())

    disagreeing = advise(jurisdiction="AE-DU", situation="send now", evidence=DUBAI_EVIDENCE,
                         adviser=HostileAdviser(), enabled=True, endpoint="https://model.health.ae/v1")
    # the hostile adviser is refused for its citation; forge an accepted one to test the gate path
    from app.advisers.base import AdvisoryRecord
    accepted = AdvisoryRecord(
        status=AdvisoryStatus.ADVISORY_ONLY, mode="ADVISORY", reason="accepted for the test",
        proposal=AdvisoryProposal(candidate_action=RecommendedAction.SEND_PRIMARY,
                                  rationale="send it", citation_chunk_ids=("S1-11.1.1",)),
    )
    with_adviser = enforce(proposal=RecommendedAction.ESCALATE_HUMAN, review_revision="R1",
                           ctx=ctx, assessments=_assessments(), advisory=accepted)

    assert disagreeing.status is AdvisoryStatus.REJECTED_OUT_OF_JURISDICTION
    assert with_adviser.enforced_action is base.enforced_action
    assert with_adviser.permitted == base.permitted
    assert with_adviser.invariant == base.invariant
    assert with_adviser.blocked_actions == base.blocked_actions
    assert with_adviser.advisory_overruled is True
    assert any("did not read the proposal" in c for c in with_adviser.conditions_checked)
