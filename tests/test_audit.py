"""The audit log is append-only and tamper-evident, or it is decoration."""

from __future__ import annotations

import json
from pathlib import Path

from app.audit.log import AuditLog, verify_entries


def test_audit_chain(tmp_path: Path):
    log = AuditLog(run_id="RUN-T", case_id="CASE-T")
    log.append(event="case.opened", actor="SYSTEM", summary="case created", at="2026-03-02T09:00:00Z")
    log.append(event="result.finalized", actor="LAB", summary="finalized R1", at="2026-03-02T09:05:00Z")
    log.append(event="transmission.requested", actor="GATE", summary="send R1", at="2026-03-02T09:06:00Z")

    ok, broken = log.verify_chain()
    assert ok is True
    assert broken == []

    entries = log.as_list()
    assert [e["seq"] for e in entries] == [1, 2, 3]
    assert entries[0]["prev_hash"] == "GENESIS"
    # Each entry commits to its predecessor.
    assert entries[1]["prev_hash"] == entries[0]["hash"]
    assert entries[2]["prev_hash"] == entries[1]["hash"]

    # Round-trip through JSON: verification works on stored rows, not just in-memory objects.
    round_tripped = json.loads(json.dumps(entries))
    assert verify_entries(round_tripped) == (True, [])


def test_editing_a_summary_breaks_the_chain():
    log = AuditLog(run_id="RUN-T", case_id="CASE-T")
    for i in range(3):
        log.append(event="e", actor="SYSTEM", summary=f"step {i}", at=f"2026-03-02T09:0{i}:00Z")

    tampered = log.as_list()
    tampered[1]["summary"] = "something the operator preferred"
    ok, broken = verify_entries(tampered)
    assert ok is False
    assert broken == [2]


def test_deleting_an_entry_breaks_the_chain():
    log = AuditLog(run_id="RUN-T", case_id="CASE-T")
    for i in range(4):
        log.append(event="e", actor="SYSTEM", summary=f"step {i}", at=f"2026-03-02T09:0{i}:00Z")

    entries = log.as_list()
    del entries[2]
    ok, broken = verify_entries(entries)
    assert ok is False
    assert broken, "removal of an entry must be detectable"


def test_payload_is_part_of_the_hash():
    log = AuditLog(run_id="RUN-T", case_id="CASE-T")
    log.append(event="e", actor="SYSTEM", summary="s", payload={"amount": 1}, at="2026-03-02T09:00:00Z")
    entries = log.as_list()
    entries[0]["payload"]["amount"] = 999
    ok, _ = verify_entries(entries)
    assert ok is False


def test_the_log_exposes_no_update_or_delete_path():
    log = AuditLog(run_id="RUN-T", case_id="CASE-T")
    public = {n for n in dir(log) if not n.startswith("_")}
    assert not {"update", "delete", "remove", "edit"} & public


def test_a_signed_checkpoint_detects_a_rebuilt_chain():
    """A consistent but forged chain passes verify_entries; it must not pass the signed checkpoint."""
    import hashlib

    from app.audit.log import AuditLog, _canonical, sign_checkpoint, verify_checkpoint, verify_entries

    log = AuditLog("RUN-1", "SYN-CASE-1")
    for i in range(3):
        log.append(event="step", actor="SYSTEM", summary=f"step {i}", at=f"2026-01-01T00:00:0{i}Z")
    key = b"held-outside-the-store"
    cp = sign_checkpoint(log, key)
    entries = log.as_list()
    assert verify_checkpoint(entries, cp, key)
    # Rewrite entry 2 and rebuild a fully consistent chain, as someone with write access could.
    forged, prev = [], "GENESIS"
    for e in entries:
        e = dict(e)
        if e["seq"] == 2:
            e["summary"] = "something else happened"
        body = {k: e[k] for k in ("seq", "at", "run_id", "case_id", "event", "actor", "summary", "payload")}
        body["kb_index_sha256"] = e.get("kb_index_sha256") or ""
        e["prev_hash"], e["hash"] = prev, hashlib.sha256((prev + _canonical(body)).encode("utf-8")).hexdigest()
        prev = e["hash"]
        forged.append(e)
    assert verify_entries(forged)[0] is True          # the chain alone is fooled
    assert verify_checkpoint(forged, cp, key) is False  # the signed checkpoint is not
