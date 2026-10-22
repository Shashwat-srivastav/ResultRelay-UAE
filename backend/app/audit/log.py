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
