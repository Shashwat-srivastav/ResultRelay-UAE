"""Provider-agnostic multi-agent council: validation, cross-check, residency, replay."""

from __future__ import annotations

import pytest

from app.multiagent.council import rule_conflicts
from app.multiagent.providers import Provider, ProviderError, configured, validate

Q = {
    "status": {"type": "choice", "criteria": {"A": "a", "B": "b"}},
    "p": {"type": "noul", "criteria": {"true": "t", "false": "f"}},
}


def test_a_chat_model_answer_outside_the_named_options_is_rejected_not_repaired():
    ok, bad = validate({"status": {"choice": "C"}, "p": {"noul": 0.3}}, Q)
    assert bad == ["status"] and ok["p"]["noul"] == 0.3


def test_a_probability_outside_zero_one_is_rejected():
    _, bad = validate({"status": {"choice": "A"}, "p": {"noul": 1.7}}, Q)
    assert bad == ["p"]


def _msg(net=None, health=None, obj=None):
    m = {}
    if net:
        m["network"] = {"answers": {"delivery_status": {"choice": net}}}
    if health:
        m["health"] = {"answers": {"obligation": {"choice": health}}}
    if obj is not None:
        m["reviewer"] = {"answers": {"objection": {"noul": obj}}}
    return m


@pytest.mark.parametrize("msgs,action,expected", [
    (_msg("DELIVERED_RECEIPT", "AWAITING_ACK", 0.1), "AWAIT_ACKNOWLEDGMENT", ["DELIVERY_WITHOUT_COMMUNICATION"]),
    (_msg("ACCEPTED_ONLY", "COMMUNICATED", 0.1), "RECORD_DOCUMENTATION", ["COMMUNICATION_WITHOUT_NETWORK_RECORD"]),
    (_msg("NOT_SENT", "DIRECT_NOT_PERMITTED", 0.1), "SEND_PRIMARY", ["SCOPE_CONFLICT"]),
    (_msg("NOT_SENT", "NOT_YET_SENT", 0.8), "SEND_PRIMARY", ["REVIEWER_OBJECTS"]),
    (_msg("NOT_SENT", "NOT_YET_SENT", 0.1), "SEND_PRIMARY", []),
])
def test_the_rule_cross_check_names_conflicts_between_mandates(msgs, action, expected):
    assert rule_conflicts(msgs, action) == expected


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


# --- critic layer -------------------------------------------------------------------------------

from app.multiagent.council import Council, fact_check  # noqa: E402

CASE = {"current_result_revision": "R1", "case_scope": "WALK_IN",
        "attempts": [{"revision": "R1", "provider_accepted": True, "delivery_receipt": False, "outcome": "ACCEPTED", "failed": False}],
        "acknowledgments": []}


def test_the_fact_check_catches_a_communicated_claim_nobody_acknowledged():
    """The hallucination observed live on S8 step 4."""
    issues = fact_check("health", {"obligation": {"choice": "COMMUNICATED"}}, CASE, "ESCALATE_HUMAN")
    assert issues and "no one acknowledged" in issues[0]


def test_the_fact_check_catches_a_receipt_that_does_not_exist():
    assert fact_check("network", {"delivery_status": {"choice": "DELIVERED_RECEIPT"}}, CASE, "AWAIT_EVIDENCE")


def test_a_correct_answer_passes_the_fact_check():
    assert fact_check("network", {"delivery_status": {"choice": "ACCEPTED_ONLY"}}, CASE, "AWAIT_EVIDENCE") == []


class _Scripted:
    """A provider that hallucinates once, then corrects itself when shown the critique."""

    label = "scripted"

    def ask(self, state, questions, *, data_class):
        if "obligation" in questions:
            choice = "AWAITING_ACK" if state.get("critic_feedback") else "COMMUNICATED"
            return {"obligation": {"choice": choice, "confidence": 0.8}, "clause": {"choice": "NONE", "confidence": 0.5}}, []
        if "delivery_status" in questions:
            return {"delivery_status": {"choice": "ACCEPTED_ONLY", "confidence": 0.9}, "clause": {"choice": "NONE", "confidence": 0.5}}, []
        if "objection" in questions:
            return {"objection": {"noul": 0.2}, "alternative": {"choice": "AWAIT_EVIDENCE", "confidence": 0.5},
                    "clause": {"choice": "NONE", "confidence": 0.5}}, []
        if any(k.endswith("_supported") for k in questions):
            return {k: ({"noul": 0.9} if k.endswith("_supported") else {"choice": "NONE", "confidence": 0.9}) for k in questions}, []
        return {"resolution": {"choice": "PROCEED", "confidence": 0.7}, "conflict": {"choice": "NONE", "confidence": 0.7}}, []


def test_a_hallucinating_agent_is_corrected_through_the_feedback_loop(monkeypatch):
    council = Council(_Scripted())
    monkeypatch.setattr(council, "_search", lambda *a, **k: [])
    rt = type("RT", (), {"case_id": "SYN-1", "patient_ref": "SYN-P", "contact_ref": "SYN-C", "jurisdiction": "AE-DU"})()
    d = council.deliberate(rt, {}, "AWAIT_EVIDENCE", CASE)
    assert d["reviews"]["health"]["outcome"] == "CORRECTED"
    assert d["messages"]["health"]["answers"]["obligation"]["choice"] == "AWAITING_ACK"
    assert d["critique_summary"]["corrected"] == 1 and not d["critique_summary"]["disputed"]


def test_an_agent_that_keeps_contradicting_the_record_is_disputed_and_escalated(monkeypatch):
    class Stubborn(_Scripted):
        def ask(self, state, questions, *, data_class):
            if "obligation" in questions:
                return {"obligation": {"choice": "COMMUNICATED", "confidence": 0.9}, "clause": {"choice": "NONE", "confidence": 0.5}}, []
            return super().ask(state, questions, data_class=data_class)

    council = Council(Stubborn())
    monkeypatch.setattr(council, "_search", lambda *a, **k: [])
    rt = type("RT", (), {"case_id": "SYN-1", "patient_ref": "SYN-P", "contact_ref": "SYN-C", "jurisdiction": "AE-DU"})()
    d = council.deliberate(rt, {}, "AWAIT_EVIDENCE", CASE)
    assert d["messages"]["health"]["status"] == "DISPUTED"
    assert d["critique_summary"]["disputed"] == ["health"]
    assert d["escalate"] is True


def test_dotenv_drops_inline_comments_and_keeps_quoted_values(tmp_path, monkeypatch):
    from app.multiagent.providers import load_dotenv

    f = tmp_path / ".env"
    f.write_text('A_KEY=abc123          # a comment\nB_KEY="x # not a comment"\nC_KEY=\n', encoding="utf-8")
    for k in ("A_KEY", "B_KEY", "C_KEY"):
        monkeypatch.delenv(k, raising=False)
    load_dotenv(f)
    import os
    assert os.environ["A_KEY"] == "abc123" and os.environ["B_KEY"] == "x # not a comment" and "C_KEY" not in os.environ


def test_a_role_can_run_on_a_different_model_family(monkeypatch):
    from app.multiagent.council import configured_council

    monkeypatch.setenv("RESULTRELAY_AGENT_PROVIDER", "mistral")
    monkeypatch.setenv("RESULTRELAY_AGENT_MODEL", "ministral-14b-2512")
    monkeypatch.setenv("RESULTRELAY_CRITIC_PROVIDER", "jev")
    monkeypatch.delenv("RESULTRELAY_CRITIC_MODEL", raising=False)
    c = configured_council()
    assert c.providers["network"].label == "mistral:ministral-14b-2512"
    assert c.providers["critic"].label == "jev:jev-latest"
    assert c.providers["coordinator"].label == "mistral:ministral-14b-2512"
