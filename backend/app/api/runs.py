"""In-process registry of live scenario runs.

Runs are held in memory for progressive stepping; every step is also persisted to SQLite so
that reads, the dashboard and the audit bundle are served from the store, not from memory.
"""

from __future__ import annotations

from typing import Any

_RUNS: dict[str, dict[str, Any]] = {}
MAX_RUNS = 40
#: How many to drop when the bound is reached. The previous version dropped 8 on the way *past*
#: 40 and then grew again, so the registry never actually stayed bounded (audit item S4).
EVICT_BATCH = 8


def put(run_id: str, entry: dict[str, Any]) -> None:
    if len(_RUNS) >= MAX_RUNS:
        for key in list(_RUNS)[:EVICT_BATCH]:
            _RUNS.pop(key, None)
    _RUNS[run_id] = entry
    assert len(_RUNS) <= MAX_RUNS, f"run registry exceeded its own bound: {len(_RUNS)}"


def get(run_id: str) -> dict[str, Any] | None:
    return _RUNS.get(run_id)


def all_runs() -> dict[str, dict[str, Any]]:
    return _RUNS
