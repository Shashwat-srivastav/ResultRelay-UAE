"""The model client, exercised without a model.

No endpoint is contacted in these tests. A fake transport stands in for an OpenAI-compatible server,
which is how the containment contract (advisers.guard) gets tested with real model-shaped output —
including the outputs a model actually produces when it is wrong.
"""

from __future__ import annotations

import json

import pytest

from app.advisers import advise
from app.advisers.base import AdvisoryStatus
from app.advisers.llm import OpenAICompatibleAdviser, RefusingTransport, _first_json_object
from app.models.schemas import RecommendedAction


class FakeTransport:
    def __init__(self, content: str, *, raises: Exception | None = None):
        self.content = content
        self.raises = raises
        self.calls: list[dict] = []

    def post(self, url, payload, headers):
        self.calls.append({"url": url, "payload": payload})
        if self.raises:
            raise self.raises
        return {"choices": [{"message": {"content": self.content}}]}


def _adviser(content: str, *, raises=None):
    transport = FakeTransport(content, raises=raises)
    return OpenAICompatibleAdviser(base_url="http://localhost:11434/v1", model="local", transport=transport), transport


def _body(action: str, cites: list[str], *, rationale="ok", confidence=0.6) -> str:
    return json.dumps({
        "candidate_action": action,
        "rationale": rationale,
        "citation_chunk_ids": cites,
        "confidence": confidence,
    })


def test_an_offshore_endpoint_is_refused_before_any_data_is_shaped():
    with pytest.raises(PermissionError, match="Article 13"):
        OpenAICompatibleAdviser(base_url="https://api.openai.com/v1", model="gpt")


def test_a_local_endpoint_is_accepted_and_sends_a_structured_prompt():
    adviser, transport = _adviser(_body("AWAIT_EVIDENCE", ["S1-11.1.1"]))
    proposal = adviser.propose(jurisdiction="AE-DU", situation="send", evidence=[
        {"chunk_id": "S1-11.1.1", "text": "critical results shall be reported clearly", "jurisdiction": "AE-DU"}
    ])
    assert proposal.candidate_action is RecommendedAction.AWAIT_EVIDENCE
    assert proposal.is_model_generated is True
    sent = transport.calls[0]["payload"]
    assert sent["temperature"] == 0
    assert "AWAIT_EVIDENCE" in sent["messages"][0]["content"]


def test_a_model_that_wraps_json_in_prose_is_still_parsed():
    adviser, _ = _adviser('Sure! Here is my answer:\n```json\n' + _body("SEND_PRIMARY", []) + '\n```')
    assert adviser.propose(jurisdiction="AE-DU", situation="", evidence=[]).candidate_action is RecommendedAction.SEND_PRIMARY


@pytest.mark.parametrize("content", ["no json here", '{"candidate_action": "SEND_PRIMARY"', '{"candidate_action": "FLY"}'])
def test_malformed_or_out_of_set_output_never_becomes_an_action(content):
    adviser, _ = _adviser(content)
    with pytest.raises((ValueError, KeyError)):
        adviser.propose(jurisdiction="AE-DU", situation="", evidence=[])


def test_a_provider_failure_is_recorded_as_no_advice_not_as_authority():
    adviser, _ = _adviser("", raises=RuntimeError("connection refused"))
    record = advise(jurisdiction="AE-DU", situation="send", evidence=[], adviser=adviser,
                    enabled=True, endpoint="http://localhost:11434/v1")
    assert record.status is AdvisoryStatus.REJECTED_MALFORMED
    assert record.proposal is None
    assert "not authority to act" in record.reason


def test_a_valid_model_proposal_is_recorded_as_advisory_only():
    adviser, _ = _adviser(_body("SEND_PRIMARY", ["S1-11.1.1"]))
    record = advise(jurisdiction="AE-DU", situation="send", evidence=[], adviser=adviser,
                    enabled=True, endpoint="http://localhost:11434/v1")
    assert record.status is AdvisoryStatus.ADVISORY_ONLY
    assert record.as_dict()["classification"] == "PRODUCT_DESIGN_CONTROL"


def test_a_model_citing_a_foreign_clause_is_rejected_by_the_guard_not_by_trust():
    adviser, _ = _adviser(_body("SEND_PRIMARY", ["AD1-PP.11.2.d"]))
    record = advise(jurisdiction="AE-DU", situation="send", evidence=[], adviser=adviser,
                    enabled=True, endpoint="http://localhost:11434/v1")
    assert record.status is AdvisoryStatus.REJECTED_OUT_OF_JURISDICTION


def test_the_default_transport_refuses_to_contact_anything():
    adviser = OpenAICompatibleAdviser(base_url="http://localhost:11434/v1", model="local")
    assert isinstance(adviser.transport, RefusingTransport)
    with pytest.raises(RuntimeError, match="does not contact a model endpoint"):
        adviser.propose(jurisdiction="AE-DU", situation="", evidence=[])


def test_json_extraction_happens_outside_any_judgement():
    assert json.loads(_first_json_object('prefix {"a": {"b": 1}} suffix')) == {"a": {"b": 1}}


# --------------------------------------------------------------------------- switches agree
def test_the_documented_switch_actually_enables_the_boundary(monkeypatch):
    """RESULTRELAY_ADVISE is what the README tells an operator to set.

    It used to be read by the engine while the guard and /api/health read
    RESULTRELAY_ENABLE_LLM, so the documented switch opened a path the health endpoint still
    reported as closed. One switch, or the report is fiction.
    """
    import importlib

    from app.core import config as config_module

    monkeypatch.delenv("RESULTRELAY_ENABLE_LLM", raising=False)
    monkeypatch.setenv("RESULTRELAY_ADVISE", "1")
    importlib.reload(config_module)
    try:
        assert config_module.settings.enable_llm is True
    finally:
        monkeypatch.delenv("RESULTRELAY_ADVISE", raising=False)
        importlib.reload(config_module)


def test_the_legacy_switch_still_works_and_default_is_closed(monkeypatch):
    import importlib

    from app.core import config as config_module

    monkeypatch.delenv("RESULTRELAY_ADVISE", raising=False)
    monkeypatch.delenv("RESULTRELAY_ENABLE_LLM", raising=False)
    importlib.reload(config_module)
    assert config_module.settings.enable_llm is False

    monkeypatch.setenv("RESULTRELAY_ENABLE_LLM", "1")
    importlib.reload(config_module)
    try:
        assert config_module.settings.enable_llm is True
    finally:
        monkeypatch.delenv("RESULTRELAY_ENABLE_LLM", raising=False)
        importlib.reload(config_module)


def test_health_distinguishes_enabled_from_connected(monkeypatch):
    import dataclasses

    from app.api import routes

    # settings is a frozen dataclass; swap the object rather than mutate it.
    monkeypatch.setattr(routes, "settings", dataclasses.replace(routes.settings, enable_llm=False))
    monkeypatch.delenv("RESULTRELAY_ADVISE_URL", raising=False)
    assert routes._advisory_status() == "closed"

    monkeypatch.setattr(routes, "settings", dataclasses.replace(routes.settings, enable_llm=True))
    assert "no adviser endpoint" in routes._advisory_status()

    monkeypatch.setenv("RESULTRELAY_ADVISE_URL", "http://localhost:11434/v1")
    assert routes._advisory_status() == "open (advisory only)"
