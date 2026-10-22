#!/usr/bin/env python3
"""Run the full scenario x configuration matrix and write the report.

    python scripts/run_evaluation.py                 # all scenarios x all configurations
    python scripts/run_evaluation.py --config resultrelay policy_blind
    python scripts/run_evaluation.py --scenario S4-genetic-scope-exclusion -v

Exit codes: 0 when every configured run completed (regardless of pass/fail assertions — the
baselines are *expected* to fail some), 1 when a run could not be executed at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.evaluation.runner import run_all, write_markdown  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", nargs="*", help="configuration names (default: all four)")
    ap.add_argument("--scenario", nargs="*", help="scenario ids (default: all)")
    ap.add_argument("--quiet", action="store_true", help="print only the summary table")
    ap.add_argument("--json", action="store_true", help="print the raw report instead of a table")
    args = ap.parse_args()

    report = run_all(args.config, args.scenario)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    if not args.quiet:
        for run in report["runs"]:
            flag = "ok  " if run["all_assertions_passed"] else "FAIL"
            print(
                f"  [{flag}] {run['scenario_id']:38s} {run['configuration']:14s} "
                f"{run['final_state']:34s} {run['assertions_passed']}/{run['assertions_total']}"
            )
            for key, passed in run["assertions"].items():
                if not passed:
                    print(f"          - {key}")

    print("\nconfiguration".ljust(18), "safe", " assertions  provenance  replay")
    for name, s in report["summary"]["by_configuration"].items():
        print(
            f"{name:18s} {s['scenarios_fully_safe']}/{s['runs']:<3} "
            f"{s['assertions_passed']:>3}/{s['assertions_total']:<8} "
            f"{s['mean_provenance_completeness']:>9.2f}  "
            f"{'stable' if s['replay_reproducible'] else 'DRIFT'}"
        )

    out = ROOT / "evaluation" / "report.md"
    write_markdown(report, out)
    print(f"\nreport: {out}")
    print(f"machine-readable: {ROOT / 'evaluation' / 'results' / 'latest.json'}")

    unfinished = [r for r in report["runs"] if not r.get("workflow_completed")]
    return 0 if report["run_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
