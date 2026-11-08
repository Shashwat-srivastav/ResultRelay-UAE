"""Fields the v4 console needs to show provenance, an owner and a deadline without opening a case."""

from __future__ import annotations

import re

ISO_Z = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d(\.\d+)?)?Z$")


def _played(client, scenario, config="resultrelay"):
    run = client.post("/api/runs", json={"scenario_id": scenario, "configuration": config}).json()["run"]
    client.post(f"/api/runs/{run['run_id']}/play")
    return run


def test_scenarios_carry_provenance_and_safe_endings(client):
    rows = {s["scenario_id"]: s for s in client.get("/api/scenarios").json()["scenarios"]}
    assert len(rows) == 12
    # S6 is a designed test: no incident source, and the API says so with None rather than an empty shell.
    assert rows["S6-jurisdiction-conflict"]["provenance"] is None
    s9 = rows["S9-reply-from-someone-else"]["provenance"]
    assert s9["match"] == "very strong" and s9["sources"][0]["url"].startswith("https://")
    for sid, s in rows.items():
        assert s["safe_final_states"], sid
        if sid != "S6-jurisdiction-conflict":
            assert {"note", "match", "failure_mode", "sources"} <= set(s["provenance"]), sid


def test_generous_match_labels_were_downgraded():
    """ux-research §6.4: S3a and S8 sources do not support "almost exact" / "strong"."""
    from app.orchestration.engine import list_scenarios

    match = {s["scenario_id"]: (s["provenance"] or {}).get("match") for s in list_scenarios()}
    assert match["S3a-channel-outage-no-evidence"] == "close"
    assert match["S8-accepted-never-delivered"] == "related"


def test_trace_names_its_scenario_and_who_owns_the_case(client):
    run = _played(client, "S10-escalation-nobody-answers")
    trace = client.get(f"/api/runs/{run['run_id']}/trace").json()
    assert trace["scenario_id"] == "S10-escalation-nobody-answers"
    assert trace["configuration_label"]
    escs = trace["escalations"]
    assert escs, "S10 must escalate"
    tiers = [e["tier"] for e in escs]
    assert tiers[0] == 1 and max(tiers) >= 2, tiers  # nobody answered: raised to the next tier
    for e in escs:
        assert e["role"] and e["status"]
        assert ISO_Z.match(e["due_at"]), e["due_at"]


def test_case_rows_include_run_configuration_and_escalation_summary(client):
    run = _played(client, "S10-escalation-nobody-answers")
    rows = client.get("/api/cases").json()["cases"]
    row = next(r for r in rows if r["case_id"] == run["case_id"])
    assert row["run_id"] == run["run_id"]
    assert row["configuration"] == "resultrelay" and row["configuration_label"]
    assert row["escalation_count"] == len(row["escalations"]) >= 2
    first = row["escalations"][0]
    assert set(first) >= {"role", "tier", "status", "due_at"}
    assert not first["escalation_id"].startswith("RUN-")  # the store's run prefix is stripped
    # The store row follows the runtime: the tier-1 escalation was superseded once it went overdue.
    trace = client.get(f"/api/runs/{run['run_id']}/trace").json()
    assert [e["status"] for e in row["escalations"]] == [e["status"] for e in trace["escalations"]]
