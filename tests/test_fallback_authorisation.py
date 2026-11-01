"""Audit finding H-1: a prohibition must never be read as permission.

The original implementation asked whether a clause contained "alternative" / "other channel" /
"fallback" together with "shall". That predicate is true of a prohibition. Authorisation is now a
declared field on the excerpt, and the gate demands the basis token that only that field produces.
These tests are the acceptance test the review asked for.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.kb import retriever
from app.kb.ingest import _declared_flag
from app.orchestration.engine import Orchestrator, build_runtime, load_scenario
from app.state_machine.transitions import MachineContext

REPO = Path(__file__).resolve().parents[1]
PROHIBITION = (
    " Under no circumstances shall an alternative channel or other channel be used to report a "
    "critical result; no fallback is permitted."
)


def _run_with_injected(text_suffix: str, *, declare: bool = False):
    """Run S3a against a corpus where one chunk has been poisoned, in a temp copy of the index."""
    src = REPO / "kb" / "index" / "chunks.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    for chunk in data["chunks"]:
        if chunk["chunk_id"] == "S1-11.1.1":
            chunk["text"] = chunk["text"] + text_suffix
            chunk["chunk_id"] = "S1-INJECTED"
            chunk["authorises_fallback"] = declare
    tmp = Path(tempfile.mkdtemp()) / "chunks.json"
    tmp.write_text(json.dumps(data), encoding="utf-8")

    original = retriever.INDEX_PATH
    retriever.INDEX_PATH = tmp
    # This test injects a poisoned corpus on purpose. The runtime now refuses to serve an index that
    # does not match the committed pin, so the experiment declares itself unverified explicitly -
    # exactly the escape hatch an adversarial experiment should have to use.
    os.environ["RESULTRELAY_ALLOW_UNVERIFIED_KB"] = "1"
    retriever.reload_index()
    try:
        scenario = load_scenario("S3a-channel-outage-no-evidence")
        runtime = build_runtime(scenario, "resultrelay", "INJ")
        orchestrator = Orchestrator(runtime)
        for step in scenario["steps"]:
            orchestrator.step(step)
        policy = [
            a for st in runtime.steps for a in st["agents"] if a["agent_id"] == "policy_applicability"
        ][-1]
        return runtime, policy
    finally:
        retriever.INDEX_PATH = original
        os.environ.pop("RESULTRELAY_ALLOW_UNVERIFIED_KB", None)
        retriever.reload_index()


def test_a_prohibition_is_not_read_as_an_authorisation():
    runtime, policy = _run_with_injected(PROHIBITION)
    assert policy["data"]["fallback_authorised"] is False
    assert policy["data"]["fallback_evidence_refs"] == []
    assert [a.channel for a in runtime.network.attempts] == ["SMS-PATIENT"]
    assert runtime.state.value == "ESCALATION_REQUIRED"


def test_the_positive_control_still_authorises_when_the_clause_declares_it():
    """Same sentence, but the excerpt declares authorisation — the control is not simply 'never'."""
    runtime, policy = _run_with_injected(PROHIBITION, declare=True)
    assert policy["data"]["fallback_authorised"] is True
    assert policy["data"]["fallback_authorisation_basis"] == "DECLARED_EXCERPT_FIELD"


@pytest.mark.parametrize("value", ["true", 1, "yes"])
def test_a_non_boolean_declaration_is_refused(value):
    with pytest.raises(ValueError, match="must be a boolean"):
        _declared_flag({"authorises_fallback": value}, field="authorises_fallback", chunk_id="X-1")


@pytest.mark.parametrize("classification", ["OFFICIAL_GUIDANCE", "GLOBAL_COMPARATOR", "PRODUCT_DESIGN_CONTROL"])
def test_guidance_and_comparators_cannot_authorise_an_action(classification):
    with pytest.raises(ValueError, match="cannot authorise an action"):
        _declared_flag(
            {"authorises_fallback": True, "claim_classification": classification},
            field="authorises_fallback",
            chunk_id="X-2",
        )


def test_the_gate_refuses_a_boolean_without_the_declared_basis():
    """An agent that sets the flag without the corpus basis cannot move the machine."""
    ctx = MachineContext(
        case_id="T-FB",
        state=None,  # type: ignore[arg-type]  # not read by fallback_authorised
        current_revision_id="R1",
        profile={},
        evidence={"fallback_authorised": True, "fallback_evidence_refs": ["S1 11.1.1"]},
    )
    ok, why = ctx.fallback_authorised()
    assert ok is False
    assert "no verified policy evidence or approved institutional procedure" in why


def test_the_gate_accepts_a_boolean_with_the_declared_basis():
    ctx = MachineContext(
        case_id="T-FB2",
        state=None,  # type: ignore[arg-type]
        current_revision_id="R1",
        profile={},
        evidence={
            "fallback_authorised": True,
            "fallback_evidence_refs": ["S1 11.1.1"],
            "fallback_authorisation_basis": "DECLARED_EXCERPT_FIELD",
        },
    )
    ok, why = ctx.fallback_authorised()
    assert ok is True
    assert "declares it" in why
