"""The served corpus must be verifiable, and a tampered corpus must not be served.

Pre-fix, ``index_sha256()`` returned a field stored *inside* the file it was supposed to protect,
the health endpoint repeated a build-time summary, and 161 tests passed against a corpus in which a
binding clause had been rewritten to say the opposite. These tests make that failure loud.
"""

from __future__ import annotations

import hashlib
import json
import shutil

import pytest

from app.kb import retriever


def _copy_corpus(tmp_path):
    """A private copy of the index and its pin, so a test can tamper without touching the repo."""
    index = tmp_path / "chunks.json"
    pin = tmp_path / "pinned.sha256"
    shutil.copyfile(retriever.INDEX_PATH, index)
    shutil.copyfile(retriever.PIN_PATH, pin)
    return index, pin


def _point_at(monkeypatch, index, pin):
    monkeypatch.setattr(retriever, "INDEX_PATH", index)
    monkeypatch.setattr(retriever, "PIN_PATH", pin)
    retriever.reload_index()


def test_the_served_index_matches_the_committed_pin():
    report = retriever.corpus_integrity()
    assert report["ok"] is True, report["reason"]
    assert report["hash_matches_pin"] is True
    assert report["declared_matches_recomputed"] is True
    # On a fresh clone the source texts are absent (not redistributed); those quotes are reported as
    # not re-verifiable here, never as verified. With the cache present every quote must verify.
    assert report["quotes_verified"] + report["quotes_not_reverifiable_here"] == report["chunk_count"]
    assert report["chunk_count"] >= 63


def test_editing_a_chunk_is_detected_and_the_corpus_is_refused(monkeypatch, tmp_path):
    index, pin = _copy_corpus(tmp_path)
    payload = json.loads(index.read_text(encoding="utf-8"))
    target = next(c for c in payload["chunks"] if c["chunk_id"] == "S1-13.4")
    target["text"] = "Genetic results shall be sent directly to the patient by SMS."
    index.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    _point_at(monkeypatch, index, pin)
    report = retriever.corpus_integrity()
    assert report["ok"] is False
    assert report["hash_matches_pin"] is False
    assert "pinned" in report["reason"]

    with pytest.raises(RuntimeError):
        retriever.all_chunks()


def test_a_forged_quote_is_caught_even_when_the_hash_is_updated(monkeypatch, tmp_path):
    """Re-pinning a tampered corpus must still fail the quote check against the sources."""
    index, pin = _copy_corpus(tmp_path)
    payload = json.loads(index.read_text(encoding="utf-8"))
    target = next(c for c in payload["chunks"] if c["chunk_id"] == "S1-11.1.2")
    target["text"] = "Critical results shall be sent to the patient without any further advice."
    payload["index_sha256"] = hashlib.sha256(
        json.dumps(payload["chunks"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    index.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pin.write_text(payload["index_sha256"] + "\n", encoding="utf-8")

    _point_at(monkeypatch, index, pin)
    report = retriever.corpus_integrity()
    assert report["hash_matches_pin"] is True, "the attacker re-pinned the index"
    assert report["ok"] is False, "a re-pinned forgery must still be rejected"
    assert any(m["chunk_id"] == "S1-11.1.2" for m in report["quote_mismatches"])


def test_the_reported_hash_is_recomputed_not_echoed(monkeypatch, tmp_path):
    index, pin = _copy_corpus(tmp_path)
    payload = json.loads(index.read_text(encoding="utf-8"))
    payload["chunks"][0]["text"] = payload["chunks"][0]["text"] + " (edited)"
    index.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _point_at(monkeypatch, index, pin)

    assert retriever.index_sha256() == retriever.compute_index_sha256(payload["chunks"])
    assert retriever.index_sha256() != payload["index_sha256"], (
        "index_sha256() must not echo the stored field it is supposed to protect"
    )


def test_health_reports_the_live_check_not_the_build_summary(client):
    body = client.get("/api/health").json()
    integrity = body["knowledge_base"]["integrity"]
    assert body["policy_corpus_verified"] is True
    assert integrity["ok"] is True
    assert integrity["hash_matches_pin"] is True
    assert "checked_at" in integrity
