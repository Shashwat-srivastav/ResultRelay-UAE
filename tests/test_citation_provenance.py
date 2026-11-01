"""H-1 and H-6: citations must come from retrieval, and a missing basis must block the workflow.

H-1  The policy agent appended "(S1 13.4)" to its reason text whatever the retriever returned, and
     the lab agent carried a literal citation for 9.1.5(g) with a hard-coded score of 0.0. Deleting
     the clause from the corpus left both citations in the trace: a human reviewer was shown an
     authority the system had not retrieved.
H-6  `blocking_conditions` was always empty and `requires_human_review` merely echoed the status, so
     a case with no policy basis could still finish without anyone being asked. Worse, the assessor's
     ESCALATE_HUMAN proposal had no transition from RESULT_FINALIZED, so the gate refused it and the
     case sat finalised with zero escalations.

Every assertion here is about what the *record* says, not about the engine's intentions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.kb import retriever
from app.orchestration.engine import load_scenario, run_scenario
from app.state_machine.states import CaseState
from app.state_machine.transitions import EventType, MachineContext, evaluate
from app.policies.profile import load_profile

INDEX = Path(__file__).resolve().parents[1] / "kb" / "index" / "chunks.json"
SCENARIOS = [
    "S1-ambiguous-delivery",
    "S2-correction-after-acknowledgment",
    "S3b-channel-outage-approved-procedure",
    "S4-genetic-scope-exclusion",
    "S7-genetic-physician-route",
]


@pytest.fixture()
def corpus_without_genetic_or_correction(monkeypatch, tmp_path):
    """A corpus that no longer contains the genetic-routing or correction clauses."""
    payload = json.loads(INDEX.read_text(encoding="utf-8"))
    kept = [
        c for c in payload["chunks"]
        if not (c["source_id"] == "S1" and set(c.get("topics") or []) & {"genetic", "correction"})
    ]
    assert len(kept) < len(payload["chunks"]), "the fixture must actually remove chunks"
    path = tmp_path / "chunks.json"
    path.write_text(json.dumps({"chunks": kept, **{k: v for k, v in payload.items() if k != "chunks"}}))
    monkeypatch.setattr(retriever, "INDEX_PATH", path)
    # The pinned hash no longer matches by construction; the point of this test is what the agents
    # do with a corpus that lacks the clause, not whether the corpus verifies.
    monkeypatch.setenv("RESULTRELAY_ALLOW_UNVERIFIED_KB", "1")
    retriever.reload_index()
    yield kept
    retriever.reload_index()


def _citations(runtime) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for step in runtime.steps:
        for agent in step.get("agents", []):
            for src in agent.get("applicable_sources", []):
                out.append((src["source_id"], src["section"]))
    return out


def test_a_deleted_clause_is_not_cited(corpus_without_genetic_or_correction):
    runtime = run_scenario(load_scenario("S4-genetic-scope-exclusion"), "resultrelay")
    cited = _citations(runtime)
    assert not [c for c in cited if c[1].startswith("13.")], cited
    assert "13.4" not in json.dumps(runtime.steps)


def test_a_missing_genetic_clause_records_a_blocking_condition(corpus_without_genetic_or_correction):
    runtime = run_scenario(load_scenario("S4-genetic-scope-exclusion"), "resultrelay")
    assert runtime.blocking_conditions, "a genetic case with no routing clause must record a block"
    assert any("unsourced" in c for c in runtime.blocking_conditions)
    policy = next(
        a for step in runtime.steps for a in step.get("agents", [])
        if a["agent_id"] == "policy_applicability"
    )
    assert policy["requires_human_review"] is True


def test_the_case_cannot_quietly_finish_when_the_route_is_unsourced(corpus_without_genetic_or_correction):
    runtime = run_scenario(load_scenario("S4-genetic-scope-exclusion"), "resultrelay")
    # Escalation is now reachable from a finalised result; before the fix the assessor's proposal was
    # refused by the gate and the case stayed finalised with no human asked.
    assert runtime.state in {CaseState.ESCALATION_REQUIRED, CaseState.ESCALATION_IN_REVIEW}, runtime.state
    assert runtime.escalations, "a blocked case must open an escalation for a named role"


def test_a_deleted_correction_clause_is_not_cited(corpus_without_genetic_or_correction):
    runtime = run_scenario(load_scenario("S2-correction-after-acknowledgment"), "resultrelay")
    cited = _citations(runtime)
    assert not [c for c in cited if c[1].startswith("9.1.5(g)")], cited
    assert any("correction duty is unsourced" in u for step in runtime.steps
               for a in step.get("agents", []) for u in a.get("conditions_unresolved", []))


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_every_citation_in_a_full_run_exists_in_the_served_corpus(scenario_id):
    known = {(c["source_id"], c["section_id"]) for c in retriever.all_chunks()}
    runtime = run_scenario(load_scenario(scenario_id), "resultrelay")
    unknown = [c for c in _citations(runtime) if c not in known]
    assert not unknown, f"citations with no chunk behind them: {unknown}"


def test_escalation_is_reachable_from_a_finalised_result():
    ctx = MachineContext(
        case_id="T-ESC",
        state=CaseState.RESULT_FINALIZED,
        current_revision_id="R1",
        profile=load_profile(None),
        evidence={},
    )
    transition = evaluate(ctx, EventType.ESCALATION_REQUESTED)
    assert transition.status == "APPLIED", transition.reason
    assert transition.next_state is CaseState.ESCALATION_REQUIRED
