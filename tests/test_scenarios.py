"""Scenario-level properties.

These are the tests that would fail if someone "fixed" a scenario to make the system look good,
or made the engine pass by special-casing a scenario id.
"""

from __future__ import annotations

import json

import pytest

from app.kb import ingest
from app.kb.retriever import all_chunks
from app.orchestration.engine import load_scenario


def test_scenario_event_order(scenario_ids):
    """Steps are contiguous from 1 and simulated time never runs backwards."""
    for sid in scenario_ids:
        scenario = load_scenario(sid)
        steps = scenario["steps"]
        assert [s["step"] for s in steps] == list(range(1, len(steps) + 1)), sid
        minutes = [float(s.get("at_minutes", 0)) for s in steps]
        assert minutes == sorted(minutes), f"{sid} has an event that travels back in time"
        for s in steps:
            assert s.get("type"), f"{sid} step {s['step']} has no event type"
            assert s.get("actor"), f"{sid} step {s['step']} has no actor"


def test_every_scenario_declares_its_own_case_and_scope(scenario_ids):
    seen = set()
    for sid in scenario_ids:
        s = load_scenario(sid)
        assert s.get("case_id"), sid
        assert s["case_id"] not in seen, f"{sid} reuses case_id {s['case_id']}"
        seen.add(s["case_id"])
        assert s.get("case_scope") in {"WALK_IN", "GENETIC", "OTHER"}
        assert s.get("jurisdiction") == "AE-DU"


def test_expected_actions_are_authored_separately(expected_actions, scenario_ids):
    """The expected outcome set is data written before running the engine, not a by-product of it.

    It was written by the same people who wrote the engine, and each file says so: an expectation set
    cannot claim independent authorship it does not have (critic finding RT-10)."""
    assert set(expected_actions) == set(scenario_ids)
    for sid, spec in expected_actions.items():
        assert spec["safe_final_states"], sid
        assert spec.get("must_hold"), sid
        assert spec.get("authorship") == "ENGINE_AUTHORS", sid
        assert spec.get("independent_review") is False, sid
        assert "authored_independently" not in spec, sid
        assert spec.get("reviewer_note"), sid


def test_jurisdiction_isolation(run):
    """S6: an Abu Dhabi clause may inform the reasoning but may never be cited as binding."""
    rt = run("S6-jurisdiction-conflict", "resultrelay")
    binding = [
        src
        for step in rt.steps
        for agent in step["agents"]
        for src in agent["applicable_sources"]
        if src["claim_type"] == "BINDING_REQUIREMENT"
    ]
    assert binding, "the case should still be grounded in a Dubai or federal clause"
    # The property is the jurisdiction of the cited clause, not a fixed source list: a Dubai case
    # may be cited from Dubai policy and from federal law, and from nothing else.
    cited = {src["source_id"] for src in binding}
    assert "AD1" not in cited
    jurisdiction = {
        row["source_id"]: row["jurisdiction"] for row in ingest.load_register().values()
    }
    assert all(jurisdiction[sid] in {"AE-DU", "AE-FED"} for sid in cited), cited


def test_a_retrieval_only_configuration_cites_the_foreign_rule(run):
    """The comparison that gives the isolation test meaning."""
    rt = run("S6-jurisdiction-conflict", "retrieval_only")
    binding = [
        src
        for step in rt.steps
        for agent in step["agents"]
        for src in agent["applicable_sources"]
        if src["claim_type"] == "BINDING_REQUIREMENT"
    ]
    assert any(src["source_id"] == "AD1" for src in binding), (
        "without the applicability filter the foreign clause should be presented as binding"
    )


def test_correction_requires_approval(run):
    """S2: a corrected result supersedes a communicated one, so a named human must approve it."""
    rt = run("S2-correction-after-acknowledgment", "resultrelay")
    assert rt.state.value in {"CORRECTED_RESULT_ACKNOWLEDGED", "COMMUNICATION_DOCUMENTED"}

    corrected_sends = [
        t for t in rt.transitions
        if t["trigger_event"] == "transmission.requested" and "CORRECTED" in t["resulting_state"]
    ]
    assert corrected_sends, "the scenario should exercise a corrected-result transmission"
    assert rt.approvals, "a superseding communication must record who approved it"
    for approval in rt.approvals.values():
        assert approval.get("by"), "an approval without a named approver is not an approval"


def test_without_approval_the_corrected_send_does_not_happen(run):
    """Run the same scenario, strip the approval event, and confirm the gate holds the send."""
    from app.orchestration.engine import Orchestrator, build_runtime

    scenario = load_scenario("S2-correction-after-acknowledgment")
    steps = [s for s in scenario["steps"] if "approv" not in json.dumps(s.get("payload", {})).lower()
             and "approv" not in str(s.get("type", "")).lower()]
    assert len(steps) < len(scenario["steps"]), "the scenario should contain an approval event to remove"

    rt = build_runtime(scenario, "resultrelay", run_id="TEST-NO-APPROVAL")
    orch = Orchestrator(rt)
    for spec in steps:
        orch.step(spec)

    corrected_attempts = [a for a in rt.network.attempts if "R2" in a.result_revision_id]
    assert not corrected_attempts, "a correction was transmitted without the required approval"
    assert rt.state.value not in {"CORRECTED_RESULT_ACKNOWLEDGED"}


def test_information_asymmetry(run):
    """No agent may hold the full picture; each is given a declared subset."""
    rt = run("S1-ambiguous-delivery", "resultrelay")
    for step in rt.steps:
        for agent in step["agents"]:
            assert agent["context_scope"], f"{agent['agent_id']} declared no context scope"
            assert len(agent["context_scope"]) < 12, (
                f"{agent['agent_id']} appears to receive the whole case"
            )
        # The set of scopes in a step must not all be identical.
        scopes = [tuple(a["context_scope"]) for a in step["agents"]]
        assert len(set(scopes)) > 1


@pytest.mark.parametrize("config", ["resultrelay", "policy_blind", "retrieval_only", "static_rules"])
def test_every_scenario_runs_under_every_configuration(run, scenario_ids, config):
    for sid in scenario_ids:
        rt = run(sid, config)
        assert rt.state is not None
        assert rt.audit is not None
        ok, broken = rt.audit.verify_chain()
        assert ok, f"{sid}/{config} produced a broken audit chain at {broken}"


def test_no_engine_path_keys_off_a_scenario_id():
    """Behaviour must not be branch-coded on the scenario name.

    A quick static check: the engine module must not contain any scenario identifier literal.
    """
    from pathlib import Path

    engine_src = Path(__file__).resolve().parents[1] / "app" / "orchestration" / "engine.py"
    text = engine_src.read_text(encoding="utf-8")
    for marker in ("S1-ambiguous", "S2-correction", "S3a-", "S3b-", "S4-genetic", "S5-late", "S6-jurisdiction"):
        assert marker not in text, f"engine.py contains a scenario-specific literal: {marker}"


def test_cases_end_in_a_state_the_expected_actions_allow(run, expected_actions):
    for sid, spec in expected_actions.items():
        rt = run(sid, "resultrelay")
        assert rt.state.value in spec["safe_final_states"], (
            f"{sid} ended in {rt.state.value}, expected one of {spec['safe_final_states']}"
        )
