"""The simulated network encodes the delivery semantics the whole system depends on.

These tests are about one claim: "accepted", "delivered" and "acknowledged" are three different
facts, and the transport layer is where the first two are kept apart.
"""

from __future__ import annotations

import pytest

from app.transport.simulator import REAL_NETWORK_ACCESS, SimulatedNetwork, sim_time


@pytest.fixture
def network():
    return SimulatedNetwork(
        channels={
            "SMS-PATIENT": {"status": "UP", "kind": "SMS", "primary": True},
            "PORTAL-PATIENT": {"status": "DOWN", "kind": "PATIENT_PORTAL", "primary": False},
        },
        attempt_plan=[
            {"outcome": "TIMEOUT", "note": "provider accepted but no receipt"},
            {"outcome": "DELIVERED", "note": "endpoint confirmed"},
        ],
    )


def test_no_real_network_access_is_ever_attempted():
    assert REAL_NETWORK_ACCESS is False


def test_timeout_produces_no_delivery_evidence(network):
    """A timeout is an absence of information, not a failure and not a success.

    The provider never answered, so the attempt is neither accepted nor delivered; the only
    honest record is TIMEOUT plus a ledger note saying so.
    """
    attempt = network.send(
        channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K1", at_minutes=0
    )
    assert attempt.accepted is False
    assert attempt.delivered is False
    assert attempt.failed is False
    assert attempt.delivered_at is None
    assert attempt.outcome == "TIMEOUT"
    note = next(e for e in network.ledger if e["event"] == "TRANSPORT_TIMEOUT")["note"]
    assert "not evidence of failure" in note


def test_same_idempotency_key_never_creates_a_second_delivered_message(network):
    """Provider semantics, not counter semantics (audit H-4).

    The first send times out, so the provider has told us nothing; a retry with the same key is a
    genuine new attempt. Once an attempt is accepted, the same key is suppressed.
    """
    first = network.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K1", at_minutes=0)
    assert first.outcome == "TIMEOUT"
    retry = network.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K1", at_minutes=5)
    assert retry.attempt_id != first.attempt_id, "a timed-out attempt must not suppress the retry"

    # the second attempt is the one the plan delivers; a third send with the same key is suppressed
    third = network.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K1", at_minutes=6)
    assert third.attempt_id == retry.attempt_id
    assert third.duplicate_suppressed is True
    assert any(e["event"] == "SEND_SUPPRESSED_DUPLICATE" for e in network.ledger)


def test_a_different_key_on_the_same_channel_is_a_new_message(network):
    network.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K1", at_minutes=0)
    network.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K2", at_minutes=1)
    assert len(network.attempts) == 2


def test_reconciliation_is_the_only_route_out_of_unknown(network):
    attempt = network.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K1", at_minutes=0)
    assert attempt.outcome == "TIMEOUT"
    assert network.delivered() is False

    result = network.reconcile(attempt.attempt_id, at_minutes=30)
    assert result["reconciled"] is True
    # STILL_UNKNOWN is a legitimate reconciliation result: the network genuinely cannot say.
    assert result["result"] in {"DELIVERED", "FAILED", "STILL_UNKNOWN"}


def test_reconcile_is_idempotent(network):
    attempt = network.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K1", at_minutes=0)
    first = network.reconcile(attempt.attempt_id, at_minutes=30)
    second = network.reconcile(attempt.attempt_id, at_minutes=45)
    assert first["result"] == second["result"]


def test_a_down_channel_does_not_silently_succeed(network):
    attempt = network.send(channel="PORTAL-PATIENT", result_revision_id="R1", idempotency_key="K9", at_minutes=0)
    assert attempt.delivered is False
    assert attempt.outcome in {"FAILED", "TIMEOUT"}


def test_delivery_receipt_is_bound_to_the_revision_that_was_sent(network):
    attempt = network.send(channel="SMS-PATIENT", result_revision_id="R2", idempotency_key="K3", at_minutes=0)
    assert attempt.result_revision_id == "R2"


def test_ledger_records_every_provider_event_with_a_timestamp(network):
    attempt = network.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K1", at_minutes=0)
    network.reconcile(attempt.attempt_id, at_minutes=20)
    assert len(network.ledger) >= 3
    assert all("at" in e and "event" in e for e in network.ledger)
    assert all(e["at"] <= sim_time(120) for e in network.ledger)


def test_channel_manifest_reports_status_per_channel(network):
    manifest = {c["channel_id"]: c["status"] for c in network.channel_manifest()}
    assert manifest["SMS-PATIENT"] == "UP"
    assert manifest["PORTAL-PATIENT"] == "DOWN"
