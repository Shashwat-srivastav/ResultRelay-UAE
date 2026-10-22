"""A simulated, deterministic asynchronous delivery network.

Design constraints that mirror the real failure modes we are testing:

* A send produces at most one provider event per attempt. Timeouts produce *no* delivery
  evidence, which is why the caller must be able to represent "unknown".
* The provider's acceptance of a message is recorded separately from the endpoint receipt.
* Every send carries an idempotency key. Re-sending with the same key never creates a second
  message; it returns the original attempt (``duplicate_suppressed=True``).
* Reconciliation is the only way to turn an unknown outcome into evidence.
* Nothing here contacts a real network. ``REAL_NETWORK_ACCESS = False`` is asserted in the
  API health payload so a reviewer can confirm the boundary without reading this file.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

REAL_NETWORK_ACCESS = False

BASE_TIME = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)


def sim_time(minutes: float) -> str:
    return (BASE_TIME + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


class ChannelState(str):
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


@dataclass
class TransportAttempt:
    attempt_id: str
    idempotency_key: str
    channel: str
    result_revision_id: str
    created_at: str
    #: Who the message was addressed to. The transport does not care; the record does, because
    #: "the patient was informed" and "the physician was informed" are different claims.
    recipient: str | None = None
    accepted: bool = False
    accepted_at: str | None = None
    delivered: bool = False
    delivered_at: str | None = None
    delivered_at_minutes: float | None = None
    #: Set only when a delivery *receipt event* has been applied for this attempt. The simulator's
    #: own delivery plan is the adapter's knowledge; a receipt is the provider telling the case.
    #: Conflating the two is what made the duplicate-receipt guard depend on a caller-supplied flag.
    receipt_recorded: bool = False
    failed: bool = False
    failure_reason: str | None = None
    outcome: str = "PENDING"  # PENDING | ACCEPTED | DELIVERED | FAILED | TIMEOUT | UNKNOWN
    reconciled: bool = False
    reconciliation_result: str | None = None
    duplicate_suppressed: bool = False
    provider_ref: str | None = None


@dataclass
class SimulatedNetwork:
    """Scripted network. Behaviour comes from the scenario file, so runs are reproducible."""

    channels: dict[str, dict[str, Any]] = field(default_factory=dict)
    attempt_plan: list[dict[str, Any]] = field(default_factory=list)
    reconciliation_plan: list[dict[str, Any]] = field(default_factory=list)
    attempts: list[TransportAttempt] = field(default_factory=list)
    ledger: list[dict[str, Any]] = field(default_factory=list)
    #: Guard the idempotency check and the attempt append. The step endpoint already serialises
    #: per run, so this is defence in depth: the invariant belongs to the transport, and a transport
    #: that can create two attempts for one key under concurrency is wrong on its own terms
    #: (red-team finding C-1).
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    # -- channel state ----------------------------------------------------
    def channel_status(self, channel_id: str) -> str:
        return str(self.channels.get(channel_id, {}).get("status", "UNKNOWN"))

    def primary_channel(self) -> str:
        for cid, spec in self.channels.items():
            if spec.get("primary"):
                return cid
        return next(iter(self.channels), "SMS-PATIENT")

    def channel_manifest(self) -> list[dict[str, Any]]:
        return [
            {
                "channel_id": cid,
                "status": spec.get("status", "UNKNOWN"),
                "kind": spec.get("kind", "SMS"),
                "primary": bool(spec.get("primary", False)),
                "note": spec.get("note", ""),
            }
            for cid, spec in self.channels.items()
        ]

    # -- sending ----------------------------------------------------------
    def send(
        self,
        *,
        channel: str,
        result_revision_id: str,
        idempotency_key: str,
        at_minutes: float,
        content_digest: str | None = None,
        recipient: str | None = None,
    ) -> TransportAttempt:
        """Idempotent send, with provider semantics.

        A repeated key never produces a second *delivered* message. But a provider that timed out has
        not told us it received anything, so a retry after TIMEOUT/FAILED is a genuine new attempt -
        suppressing it would strand the case with no way to reach the patient.
        """
        with self._lock:
            return self._send_locked(
                channel=channel,
                result_revision_id=result_revision_id,
                idempotency_key=idempotency_key,
                at_minutes=at_minutes,
                content_digest=content_digest,
                recipient=recipient,
            )

    def _send_locked(
        self,
        *,
        channel: str,
        result_revision_id: str,
        idempotency_key: str,
        at_minutes: float,
        content_digest: str | None = None,
        recipient: str | None = None,
    ) -> TransportAttempt:
        for existing in self.attempts:
            if existing.idempotency_key == idempotency_key and existing.outcome not in {"TIMEOUT", "FAILED"}:
                existing.duplicate_suppressed = True
                self.ledger.append(
                    {
                        "at": sim_time(at_minutes),
                        "event": "SEND_SUPPRESSED_DUPLICATE",
                        "channel": channel,
                        "idempotency_key": idempotency_key,
                        "attempt_id": existing.attempt_id,
                        "note": "identical idempotency key already used; no second message created",
                    }
                )
                return existing

        attempt = TransportAttempt(
            attempt_id=f"ATT-{len(self.attempts) + 1:03d}",
            idempotency_key=idempotency_key,
            channel=channel,
            result_revision_id=result_revision_id,
            created_at=sim_time(at_minutes),
            provider_ref="SIM-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:10],
            recipient=recipient,
        )
        self.attempts.append(attempt)
        self.ledger.append(
            {
                "at": sim_time(at_minutes),
                "event": "SEND_REQUESTED",
                "channel": channel,
                "attempt_id": attempt.attempt_id,
                "idempotency_key": idempotency_key,
                "content_digest": content_digest,
                "recipient": recipient,
            }
        )

        plan = self._plan_for(len(self.attempts) - 1)
        outcome = str(plan.get("outcome", "ACCEPTED"))
        status = self.channel_status(channel)
        if status == "DOWN" and outcome not in {"TIMEOUT", "FAILED"}:
            outcome = "TIMEOUT"

        if outcome in {"ACCEPTED", "DELIVERED"}:
            attempt.accepted = True
            attempt.accepted_at = sim_time(at_minutes + float(plan.get("accept_after_minutes", 0.2)))
            attempt.outcome = "ACCEPTED"
            self.ledger.append(
                {
                    "at": attempt.accepted_at,
                    "event": "PROVIDER_ACCEPTED",
                    "channel": channel,
                    "attempt_id": attempt.attempt_id,
                    "note": "provider accepted the message; endpoint delivery not yet observed",
                }
            )
            if outcome == "DELIVERED":
                attempt.delivered = True
                attempt.delivered_at_minutes = at_minutes + float(plan.get("deliver_after_minutes", 1.0))
                attempt.delivered_at = sim_time(attempt.delivered_at_minutes)
                attempt.outcome = "DELIVERED"
                self.ledger.append(
                    {
                        "at": attempt.delivered_at,
                        "event": "ENDPOINT_DELIVERY_RECEIPT",
                        "channel": channel,
                        "attempt_id": attempt.attempt_id,
                        "note": "endpoint acknowledged receipt of the message (transport-level only)",
                    }
                )
        elif outcome == "FAILED":
            attempt.failed = True
            attempt.failure_reason = str(plan.get("reason", "channel rejected the message"))
            attempt.outcome = "FAILED"
            self.ledger.append(
                {
                    "at": sim_time(at_minutes + 0.5),
                    "event": "DELIVERY_FAILED",
                    "channel": channel,
                    "attempt_id": attempt.attempt_id,
                    "note": attempt.failure_reason,
                }
            )
        else:  # TIMEOUT / UNKNOWN -> no evidence at all
            attempt.outcome = "TIMEOUT" if outcome == "TIMEOUT" else "UNKNOWN"
            self.ledger.append(
                {
                    "at": sim_time(at_minutes + float(plan.get("timeout_after_minutes", 2.0))),
                    "event": "TRANSPORT_TIMEOUT" if outcome == "TIMEOUT" else "TRANSPORT_STATE_UNKNOWN",
                    "channel": channel,
                    "attempt_id": attempt.attempt_id,
                    "note": "no provider response. Absence of a response is not evidence of failure.",
                }
            )
        return attempt

    # -- reconciliation ---------------------------------------------------
    def record_acceptance_as_delivery(self, attempt_id: str, at_minutes: float) -> dict[str, Any]:
        """Model a legacy adapter that treats provider acceptance as delivery.

        This is the defect the strict semantics exist to prevent, reproduced on purpose so that the
        comparison in ``evaluation/report.md`` compares behaviour rather than a label. It is only
        reachable from a configuration whose ``transport_semantics`` is ``optimistic``; the shipped
        configuration never calls it. The write is recorded in the ledger, so a reviewer can see the
        conflation happening rather than infer it.
        """
        attempt = next((a for a in self.attempts if a.attempt_id == attempt_id), None)
        if attempt is None:
            return {"attempt_id": attempt_id, "result": "NO_SUCH_ATTEMPT", "conflated": False}
        if attempt.delivered:
            return {"attempt_id": attempt_id, "result": "ALREADY_DELIVERED", "conflated": False}
        if not attempt.accepted:
            return {"attempt_id": attempt_id, "result": "NOT_ACCEPTED", "conflated": False}
        attempt.delivered = True
        attempt.delivered_at = sim_time(at_minutes)
        attempt.delivered_at_minutes = at_minutes
        self.ledger.append(
            {
                "at": sim_time(at_minutes),
                "event": "ACCEPTANCE_RECORDED_AS_DELIVERY",
                "attempt_id": attempt_id,
                "note": "optimistic transport semantics: provider acceptance was recorded as endpoint delivery",
            }
        )
        return {"attempt_id": attempt_id, "result": "CONFLATED", "conflated": True}

    def reconcile(self, attempt_id: str, at_minutes: float) -> dict[str, Any]:
        """Resolve an unknown outcome by querying the provider ledger."""
        attempt = next((a for a in self.attempts if a.attempt_id == attempt_id), None)
        if attempt is None:
            return {"attempt_id": attempt_id, "result": "NO_SUCH_ATTEMPT", "reconciled": False}
        plan = next(
            (p for p in self.reconciliation_plan if p.get("attempt_id") in (None, attempt_id)),
            {"result": "STILL_UNKNOWN"},
        )
        result = str(plan.get("result", "STILL_UNKNOWN"))
        attempt.reconciled = True
        attempt.reconciliation_result = result
        if result == "DELIVERED":
            attempt.delivered = True
            attempt.accepted = True
            attempt.delivered_at = sim_time(at_minutes)
            attempt.delivered_at_minutes = at_minutes
            attempt.outcome = "DELIVERED"
            self.ledger.append(
                {
                    "at": sim_time(at_minutes),
                    "event": "RECONCILIATION_FOUND_DELIVERY",
                    "attempt_id": attempt_id,
                    "note": plan.get("note", "provider ledger shows an endpoint receipt issued after the timeout"),
                }
            )
        elif result == "FAILED":
            attempt.failed = True
            attempt.outcome = "FAILED"
            self.ledger.append(
                {
                    "at": sim_time(at_minutes),
                    "event": "RECONCILIATION_FOUND_FAILURE",
                    "attempt_id": attempt_id,
                    "note": plan.get("note", "provider ledger shows the message was never accepted"),
                }
            )
        else:
            self.ledger.append(
                {
                    "at": sim_time(at_minutes),
                    "event": "RECONCILIATION_INCONCLUSIVE",
                    "attempt_id": attempt_id,
                    "note": plan.get("note", "provider cannot determine the outcome"),
                }
            )
        return {
            "attempt_id": attempt_id,
            "result": result,
            "reconciled": True,
            "note": plan.get("note", ""),
        }

    # -- helpers ----------------------------------------------------------
    def _plan_for(self, index: int) -> dict[str, Any]:
        if index < len(self.attempt_plan):
            return self.attempt_plan[index]
        return {"outcome": "ACCEPTED"}

    def delivered(self) -> bool:
        return any(a.delivered for a in self.attempts)

    def outcome_of(self, attempt_id: str) -> str:
        a = next((x for x in self.attempts if x.attempt_id == attempt_id), None)
        return a.outcome if a else "MISSING"
