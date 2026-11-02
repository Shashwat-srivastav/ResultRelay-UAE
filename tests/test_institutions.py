"""Institutional agents (DHA, TDRA) and their deterministic coordinator."""

from __future__ import annotations

from types import SimpleNamespace

from app.advisers import institutions
from app.advisers.institutions import coordinate


def _dha(p_comm: float, p_ai: float = 0.9) -> dict:
    return {"communication_established": p_comm, "ai_use_conforms": p_ai, "governing_clause": "S1-11.1.3"}


def _tdra(p_del: float) -> dict:
    return {"network_delivery_evidenced": p_del, "governing_clause": "U8-1-23-delivery-definition"}


def test_a_delivery_receipt_without_communication_is_flagged_as_a_conflict_between_mandates():
    conflicts, agrees = coordinate(_dha(0.1), _tdra(0.95), "DELIVERY_CONFIRMED")
    assert [c["type"] for c in conflicts] == ["DELIVERY_WITHOUT_COMMUNICATION"]
    assert agrees is True  # the gate did not claim communication either


def test_a_physician_phone_route_is_flagged_as_outside_the_telecom_record():
    conflicts, _ = coordinate(_dha(0.9), _tdra(0.05), "COMMUNICATION_DOCUMENTED")
    assert [c["type"] for c in conflicts] == ["COMMUNICATION_WITHOUT_NETWORK_RECORD"]


def test_the_coordinator_reports_disagreement_with_the_gate_rather_than_overriding_it():
    _, agrees = coordinate(_dha(0.2), _tdra(0.9), "COMMUNICATION_DOCUMENTED")
    assert agrees is False


def test_doubt_about_ai_use_is_surfaced():
    conflicts, _ = coordinate(_dha(0.9, p_ai=0.2), _tdra(0.9), "COMMUNICATION_DOCUMENTED")
    assert "AI_USE_QUESTIONED" in [c["type"] for c in conflicts]


def test_a_real_case_is_refused_before_any_request_leaves_the_state(monkeypatch):
    def boom(*a, **k):  # pragma: no cover - must never be reached
        raise AssertionError("a request was attempted for a real case")

    monkeypatch.setattr(institutions, "_ask", boom)
    rt = SimpleNamespace(case_id="CASE-REAL-1", patient_ref="P-1", contact_ref="C-1")
    review = institutions.review(rt)
    assert review.status == "REFUSED_RESIDENCY"
    assert "Art. 13" in review.residency or "Article 13" in review.residency
