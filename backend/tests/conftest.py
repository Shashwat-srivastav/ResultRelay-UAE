"""Shared fixtures.

The tests run the real engine, the real state machine and the real knowledge base. Nothing is
mocked except the network (which is simulated by design) — a test that passed only against a
stub of the guard rules would not tell us anything about the guard rules.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

REPO = BACKEND.parent
SCENARIO_DIR = REPO / "evaluation" / "scenarios"
EXPECTED_DIR = REPO / "evaluation" / "expected_actions"

from app.orchestration.engine import CONFIGS, Orchestrator, build_runtime, load_scenario  # noqa: E402


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO


@pytest.fixture(scope="session")
def scenario_ids() -> list[str]:
    return sorted(p.stem for p in SCENARIO_DIR.glob("*.json"))


@pytest.fixture(scope="session")
def expected_actions() -> dict[str, dict]:
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8")) for p in EXPECTED_DIR.glob("*.json")
    }


@pytest.fixture(scope="session")
def configs() -> dict:
    return CONFIGS


@pytest.fixture
def run(scenario_ids):
    """Run a scenario under a configuration and return the finished runtime."""

    def _run(scenario_id: str, config: str = "resultrelay", stop_after: int | None = None):
        scenario = load_scenario(scenario_id)
        rt = build_runtime(scenario, config, run_id=f"TEST-{scenario_id}-{config}")
        orch = Orchestrator(rt)
        for i, spec in enumerate(scenario["steps"]):
            if stop_after is not None and i >= stop_after:
                break
            orch.step(spec)
        return rt

    return _run


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Point the persistence layer at a throwaway SQLite file."""
    from app.models import db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db", raising=False)
    db_module.reset_engine()
    yield tmp_path / "test.db"
    db_module.reset_engine()


@pytest.fixture
def client(tmp_db):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
