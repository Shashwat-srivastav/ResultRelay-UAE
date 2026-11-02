"""Append-only audit log with a hash chain.

The chain makes silent rewriting detectable: each entry commits to its predecessor. The
application exposes no update or delete path for audit entries, and ``verify_chain`` is
asserted in the test suite and shown in the exported bundle.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class AuditEntry:
    seq: int
    at: str
    run_id: str
    case_id: str
    event: str
    actor: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    #: Hash of the policy corpus in force when the entry was written (see retriever.index_sha256).
    kb_index_sha256: str = ""
    prev_hash: str = ""
    hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditLog:
    def __init__(self, run_id: str, case_id: str):
        self.run_id = run_id
        self.case_id = case_id
        self.entries: list[AuditEntry] = []
        self._last_hash = "GENESIS"

    def append(self, *, event: str, actor: str, summary: str, payload: dict[str, Any] | None = None,
               at: str | None = None) -> AuditEntry:
        from app.kb.retriever import index_sha256

        body = {
            "seq": len(self.entries) + 1,
            "at": at or datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "case_id": self.case_id,
            "event": event,
            "actor": actor,
            # Which version of the policy corpus was in force when this record was written. Without
            # it a decision cannot be reconstructed after the index is rebuilt (audit item A8).
            "kb_index_sha256": index_sha256(),
            "summary": summary,
            "payload": payload or {},
        }
        digest = hashlib.sha256((self._last_hash + _canonical(body)).encode("utf-8")).hexdigest()
        entry = AuditEntry(**body, prev_hash=self._last_hash, hash=digest)
        self.entries.append(entry)
        self._last_hash = digest
        return entry

    def verify_chain(self) -> tuple[bool, list[int]]:
        return verify_entries([e.to_dict() for e in self.entries])

    def as_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.entries]


def verify_entries(entries: list[dict[str, Any]]) -> tuple[bool, list[int]]:
    """Verify a chain from serialised entries.

    Used by the API to re-verify a chain read back out of the store, so the check is not
    assumed to hold merely because the writer said so.
    """
    prev = "GENESIS"
    broken: list[int] = []
    for entry in entries:
        body = {
            "seq": entry["seq"],
            "at": entry["at"],
            "run_id": entry["run_id"],
            "case_id": entry["case_id"],
            "event": entry["event"],
            "actor": entry["actor"],
            "summary": entry["summary"],
            "payload": entry.get("payload") or {},
            # Included in the digest, so the corpus a decision was made from cannot be edited after
            # the fact any more than the decision itself can.
            "kb_index_sha256": entry.get("kb_index_sha256") or "",
        }
        expected = hashlib.sha256((prev + _canonical(body)).encode("utf-8")).hexdigest()
        if entry.get("prev_hash") != prev or entry.get("hash") != expected:
            broken.append(int(entry["seq"]))
        prev = entry.get("hash", "")
    return (not broken, broken)


# --- signed checkpoints ---------------------------------------------------------------------------
# A hash chain proves the entries are consistent with each other, not that they are the ones that were
# written: anyone who can rewrite the store can rebuild a consistent chain. A checkpoint signs the chain
# head with a key held outside the store (RESULTRELAY_AUDIT_KEY), so a rebuilt chain no longer matches.
# It is not a trusted timestamp; an external timestamping service would be the next step.

def _checkpoint_message(run_id: str, case_id: str, count: int, head: str) -> bytes:
    return f"{run_id}|{case_id}|{count}|{head}".encode("utf-8")


def sign_checkpoint(log: "AuditLog", key: bytes | None = None) -> dict[str, Any]:
    import hmac
    import os

    key = key or os.environ.get("RESULTRELAY_AUDIT_KEY", "").encode("utf-8")
    head = log.entries[-1].hash if log.entries else "GENESIS"
    cp = {"run_id": log.run_id, "case_id": log.case_id, "entries": len(log.entries), "head": head,
          "signed_at": datetime.now(timezone.utc).isoformat(), "alg": "HMAC-SHA256"}
    if not key:
        return {**cp, "signature": None, "note": "unsigned: set RESULTRELAY_AUDIT_KEY to sign checkpoints"}
    cp["signature"] = hmac.new(key, _checkpoint_message(log.run_id, log.case_id, len(log.entries), head),
                               hashlib.sha256).hexdigest()
    return cp


def verify_checkpoint(entries: list[dict[str, Any]], checkpoint: dict[str, Any], key: bytes) -> bool:
    """True only if the chain is intact, its head is the checkpointed head, and the signature matches."""
    import hmac

    ok, _ = verify_entries(entries)
    if not ok or not checkpoint.get("signature"):
        return False
    count = int(checkpoint["entries"])
    if count > len(entries):
        return False
    head = entries[count - 1]["hash"] if count else "GENESIS"
    expected = hmac.new(key, _checkpoint_message(checkpoint["run_id"], checkpoint["case_id"], count, head),
                        hashlib.sha256).hexdigest()
    return head == checkpoint["head"] and hmac.compare_digest(expected, checkpoint["signature"])
