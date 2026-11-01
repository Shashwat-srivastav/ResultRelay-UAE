"""Audit finding H-4: the idempotency key has to mean something.

The key used to include an attempt counter, so it was unique by construction and the transport's
duplicate suppression could never fire. The key now identifies the message; a retry reuses it.
"""

from __future__ import annotations

from app.transport.simulator import SimulatedNetwork


def _network() -> SimulatedNetwork:
    return SimulatedNetwork(
        channels={"SMS-PATIENT": {"status": "UP", "primary": True}, "PORTAL-PATIENT": {"status": "UP"}},
        attempt_plan=[{"outcome": "ACCEPTED", "deliver_after_minutes": 1}],
    )


def test_the_same_message_is_never_sent_twice():
    net = _network()
    first = net.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K",
                     at_minutes=0, content_digest="d")
    second = net.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K",
                      at_minutes=5, content_digest="d")
    assert len(net.attempts) == 1
    assert first.attempt_id == second.attempt_id
    assert net.attempts[0].duplicate_suppressed is True
    assert any(row["event"] == "SEND_SUPPRESSED_DUPLICATE" for row in net.ledger)


def test_a_retry_after_a_provider_timeout_is_a_new_attempt():
    net = _network()
    net.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K2",
             at_minutes=0, content_digest="d")
    net.attempts[0].outcome = "TIMEOUT"          # provider told us nothing
    again = net.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="K2",
                     at_minutes=6, content_digest="d")
    assert len(net.attempts) == 2
    assert again.attempt_id != net.attempts[0].attempt_id


def test_a_corrected_revision_is_a_different_message():
    net = _network()
    net.send(channel="SMS-PATIENT", result_revision_id="R1", idempotency_key="C:R1:SMS-PATIENT:RESULT_NOTIFICATION",
             at_minutes=0, content_digest="d")
    net.send(channel="SMS-PATIENT", result_revision_id="R2", idempotency_key="C:R2:SMS-PATIENT:CORRECTED_RESULT",
             at_minutes=30, content_digest="d2")
    assert len(net.attempts) == 2
