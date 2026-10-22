"""API-level tests.

The API is where a reviewer meets the system, so these tests check the claims the UI makes:
that the timeline keeps event layers apart, that the audit chain is re-verified on read, and that
nothing is served from frontend state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _start(client, scenario="S1-ambiguous-delivery", config="resultrelay"):
    res = client.post("/api/runs", json={"scenario_id": scenario, "configuration": config})
    assert res.status_code == 200, res.text
    return res.json()


def test_health_reports_the_synthetic_boundary(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["synthetic_data_only"] is True
    assert body["real_network_access"] is False
    assert body["real_ehr_integration"] is False
    assert "not a clinical service" in body["disclaimer"].lower()
    assert body["knowledge_base"]["verification"]["verified"] > 0


def test_openapi_is_exposed(client):
    assert client.get("/api/openapi.json").status_code == 200


def test_unknown_configuration_is_rejected(client):
    res = client.post("/api/runs", json={"scenario_id": "S1-ambiguous-delivery", "configuration": "wishful"})
    assert res.status_code == 400


def test_unknown_scenario_is_404(client):
    res = client.post("/api/runs", json={"scenario_id": "S99-does-not-exist", "configuration": "resultrelay"})
    assert res.status_code == 404


def test_a_run_can_be_stepped_and_reaches_a_terminal_state(client):
    started = _start(client)
    run_id = started["run"]["run_id"]
    assert started["events_remaining"] > 0

    for _ in range(started["events_remaining"]):
        res = client.post(f"/api/runs/{run_id}/step")
        assert res.status_code == 200
    final = res.json()
    assert final["done"] is True
    assert final["run"]["state"] in {"COMMUNICATION_DOCUMENTED", "CORRECTED_RESULT_ACKNOWLEDGED",
                                     "ESCALATION_REQUIRED", "RESULT_FINALIZED"}
    assert final["run"]["audit_chain_valid"] is True


def test_case_timeline_separates_event_layers(client):
    """A transport observation, a clinical fact and a human act must not share a layer."""
    started = _start(client)
    run_id = started["run"]["run_id"]
    client.post(f"/api/runs/{run_id}/play")
    case_id = started["run"]["case_id"]

    detail = client.get(f"/api/cases/{case_id}").json()
    events = detail["events"]
    assert events

    layers = {e["source_layer"] for e in events}
    assert len(layers) >= 3, f"expected several distinct layers, saw {layers}"
    for layer in ("WORKFLOW", "CLINICAL", "TRANSPORT", "HUMAN"):
        assert layer in layers, f"missing {layer} layer"

    # Delivery evidence lives in the transport layer, acknowledgment in the human layer.
    transport = [e for e in events if e["source_layer"] == "TRANSPORT"]
    human = [e for e in events if e["source_layer"] == "HUMAN"]
    assert any("receipt" in e["kind"] or "deliver" in e["kind"] for e in transport)
    assert any("acknowledg" in e["kind"] for e in human)
    assert not any("acknowledg" in e["kind"] for e in transport)


def test_case_detail_exposes_transitions_and_citations(client):
    started = _start(client)
    run_id = started["run"]["run_id"]
    client.post(f"/api/runs/{run_id}/play")
    detail = client.get(f"/api/cases/{started['run']['case_id']}").json()

    assert detail["transitions"]
    assert all(t["status"] in {"APPLIED", "BLOCKED", "FORBIDDEN", "NO_RULE"} for t in detail["transitions"])
    assert detail["citations"]
    assert all(c["page"] >= 1 for c in detail["citations"])
    assert detail["revisions"]


def test_audit_chain_is_verified_after_being_read_back(client):
    started = _start(client)
    run_id = started["run"]["run_id"]
    client.post(f"/api/runs/{run_id}/play")
    body = client.get(f"/api/cases/{started['run']['case_id']}/audit").json()

    assert body["count"] > 0
    assert body["chain_valid"] is True
    assert body["broken_sequences"] == []
    assert "recomputed" in body["verification"].lower()


def test_bundle_export_contains_what_a_reviewer_needs(client):
    started = _start(client)
    run_id = started["run"]["run_id"]
    client.post(f"/api/runs/{run_id}/play")
    bundle = client.get(f"/api/cases/{started['run']['case_id']}/bundle").json()

    assert bundle["synthetic"] is True
    assert bundle["audit_chain_valid"] is True
    assert bundle["case"]["events"]
    for key in ("case", "audit_log", "knowledge_base"):
        assert key in bundle
    json.dumps(bundle)  # must be serialisable


def test_dashboard_counters_are_aggregates_over_stored_cases(client):
    started = _start(client)
    client.post(f"/api/runs/{started['run']['run_id']}/play")

    dash = client.get("/api/dashboard").json()
    cases = client.get("/api/cases").json()
    assert dash["counters"]["active_cases"] == len(cases["cases"])
    assert "aggregates" in dash["note"].lower()


def test_kb_endpoints_only_return_verified_excerpts(client):
    sources = client.get("/api/kb/sources").json()
    assert sources["count"] >= 8
    assert sources["manifest"]["verification"]["unverified"] == 0

    search = client.get("/api/kb/search", params={"q": "critical result", "jurisdiction": "AE-DU"}).json()
    assert search["chunks"]
    for chunk in search["chunks"]:
        assert chunk["excerpt_status"] == "VERIFIED_AGAINST_SOURCE"
        assert chunk["page_start"] >= 1


def test_kb_search_reports_what_the_filter_removed(client):
    body = client.get("/api/kb/search", params={"q": "critical result", "jurisdiction": "AE-DU", "scope": "applicable"}).json()
    assert all(c["jurisdiction"] == "AE-DU" for c in body["chunks"])
    assert body["excluded_by_filter"] > 0


def test_state_machine_metadata_is_published(client):
    body = client.get("/api/meta/state-machine").json()
    assert len(body["states"]) >= 15
    assert len(body["transitions"]) >= 20
    assert "resultrelay" in body["configurations"]
    assert body["configurations"]["resultrelay"]["use_kb"] is True


def test_gap_register_and_mappings_are_served(client):
    gaps = client.get("/api/gaps").json()
    assert gaps["count"] >= 10
    assert gaps["facets"]["classification"]

    for name in ("y3172", "readiness"):
        mapping = client.get(f"/api/mappings/{name}").json()
        assert mapping["count"] >= 9
    assert client.get("/api/mappings/nonsense").status_code == 404


def test_missing_case_is_404(client):
    assert client.get("/api/cases/NOPE").status_code == 404


# --------------------------------------------------------------------------- store reconciliation
def test_the_store_reconciles_against_its_audit_chain(client):
    """H-3: the runtime is in memory, so the store must be checkable against something durable."""
    started = _start(client)
    run_id = started["run"]["run_id"]
    case_id = started["run"]["case_id"]
    client.post(f"/api/runs/{run_id}/play")

    body = client.get(f"/api/cases/{case_id}/integrity").json()
    assert body["chain_valid"] is True
    assert body["reconciled"] is True, body["findings"]
    assert body["store_state"] == body["replayed_state"]
    assert body["transition_count"] >= 1
    assert body["audit_entry_count"] >= 1


def test_divergence_between_store_and_replay_is_reported_not_repaired(client):
    """Point the replayed state away from the stored state and the endpoint must say so."""
    from sqlalchemy import select

    from app.models.db import CaseRow, session

    started = _start(client)
    run_id = started["run"]["run_id"]
    case_id = started["run"]["case_id"]
    client.post(f"/api/runs/{run_id}/play")

    s = session()
    try:
        case = s.get(CaseRow, case_id)
        assert case is not None
        original = case.current_state
        case.current_state = "COMMUNICATION_DOCUMENTED" if original != "COMMUNICATION_DOCUMENTED" else "RESULT_DRAFT"
        s.commit()
    finally:
        s.close()

    body = client.get(f"/api/cases/{case_id}/integrity").json()
    assert body["reconciled"] is False
    assert any("replaying the persisted transitions yields" in f for f in body["findings"])

    # put the row back so the failure does not leak into other tests through the shared database
    s = session()
    try:
        case = s.get(CaseRow, case_id)
        assert case is not None
        case.current_state = original
        s.commit()
    finally:
        s.close()


def test_self_hosted_fonts_are_served_as_fonts(client):
    """The SPA catch-all used to answer /fonts/* with index.html, so every font silently fell back.

    A font that 200s as text/html is worse than a 404: nothing logs, nothing breaks, and the whole
    typographic system is quietly replaced by DejaVu.
    """
    STATIC = Path(__file__).resolve().parents[1] / "app" / "static" / "app"
    if not (STATIC / "fonts").exists():
        pytest.skip("frontend not built: no static fonts to serve")
    for name in ("inter-var-latin.woff2", "jetbrains-mono-var-latin.woff2"):
        r = client.get(f"/fonts/{name}")
        assert r.status_code == 200, name
        assert r.headers["content-type"] in {"font/woff2", "application/font-woff2", "application/octet-stream"}, (
            f"{name} served as {r.headers['content-type']}"
        )
        assert r.content[:4] == b"wOF2", f"{name} is not a woff2 payload"
