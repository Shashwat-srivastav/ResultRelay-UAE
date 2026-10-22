"""Benchmark runner.

Runs every scenario in every configuration against the same event stream and the same
simulated network, then compares the resulting record with independently authored
expectations. Determinism is checked by executing each run twice and comparing a
signature of the observable record.

One command runs everything:
    python scripts/run_evaluation.py
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.evaluation.metrics import compute
from app.orchestration.engine import CONFIGS, load_scenario, run_scenario

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO_DIR = REPO_ROOT / "evaluation" / "scenarios"
EXPECTED_DIR = REPO_ROOT / "evaluation" / "expected_actions"
RESULTS_DIR = REPO_ROOT / "evaluation" / "results"


def signature(rt) -> tuple:
    """A deterministic fingerprint of the observable record, used for replay checks."""
    return (
        rt.state.value,
        tuple(
            (
                t["step"],
                t["prior_state"],
                t["resulting_state"],
                t["trigger_event"],
                t["status"],
            )
            for t in rt.transitions
        ),
        tuple((a.channel, a.result_revision_id, a.outcome, a.reconciled) for a in rt.network.attempts),
    )


def run_one(scenario: dict[str, Any], config_name: str, expected: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    rt = run_scenario(scenario, config_name)
    wall_ms = (time.perf_counter() - t0) * 1000.0
    record = compute(rt, expected, wall_ms)

    rt2 = run_scenario(scenario, config_name)
    record["replay_reproducible"] = signature(rt) == signature(rt2)
    record["deterministic_state"] = rt2.state.value == rt.state.value

    ok, broken = rt.audit.verify_chain() if rt.audit else (False, [])
    record["audit_entries"] = len(rt.audit.entries) if rt.audit else 0
    record["audit_broken_seqs"] = broken

    record["prohibited_actions_observed"] = [
        name for name, passed in record["assertions"].items() if not passed
    ]
    record["agent_sequence"] = [
        {
            "step": s["step"],
            "event": s["event"]["kind"],
            "agents": [a["agent_id"] for a in s["agents"]],
            "proposed": s["proposed_action"],
            "enforced": s["enforced_action"],
            "state": s["resulting_state"],
        }
        for s in rt.steps
    ]
    record["citations"] = _collect_citations(rt)
    return record


def _collect_citations(rt) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for step in rt.steps:
        for agent in step["agents"]:
            for src in agent["applicable_sources"]:
                out.append(
                    {
                        "step": step["step"],
                        "agent_id": agent["agent_id"],
                        "source_id": src["source_id"],
                        "section": src["section"],
                        "page": src["page"],
                        "claim_type": src["claim_type"],
                        "consumed_by_decision": agent["agent_id"]
                        in ("policy_applicability", "lab_workflow"),
                    }
                )
    return out


def run_all(
    configurations: list[str] | None = None,
    scenario_ids: list[str] | None = None,
) -> dict[str, Any]:
    configurations = configurations or list(CONFIGS)
    unknown = [c for c in configurations if c not in CONFIGS]
    if unknown:
        raise SystemExit(f"unknown configuration(s): {unknown}; choose from {list(CONFIGS)}")
    started = datetime.now(timezone.utc).isoformat()
    runs: list[dict[str, Any]] = []

    for path in sorted(SCENARIO_DIR.glob("*.json")):
        scenario = json.loads(path.read_text(encoding="utf-8"))
        if scenario_ids and scenario["scenario_id"] not in scenario_ids:
            continue
        exp_path = EXPECTED_DIR / f"{scenario['scenario_id']}.json"
        expected = (
            json.loads(exp_path.read_text(encoding="utf-8"))
            if exp_path.exists()
            else {"must_hold": [], "safe_final_states": []}
        )
        for config in configurations:
            runs.append(run_one(scenario, config, expected))

    summary = _summarise(runs, configurations)
    report = {
        "run_started": started,
        "run_finished": datetime.now(timezone.utc).isoformat(),
        "configurations": {name: CONFIGS[name].label for name in configurations},
        "scenario_count": len({r["scenario_id"] for r in runs}),
        "run_count": len(runs),
        "summary": summary,
        "runs": runs,
        "caveats": [
            "All records are synthetic. These results are not evidence of clinical safety, clinical effectiveness, or regulatory compliance.",
            "The scenario set is authored by the same team that built the system; expected actions were written separately from engine code, but authorship is not independent of the project.",
            "Timings are wall-clock measurements on the build machine and are indicative only.",
        ],
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (RESULTS_DIR / f"run-{started.replace(':', '').replace('-', '')[:15]}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def _summarise(runs: list[dict[str, Any]], configurations: list[str]) -> dict[str, Any]:
    by_config: dict[str, dict[str, Any]] = {}
    for name in configurations:
        subset = [r for r in runs if r["configuration"] == name]
        total_assertions = sum(r["assertions_total"] for r in subset)
        passed = sum(r["assertions_passed"] for r in subset)
        by_config[name] = {
            "label": CONFIGS[name].label,
            "runs": len(subset),
            "assertions_passed": passed,
            "assertions_total": total_assertions,
            "assertion_pass_rate": round(passed / total_assertions, 3) if total_assertions else 0.0,
            "scenarios_fully_safe": sum(1 for r in subset if r["all_assertions_passed"]),
            "workflows_completed": sum(1 for r in subset if r["workflow_completed"]),
            "false_closures": sum(1 for r in subset if r["measures"]["false_closure"]),
            "false_deliveries": sum(1 for r in subset if r["measures"]["false_delivery"]),
            "stale_ack_uses": sum(1 for r in subset if r["measures"]["stale_ack_used"]),
            "unauthorised_channels": sum(1 for r in subset if r["measures"]["unauthorised_channel"]),
            "scope_violations": sum(1 for r in subset if r["measures"]["scope_violation"]),
            "audit_findings": sum(r["measures"]["audit_findings"] for r in subset),
            "comparator_cited_as_binding": sum(1 for r in subset if r["measures"]["comparator_cited_as_binding"]),
            "mean_provenance_completeness": round(
                sum(r["measures"]["provenance_completeness"] for r in subset) / len(subset), 3
            ) if subset else 0.0,
            "replay_reproducible": all(r["replay_reproducible"] for r in subset),
            "audit_chains_valid": all(r["measures"]["audit_chain_valid"] for r in subset),
            "mean_wall_ms": round(sum(r["wall_ms"] for r in subset) / len(subset), 1) if subset else 0.0,
        }

    per_scenario: dict[str, dict[str, Any]] = {}
    for r in runs:
        per_scenario.setdefault(r["scenario_id"], {})[r["configuration"]] = {
            "final_state": r["final_state"],
            "safe": r["all_assertions_passed"],
            "completed": r["workflow_completed"],
            "failed_assertions": r["prohibited_actions_observed"],
        }
    return {"by_configuration": by_config, "by_scenario": per_scenario}


def write_markdown(report: dict[str, Any], path: Path) -> Path:
    s = report["summary"]["by_configuration"]
    lines: list[str] = []
    lines.append("# ResultRelay evaluation report\n")
    lines.append(f"Generated: {report['run_finished']}  \nRuns: {report['run_count']} "
                 f"({report['scenario_count']} scenarios x {len(report['configurations'])} configurations)\n")
    lines.append("> All data is synthetic. These results are **not** evidence of clinical safety, clinical "
                 "effectiveness, or regulatory compliance.\n")

    lines.append("## Headline comparison\n")
    lines.append("| Configuration | Safe scenarios | Assertions passed | False closures | False deliveries | Stale-ack uses | Unauthorised channels | Scope violations | Comparator cited as binding | Transmission provenance | Replay stable |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for name, row in s.items():
        lines.append(
            f"| {row['label']} | {row['scenarios_fully_safe']}/{row['runs']} | "
            f"{row['assertions_passed']}/{row['assertions_total']} ({row['assertion_pass_rate']:.0%}) | "
            f"{row['false_closures']} | {row['false_deliveries']} | {row['stale_ack_uses']} | "
            f"{row['unauthorised_channels']} | {row['scope_violations']} | "
            f"{row['comparator_cited_as_binding']} | "
            f"{row['mean_provenance_completeness']:.2f} | {'yes' if row['replay_reproducible'] else 'no'} |"
        )

    lines.append("\n## Per-scenario outcome\n")
    configs = list(report["configurations"].keys())
    lines.append("| Scenario | " + " | ".join(configs) + " |")
    lines.append("|---|" + "---|" * len(configs))
    for sid, row in report["summary"]["by_scenario"].items():
        cells = []
        for c in configs:
            r = row.get(c, {})
            mark = "PASS" if r.get("safe") else "FAIL"
            cells.append(f"{mark} `{r.get('final_state','?')}`")
        lines.append(f"| {sid} | " + " | ".join(cells) + " |")

    lines.append("\n## Failed assertions by run\n")
    any_fail = False
    for r in report["runs"]:
        if r["prohibited_actions_observed"]:
            any_fail = True
            lines.append(f"- **{r['scenario_id']} / {r['configuration']}** -> final `{r['final_state']}`: "
                         + ", ".join(r["prohibited_actions_observed"]))
    if not any_fail:
        lines.append("- none")

    lines.append("\n## Caveats\n")
    for c in report["caveats"]:
        lines.append(f"- {c}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    rep = run_all()
    out = write_markdown(rep, REPO_ROOT / "evaluation" / "report.md")
    print(json.dumps(rep["summary"]["by_configuration"], indent=2))
    print("report written to", out)
