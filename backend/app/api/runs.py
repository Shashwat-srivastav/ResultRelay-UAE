"""Registry of live scenario runs, with the concurrency control the step endpoint needs.

Runs are held in memory for progressive stepping; every step is also persisted to SQLite so that
reads, the dashboard and the audit bundle are served from the store, not from memory.

Two things here exist because of red-team findings C-1 and H-7:

* **One writer per run.** ``run_lock(run_id)`` returns a mutual-exclusion lock that the step and
  play endpoints hold for the whole read-modify-write cycle. Without it, two concurrent step
  requests read the same cursor, both execute the same event, and both dispatch the same message
  (measured: two delivered SMS for one notification). The lock is per run, so different runs still
  progress in parallel.
* **Eviction that cannot orphan a run.** A run that is executing is never evicted, and an evicted
  run is not lost: its cursor is durable (``runs`` table), so ``routes`` can rebuild the runtime by
  deterministic replay instead of answering 404.
"""

from __future__ import annotations

import threading
from typing import Any

_RUNS: dict[str, dict[str, Any]] = {}
_REGISTRY_LOCK = threading.RLock()
_RUN_LOCKS: dict[str, threading.RLock] = {}

MAX_RUNS = 40
#: How many to drop when the bound is reached. The previous version dropped 8 on the way *past*
#: 40 and then grew again, so the registry never actually stayed bounded (audit item S4).
EVICT_BATCH = 8


def run_lock(run_id: str) -> threading.RLock:
    """The mutex for one run. Created lazily and never handed to two runs at once."""
    with _REGISTRY_LOCK:
        lock = _RUN_LOCKS.get(run_id)
        if lock is None:
            lock = threading.RLock()
            _RUN_LOCKS[run_id] = lock
        return lock


def put(run_id: str, entry: dict[str, Any]) -> None:
    with _REGISTRY_LOCK:
        if len(_RUNS) >= MAX_RUNS:
            _evict_locked()
        entry.setdefault("busy", 0)
        _RUNS[run_id] = entry
        assert len(_RUNS) <= MAX_RUNS, f"run registry exceeded its own bound: {len(_RUNS)}"


def _evict_locked() -> int:
    """Drop the least-recently-used runs that are not executing. Never evicts a busy run.

    Eviction only removes the *in-memory* copy. The cursor is durable, so a resumed run is rebuilt
    by replay; this is why an eviction is no longer a data-loss event (H-7).
    """
    candidates = [
        (entry.get("last_used", 0.0), run_id)
        for run_id, entry in _RUNS.items()
        if not entry.get("busy")
    ]
    candidates.sort()
    dropped = 0
    for _, run_id in candidates[:EVICT_BATCH]:
        _RUNS.pop(run_id, None)
        dropped += 1
    return dropped


def get(run_id: str) -> dict[str, Any] | None:
    with _REGISTRY_LOCK:
        entry = _RUNS.get(run_id)
        if entry is not None:
            entry["last_used"] = _touch_counter()
        return entry


_TOUCHES = [0]


def _touch_counter() -> float:
    _TOUCHES[0] += 1
    return float(_TOUCHES[0])


def all_runs() -> dict[str, dict[str, Any]]:
    with _REGISTRY_LOCK:
        return dict(_RUNS)


def clear() -> None:
    """Test hook: forget every run and lock."""
    with _REGISTRY_LOCK:
        _RUNS.clear()
        _RUN_LOCKS.clear()
