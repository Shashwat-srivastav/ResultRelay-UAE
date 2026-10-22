"""In-process registry of live scenario runs.

Runs are held in memory for progressive stepping; every step is also persisted to SQLite so
that reads, the dashboard and the audit bundle are served from the store, not from memory.
"""

from __future__ import annotations

from typing import Any

_RUNS: dict[str, dict[str, Any]] = {}
MAX_RUNS = 40


def put(run_id: str, entry: dict[str, Any]) -> None:
    if len(_RUNS) >= MAX_RUNS:
        # Drop the oldest completed run so a long demo does not grow without bound.
        for key in list(_RUNS)[:8]:
            _RUNS.pop(key, None)
    _RUNS[run_id] = entry


def get(run_id: str) -> dict[str, Any] | None:
    return _RUNS.get(run_id)


def all_runs() -> dict[str, dict[str, Any]]:
    return _RUNS
