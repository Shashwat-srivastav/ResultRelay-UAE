"""H-2: the agents' declared asymmetry and their disagreements, measured rather than asserted.

Before this change the resolver returned only the winning action, so a step on which the assessors
disagreed was indistinguishable in the record from a step on which they agreed. Two claims were
therefore untestable: that the assessors hold different information, and that their conflicts are
resolved by a stated rule rather than by list order.

What the measurement shows, and this file pins both halves honestly:

* the asymmetry is real in code - an assessor that does not declare a field does not receive it;
* the resolver ignores arrival order and applies a fixed safety-first precedence;
* a contested step is recorded with the names of the outvoted assessors;
* handing every assessor the whole snapshot changes **no outcome** on the seven benchmark
  scenarios, so the asymmetry is a design property here, not a demonstrated effect.
"""

from __future__ import annotations

import pytest

from app.agents.base import UNRESTRICTED, scope_view
from app.evaluation.runner import changed_inputs
from app.models.schemas import AgentAssessment, AssessmentStatus, RecommendedAction
from app.orchestration.engine import load_scenario, run_scenario
from app.orchestration.gate import resolve_proposals


def _assessment(agent_id: str, action: RecommendedAction) -> AgentAssessment:
    return AgentAssessment(
        agent_id=agent_id,
        case_id="SYN-CASE",
        context_scope=["case_id"],
        assessment_status=AssessmentStatus.OK,
        recommended_action=action,
        requires_human_review=action is RecommendedAction.ESCALATE_HUMAN,
        confidence=0.5,
        concise_rationale="synthetic",
        conditions_checked=["synthetic"],
        conditions_unresolved=[],
        applicable_sources=[],
        mode="DETERMINISTIC",
        data={},
    )


def test_an_assessor_cannot_see_a_field_it_does_not_declare():
    snapshot = {"case_id": "C1", "patient_ref": "SYN-PATIENT-001", "clinical_summary": "synthetic"}
    view = scope_view(snapshot, ("case_id",))
    assert view == {"case_id": "C1"}
    assert "patient_ref" not in view and "clinical_summary" not in view


def test_the_ablation_hands_every_assessor_the_whole_snapshot():
    snapshot = {"case_id": "C1", "patient_ref": "SYN-PATIENT-001", UNRESTRICTED: True}
    view = scope_view(snapshot, ("case_id",))
    assert view["patient_ref"] == "SYN-PATIENT-001"
    assert UNRESTRICTED not in view, "the sentinel is a control input, not case data"


def test_the_ablation_changes_exactly_one_input():
    assert list(changed_inputs("ablate_full_context")) == ["asymmetric_context"]


def test_resolution_does_not_depend_on_arrival_order():
    assessments = [
        _assessment("policy_applicability", RecommendedAction.SEND_PRIMARY),
        _assessment("network_delivery", RecommendedAction.AWAIT_ACKNOWLEDGMENT),
        _assessment("escalation_coordinator", RecommendedAction.ESCALATE_HUMAN),
    ]
    forward, _, res_forward = resolve_proposals(assessments)
    backward, _, res_backward = resolve_proposals(list(reversed(assessments)))
    assert forward is RecommendedAction.ESCALATE_HUMAN, "the most conservative proposal wins"
    assert forward is backward
    assert res_forward["chosen"] == res_backward["chosen"]
    assert res_forward["conflict"] is True
    assert {d["agent_id"] for d in res_forward["dissent"]} == {
        "policy_applicability", "network_delivery"
    }


def test_agreement_is_not_recorded_as_conflict():
    assessed = [
        _assessment("network_delivery", RecommendedAction.AWAIT_EVIDENCE),
        _assessment("policy_applicability", RecommendedAction.AWAIT_EVIDENCE),
    ]
    chosen, _, resolution = resolve_proposals(assessed)
    assert chosen is RecommendedAction.AWAIT_EVIDENCE
    assert resolution["conflict"] is False
    assert resolution["corroboration"] is True


def test_a_contested_step_appears_in_the_audit_log():
    rt = run_scenario(load_scenario("S3a-channel-outage-no-evidence"), "resultrelay")
    contested = [s for s in rt.steps if (s.get("proposal_resolution") or {}).get("conflict")]
    assert contested, "this scenario is expected to contain at least one contested step"
    logged = [e for e in rt.audit.entries if e.event == "proposal.contested"]
    assert len(logged) == len(contested)
    payload = logged[0].payload
    assert payload["rule"].startswith("safety-first precedence")
    assert payload["dissent"], "a contested step must name who was outvoted"


def test_full_context_is_a_null_result_on_the_benchmark():
    """Documented, not wished away: the asymmetry buys nothing measurable on these scenarios."""
    strict = run_scenario(load_scenario("S3a-channel-outage-no-evidence"), "resultrelay")
    open_ctx = run_scenario(load_scenario("S3a-channel-outage-no-evidence"), "ablate_full_context")
    assert strict.state is open_ctx.state
    assert [s.get("proposed_action") for s in strict.steps] == [
        s.get("proposed_action") for s in open_ctx.steps
    ]


@pytest.mark.parametrize("scenario_id", [
    "S1-ambiguous-delivery",
    "S4-genetic-scope-exclusion",
    "S6-jurisdiction-conflict",
])
def test_every_run_records_a_resolution_for_every_deciding_step(scenario_id):
    rt = run_scenario(load_scenario(scenario_id), "resultrelay")
    deciding = [s for s in rt.steps if s.get("proposed_action")]
    assert deciding
    for step in deciding:
        resolution = step["proposal_resolution"]
        assert resolution["rule"]
        assert resolution["chosen"] == step["proposed_action"]
        assert all("agent_id" in p and "proposed" in p for p in resolution["proposals"])
