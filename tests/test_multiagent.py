"""Multi-agent council: providers, deterministic assurance, feedback loop and the deterministic orchestrator."""

from __future__ import annotations

import os

import pytest

from app.multiagent.council import (
    Council, assure, detect_conflicts, fact_check, orchestrate, transport_unresolved,
)
from app.multiagent.providers import Provider, ProviderError, configured, load_dotenv, validate

Q = {
    "status": {"type": "choice", "criteria": {"A": "a", "B": "b"}},
    "p": {"type": "noul", "criteria": {"true": "t", "false": "f"}},
}


# --- providers -------------------------------------------------------------------------------------

def test_a_chat_model_answer_outside_the_named_options_is_rejected_not_repaired():
    ok, bad = validate({"status": {"choice": "C"}, "p": {"noul": 0.3}}, Q)
    assert bad == ["status"] and ok["p"]["noul"] == 0.3


def test_a_probability_outside_zero_one_is_rejected():
    _, bad = validate({"status": {"choice": "A"}, "p": {"noul": 1.7}}, Q)
    assert bad == ["p"]


def test_an_offshore_provider_is_refused_for_a_real_case_before_any_request(monkeypatch):
    p = Provider("mistral", "https://api.mistral.ai/v1", "mistral-small-latest", "MISTRAL_API_KEY")
    monkeypatch.setattr(p, "_ask_live", lambda *a: pytest.fail("a request was made for a real case"))
    with pytest.raises(PermissionError):
        p.ask({"case": {}}, Q, data_class="HEALTH")


def test_replay_refuses_an_unrecorded_case_view():
    with pytest.raises(ProviderError):
        Provider("replay", "", "recorded").ask({"case": {"never": "seen"}}, Q, data_class="SYNTHETIC")


@pytest.mark.parametrize("kind,url", [("ollama", "http://localhost:11434/v1"), ("mistral", "https://api.mistral.ai/v1")])
def test_providers_are_configured_from_the_environment(monkeypatch, kind, url):
    monkeypatch.setenv("RESULTRELAY_AGENT_PROVIDER", kind)
    monkeypatch.delenv("RESULTRELAY_AGENT_URL", raising=False)
    p = configured()
    assert p.kind == kind and p.url == url


def test_the_reviewer_can_run_on_a_different_model_family(monkeypatch):
    from app.multiagent.council import configured_council

    monkeypatch.setenv("RESULTRELAY_AGENT_PROVIDER", "mistral")
    monkeypatch.setenv("RESULTRELAY_AGENT_MODEL", "ministral-14b-2512")
    monkeypatch.setenv("RESULTRELAY_REVIEWER_PROVIDER", "jev")
    monkeypatch.delenv("RESULTRELAY_REVIEWER_MODEL", raising=False)
    c = configured_council()
    assert c.providers["analyst"].label == "mistral:ministral-14b-2512"
    assert c.providers["institution"].label == "mistral:ministral-14b-2512"
    assert c.providers["reviewer"].label == "jev:jev-latest"


def test_dotenv_drops_inline_comments_and_keeps_quoted_values(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('A_KEY=abc123          # a comment\nB_KEY="x # not a comment"\nC_KEY=\n', encoding="utf-8")
    for k in ("A_KEY", "B_KEY", "C_KEY"):
        monkeypatch.delenv(k, raising=False)
    load_dotenv(f)
    assert os.environ["A_KEY"] == "abc123" and os.environ["B_KEY"] == "x # not a comment" and "C_KEY" not in os.environ


# --- deterministic assurance -------------------------------------------------------------------------

CASE = {"current_result_revision": "R1", "case_scope": "WALK_IN", "recipient_route": "PATIENT",
        "attempts": [{"revision": "R1", "provider_accepted": True, "delivery_receipt": False, "outcome": "ACCEPTED", "failed": False}],
        "acknowledgments": [], "recent_events": []}


def test_the_fact_check_catches_a_communicated_claim_nobody_acknowledged():
    """The hallucination observed live (S8): 'communicated' with no acknowledgment."""
    issues = fact_check("analyst", {"obligation": {"choice": "COMMUNICATED"}}, CASE, "ESCALATE_HUMAN")
    assert issues and "no one acknowledged" in issues[0]


def test_a_correct_claim_passes_the_fact_check():
    assert fact_check("analyst", {"obligation": {"choice": "AWAITING_ACK"}}, CASE, "AWAIT_EVIDENCE") == []


def test_the_policy_rules_check_refuses_a_comparator_as_the_governing_clause():
    msg = {"answers": {"obligation": {"choice": "AWAITING_ACK"}, "clause": {"choice": "G5-8-clinical-team-only"}},
           "_chunks": [{"chunk_id": "G5-8-clinical-team-only", "jurisdiction": "GLOBAL", "claim_classification": "GLOBAL_COMPARATOR"}]}
    issues = assure("analyst", msg, CASE, "AWAIT_EVIDENCE", "AE-DU")
    assert any("cannot govern" in i for i in issues)


def test_a_reviewer_objection_that_does_not_fit_the_facts_is_rejected_by_code():
    issues = fact_check("reviewer", {"objection": {"choice": "SCOPE_ROUTES_ELSEWHERE"}, "alternative": {"choice": "ESCALATE_HUMAN"}},
                        CASE, "SEND_PRIMARY")
    assert issues and "does not fit" in issues[0]


def test_the_institutional_analyst_is_invoked_only_when_transport_is_unresolved():
    assert transport_unresolved(CASE) is True
    delivered = {**CASE, "attempts": [{**CASE["attempts"][0], "delivery_receipt": True}]}
    assert transport_unresolved(delivered) is False
    assert transport_unresolved({**CASE, "attempts": []}) is False


def test_the_physician_route_is_not_a_scope_conflict():
    msgs = {"analyst": {"status": "ANSWERED", "answers": {"obligation": {"choice": "DIRECT_NOT_PERMITTED"}}}}
    assert not any(c.startswith("SCOPE_CONFLICT") for c in
                   detect_conflicts(msgs, {}, {**CASE, "case_scope": "GENETIC", "recipient_route": "PHYSICIAN"}, "SEND_PRIMARY"))
    assert any(c.startswith("SCOPE_CONFLICT") for c in
               detect_conflicts(msgs, {}, {**CASE, "case_scope": "GENETIC", "recipient_route": "PATIENT"}, "SEND_PRIMARY"))


# --- the deterministic orchestrator ---------------------------------------------------------------

def _reviewer(kind, conf=0.9):
    return {"reviewer": {"status": "ANSWERED", "answers": {"objection": {"choice": kind, "confidence": conf}}}}


def test_a_verified_objection_escalates_and_a_rejected_one_does_not():
    assert orchestrate(_reviewer("ACCEPTANCE_AS_DELIVERY"), {"reviewer": {"outcome": "ACCEPTED"}}, [], "AWAIT_ACKNOWLEDGMENT")[0] == "ESCALATE"
    assert orchestrate(_reviewer("ACCEPTANCE_AS_DELIVERY"), {"reviewer": {"outcome": "OBJECTION_REJECTED"}}, [], "AWAIT_ACKNOWLEDGMENT")[0] == "PROCEED"


def test_a_free_text_objection_needs_more_confidence_because_code_cannot_verify_it():
    ok = {"reviewer": {"outcome": "ACCEPTED"}}
    assert orchestrate(_reviewer("TEXT_CONTRADICTS_RECORD", 0.6), ok, [], "RECORD_DOCUMENTATION")[0] == "PROCEED"
    assert orchestrate(_reviewer("TEXT_CONTRADICTS_RECORD", 0.8), ok, [], "RECORD_DOCUMENTATION")[0] == "ESCALATE"


def test_gaps_and_differing_readings_are_recorded_not_escalated():
    ok = {"reviewer": {"outcome": "ACCEPTED"}}
    assert orchestrate(_reviewer("NONE"), ok, ["UNSETTLED_HIGH_RISK: x"], "RECORD_DOCUMENTATION")[0] == "PROCEED"
    assert orchestrate(_reviewer("NONE"), ok, ["UNSETTLED_HIGH_RISK: x", "READINGS_DIFFER: a vs b"], "RECORD_DOCUMENTATION")[0] == "PROCEED"


# --- feedback loop, end to end with a scripted provider ----------------------------------------------

class _Scripted:
    """Analyst hallucinates 'communicated' once, then corrects itself when shown the findings."""

    label = "scripted"

    def __init__(self, stubborn=False):
        self.stubborn = stubborn

    def ask(self, state, questions, *, data_class):
        if "obligation" in questions:
            choice = "COMMUNICATED" if (self.stubborn or not state.get("assurance_findings")) else "AWAITING_ACK"
            return {"obligation": {"choice": choice, "confidence": 0.8}, "clause": {"choice": "NONE", "confidence": 0.5},
                    "settled": {"noul": 0.8}, "gap": {"choice": "NONE", "confidence": 0.6}}, []
        if "telecom_covers" in questions:
            return {"telecom_covers": {"noul": 0.2}, "clause": {"choice": "NONE", "confidence": 0.5}}, []
        out = {"objection": {"choice": "NONE", "confidence": 0.8}, "own_reading": {"choice": "AWAITING_ACK", "confidence": 0.7},
               "alternative": {"choice": "ESCALATE_HUMAN", "confidence": 0.5}}
        for k in questions:
            if k.endswith("_supported"):
                out[k] = {"noul": 0.9}
            elif k.endswith("_issue"):
                out[k] = {"choice": "NONE", "confidence": 0.9}
        return out, []


def _rt():
    return type("RT", (), {"case_id": "SYN-1", "patient_ref": "SYN-P", "contact_ref": "SYN-C", "jurisdiction": "AE-DU"})()


def test_a_hallucinating_analyst_is_corrected_through_the_feedback_loop(monkeypatch):
    council = Council(_Scripted())
    monkeypatch.setattr(council, "_search", lambda *a, **k: [])
    d = council.deliberate(_rt(), {}, "AWAIT_EVIDENCE", CASE)
    assert d["reviews"]["analyst"]["outcome"] == "CORRECTED"
    assert d["messages"]["analyst"]["answers"]["obligation"]["choice"] == "AWAITING_ACK"
    assert "institution" in d["messages"]                     # transport unresolved -> TDRA lens invoked
    assert any(c.startswith("TELECOM_GAP") for c in d["conflicts"])
    assert d["decision"] == "PROCEED"


def test_an_analyst_that_keeps_contradicting_the_record_on_a_high_risk_step_is_disputed_and_escalated(monkeypatch):
    council = Council(_Scripted(stubborn=True))
    monkeypatch.setattr(council, "_search", lambda *a, **k: [])
    d = council.deliberate(_rt(), {}, "RECORD_DOCUMENTATION", CASE)
    assert d["messages"]["analyst"]["status"] == "DISPUTED"
    assert d["decision"] == "ESCALATE"
