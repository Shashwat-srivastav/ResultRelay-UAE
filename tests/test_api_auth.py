"""H-7 / M-6: the API had no way to refuse a request.

The shipped default is still open, because the reviewer runs it on loopback and the README says so.
What changed is that closing it is now a switch rather than a rewrite, and /api/health reports which
state the running process is in.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import runs
from app.core.config import settings
from app.main import app

KEY = "test-key-do-not-use"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RESULTRELAY_API_KEY", KEY)
    runs.clear()
    return TestClient(app)


@pytest.fixture()
def open_client(monkeypatch):
    monkeypatch.delenv("RESULTRELAY_API_KEY", raising=False)
    runs.clear()
    return TestClient(app)


def test_a_protected_endpoint_refuses_an_anonymous_request(client):
    response = client.get("/api/cases")
    assert response.status_code == 401
    assert "X-API-Key" in response.text


def test_the_key_admits_the_request_and_the_key_is_not_echoed(client):
    response = client.get("/api/cases", headers={"X-API-Key": KEY})
    assert response.status_code == 200, response.text
    assert KEY not in response.text


def test_a_wrong_key_is_refused(client):
    assert client.get("/api/cases", headers={"X-API-Key": KEY + "x"}).status_code == 401


def test_health_stays_reachable_and_says_auth_is_on(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["authentication_enabled"] is True
    assert KEY not in response.text


def test_health_carries_no_case_data(client):
    client.post("/api/runs", json={"scenario_id": "S1-critical-result-unknown-delivery"},
                headers={"X-API-Key": KEY})
    body = client.get("/api/health").text
    for leaked in ("case_id", "patient_ref", "SMS-PATIENT"):
        assert leaked not in body


def test_without_a_key_the_api_behaves_as_documented(open_client):
    assert open_client.get("/api/cases").status_code == 200
    assert open_client.get("/api/health").json()["authentication_enabled"] is False
    assert settings.authentication_enabled is False
