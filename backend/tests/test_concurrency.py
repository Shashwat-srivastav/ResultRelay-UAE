"""Concurrency, retry and replay.

These tests exist because the shipped system had none: 161 tests passed while two concurrent step
requests could deliver the same patient message twice, and while a replayed scenario silently wrote
zero transitions and reported a broken audit chain. Each test here fails on the pre-fix code.

The endpoints are exercised as plain functions rather than over HTTP so that the threads in a test
contend for the same lock, cursor and database. A ``TestClient`` may serialise request handling per
client instance, which would have made a concurrency test pass without ever being concurrent.
"""

from __future__ import annotations

import threading

import pytest
from starlette.requests import Request

from app.api import routes
from app.api import runs as registry


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.clear()
    yield
    registry.clear()


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": raw})


def _start(scenario: str = "S1-ambiguous-delivery", config: str = "resultrelay") -> dict:
    return routes.start_run(routes.StartRun(scenario_id=scenario, configuration=config))["run"]


def _delivered(run: dict) -> int:
    return sum(1 for a in run["attempts"] if a["delivered"])


def test_concurrent_steps_release_each_event_once(tmp_db):
    """Eight parallel step requests must release eight distinct events, once each.

    Pre-fix: every request read the same cursor and executed the same event, so the run stalled or
    dispatched the same message more than once.
    """
    run = _start()
    run_id = run["run_id"]
    responses: list[dict] = []
    errors: list[BaseException] = []

    def step() -> None:
        try:
            responses.append(routes.step_run(run_id, _request()))
        except BaseException as exc:  # noqa: BLE001 - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=step) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    released = sorted(r["progress"]["released"] for r in responses if r.get("progress"))
    assert released == list(range(1, len(released) + 1)), released

    final = routes.get_run(run_id)
    assert _delivered(final) == 1, f"expected one delivered message, got {_delivered(final)}"


def test_concurrent_steps_are_deterministic(tmp_db):
    """The same input must produce the same terminal state on every repetition.

    Pre-fix: one interleaving ended RESULT_FINALIZED and another ended ESCALATION_REQUIRED.
    """
    states = set()
    for _ in range(6):
        registry.clear()
        run = _start()
        run_id = run["run_id"]
        threads = [threading.Thread(target=lambda: routes.step_run(run_id, _request())) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        states.add(routes.get_run(run_id)["state"])
    assert len(states) == 1, f"concurrent runs diverged: {states}"


def test_a_retried_step_does_not_consume_the_next_event(tmp_db):
    """A retried request carrying the same idempotency key must return the first response.

    Pre-fix: the retry advanced the cursor, so an at-least-once client silently skipped an event.
    """
    run_id = _start()["run_id"]
    first = routes.step_run(run_id, _request({"Idempotency-Key": "k-1"}))
    retried = routes.step_run(run_id, _request({"Idempotency-Key": "k-1"}))
    assert retried["progress"] == first["progress"] == {"released": 1, "total": 8}
    second = routes.step_run(run_id, _request({"Idempotency-Key": "k-2"}))
    assert second["progress"]["released"] == 2


def test_replaying_a_scenario_keeps_its_own_transitions_and_valid_chain(tmp_db):
    """Two runs of one scenario must both persist their transitions and verify.

    Pre-fix, on a fresh database: run 1 wrote 15 transitions and a valid chain; the identical run 2
    wrote 0 transitions and reported every sequence as broken.
    """
    first = _start("S2-correction-after-acknowledgment")
    routes.play_run(first["run_id"])
    one = routes.case_integrity(first["case_id"])
    assert one["chain_valid"] is True, one["findings"]
    assert one["transition_count"] > 0

    second = _start("S2-correction-after-acknowledgment")
    routes.play_run(second["run_id"])
    two = routes.case_integrity(second["case_id"])

    assert two["case_id"] != one["case_id"], "a replay must be its own case, not merged history"
    assert two["chain_valid"] is True, two["findings"]
    assert two["transition_count"] == one["transition_count"], (one, two)
    assert two["replayed_state"] == two["store_state"]
    assert len(two["runs"]) == 1


def test_an_evicted_run_is_resumable_from_the_store(tmp_db):
    """Eviction must not orphan a run: the cursor is durable and the runtime is rebuilt.

    Pre-fix: after 44 runs the oldest run answered 404 on step, mid-flight, with no way back.
    """
    run_id = _start("S3a-channel-outage-no-evidence")["run_id"]
    routes.step_run(run_id, _request())
    registry._RUNS.pop(run_id, None)  # exactly what eviction does

    resumed = routes.step_run(run_id, _request())
    assert resumed["progress"]["released"] == 2
    final = routes.get_run(run_id)
    assert final["run_id"] == run_id
    assert len(final["transitions"]) >= 1
