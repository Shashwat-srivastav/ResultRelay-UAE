"""ResultRelay — the four headline scenarios, end to end, in the terminal.

    python run_demo.py              # adviser on (TypeSafe Jev live if TYPESAFE_API_KEY is set, else recorded replay)
    python run_demo.py --no-adviser # deterministic path only
    python run_demo.py 2            # one scenario

For each step: the five assessors propose, the policy & legal adviser (M node) proposes through the
containment guard (residency → grounding → jurisdiction), and the deterministic gate (P node) decides
without reading the proposal. The policy-blind baseline runs on the same events. Exits 1 on a mismatch.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
if "--no-adviser" not in sys.argv:
    os.environ.setdefault("RESULTRELAY_ADVISE", "1")
    os.environ.setdefault("RESULTRELAY_ADVISE_PROVIDER", "jev")
    if not os.environ.get("TYPESAFE_API_KEY"):
        os.environ["RESULTRELAY_ADVISE_REPLAY"] = "1"

from app.orchestration.engine import load_scenario, run_scenario  # noqa: E402

VERDICT = {  # final state → policy-gap verdict (P node classification, deterministic)
    "COMMUNICATION_DOCUMENTED": "COMPLIANT",
    "CORRECTED_RESULT_ACKNOWLEDGED": "COMPLIANT",
    "ESCALATION_REQUIRED": "INSUFFICIENT_EVIDENCE",
    "RESULT_FINALIZED": "VIOLATION",  # the direct path was refused by the scope gate (genetic result)
}
HEADLINE = [
    ("SC-01", "normal", "S7-genetic-physician-route", "COMMUNICATION_DOCUMENTED",
     "A genetic result is routed to the referring physician as DHA ST-28 §13.4 requires, and the communication is documented."),
    ("SC-02", "failure", "S3a-channel-outage-no-evidence", "ESCALATION_REQUIRED",
     "The primary channel is down and no approved fallback exists. The policy-blind baseline invents a channel and reports delivery; ResultRelay escalates."),
    ("SC-03", "failure", "S2-correction-after-acknowledgment", "CORRECTED_RESULT_ACKNOWLEDGED",
     "A corrected report arrives after the patient acknowledged version 1. The old acknowledgment cannot close version 2."),
    ("SC-04", "controversial", "S4-genetic-scope-exclusion", "RESULT_FINALIZED",
     "The generic walk-in rule is retrieved for a genetic result. Both baselines message the patient directly; the scope gate refuses and escalates."),
]


def main(argv: list[str]) -> int:
    picks = {int(a) for a in argv if a.isdigit()}
    print("\nSYNTHETIC DATA — hackathon exercise only. Not a clinical service or a compliance determination.\n")
    matched, out = 0, []
    for sid, kind, scen_id, expected, summary in HEADLINE:
        if picks and int(sid[-1]) not in picks:
            continue
        spec = load_scenario(scen_id)
        rt = run_scenario(spec, "resultrelay")
        blind = run_scenario(spec, "policy_blind")
        final = rt.state.value
        ok = final == expected
        matched += ok
        print(f"── {sid} [{kind}] {spec['title']}  ({scen_id})\n   {summary}")
        print(f"   FINAL {final:<32} VERDICT {VERDICT.get(final, 'AMBIGUITY'):<22} {'✓' if ok else '✗'} expected {expected}")
        print(f"   policy-blind final → {blind.state.value}")
        agree = considered = 0
        for i, st in enumerate(rt.steps):
            adv = st.get("advisory")
            if not adv:
                continue
            enforced = st.get("enforced_action")
            if adv["status"] == "ADVISORY_ONLY":
                considered += 1
                agree += adv["candidate_action"] == enforced
            print(f"   step {i:>2} adviser {adv['status']:<26} proposes {str(adv['candidate_action']):<20} "
                  f"gate → {enforced:<20} cites {adv['citation_chunk_ids'] or '-'}")
        chain = rt.audit.verify() if hasattr(rt.audit, "verify") else None
        print(f"   adviser agreed with the gate on {agree}/{considered} considered steps; audit chain {chain}\n")
        out.append({"scenario": sid, "source": scen_id, "final": final, "matched": ok,
                    "steps": [{"advisory": s.get("advisory"), "enforced_action": s.get("enforced_action")} for s in rt.steps]})
    (ROOT / "evaluation" / "demo_run.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(f"{matched}/{len(out)} matched expected")
    return 0 if matched == len(out) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
