"""ResultRelay — the five headline scenarios, end to end, in the terminal.

    python run_demo.py                 # multi-agent council on (recorded replay offline; live if a provider is set)
    python run_demo.py --no-agents     # deterministic path only
    python run_demo.py 2               # one scenario
    RESULTRELAY_AGENT_PROVIDER=mistral python run_demo.py      # live on Mistral (MISTRAL_API_KEY, e.g. in .env)
    RESULTRELAY_AGENT_PROVIDER=ollama RESULTRELAY_AGENT_MODEL=qwen2.5:14b python run_demo.py   # fully local

At every decision point the council runs: network (TDRA lens), health (DHA lens) and policy & legal
reviewer agents answer from their own clauses and may use read-only tools; a fact check and a critic
agent review every answer and send flagged ones back for one revision; a coordinator agent resolves; a
rule cross-check recomputes the conflicts. The deterministic gate (P node) decides without reading any of
it. The policy-blind baseline runs on the same events. Exits 1 on a final-state mismatch.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.multiagent.providers import load_dotenv  # noqa: E402

load_dotenv()
if "--no-agents" not in sys.argv and not os.environ.get("RESULTRELAY_AGENT_PROVIDER"):
    # Offline default: replay the recorded run of the recommended allocation — mandate agents on
    # Mistral ministral-14b, critic and coordinator on Jev (a different model family checks the agents).
    os.environ["RESULTRELAY_AGENT_PROVIDER"] = "replay"
    os.environ.setdefault("RESULTRELAY_AGENT_REPLAY_FROM", "mistral")
    for role in ("CRITIC", "COORDINATOR"):
        os.environ.setdefault(f"RESULTRELAY_{role}_PROVIDER", "replay")
        os.environ.setdefault(f"RESULTRELAY_{role}_REPLAY_FROM", "jev")

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
    ("SC-05", "failure", "S8-accepted-never-delivered", "ESCALATION_REQUIRED",
     "The gateway accepts the SMS and nothing else ever happens. The policy-blind baseline records delivery; ResultRelay escalates to a person after the configured window."),
]


def _g(m: dict, role: str, key: str, field: str):
    return m.get(role, {}).get("answers", {}).get(key, {}).get(field)


def main(argv: list[str]) -> int:
    picks = {int(a) for a in argv if a.isdigit()}
    print("\nSYNTHETIC DATA — hackathon exercise only. Not a clinical service or a compliance determination.")
    from app.multiagent.providers import ROLES, configured

    roles = {r: configured(r) for r in ROLES} if "--no-agents" not in sys.argv else {}
    print("council: " + (" · ".join(f"{r} {p.label}" for r, p in roles.items() if p) or "off") + "\n")
    matched, out = 0, []
    tot = {"decision_points": 0, "answers": 0, "flagged": 0, "corrected": 0, "upheld": 0, "disputed": 0,
           "tool_calls": 0, "coordinator_checked": 0, "coordinator_matches_rules": 0, "escalations": 0, "unavailable": 0}
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
        for st in rt.steps:
            d = st.get("agent_deliberation")
            if not d:
                continue
            m, c, cs = d["messages"], d["coordinator"].get("answers", {}), d["critique_summary"]
            tot["decision_points"] += 1
            tot["answers"] += sum(1 for x in m.values() if x.get("answers"))
            tot["unavailable"] += sum(1 for x in m.values() if x.get("status") in ("UNAVAILABLE", "REFUSED_RESIDENCY"))
            tot["flagged"] += cs["flagged"]
            tot["corrected"] += cs["corrected"]
            tot["disputed"] += len(cs["disputed"])
            tot["upheld"] += sum(1 for rv in d["reviews"].values() if rv.get("outcome") == "UPHELD")
            tot["tool_calls"] += len(d["tool_calls"])
            if d["coordinator_matches_rules"] is not None:
                tot["coordinator_checked"] += 1
                tot["coordinator_matches_rules"] += bool(d["coordinator_matches_rules"])
            tot["escalations"] += bool(d["escalate"])
            print(f"   step {st['step']:>2} {d['action_under_review']:<20} gate → {st['enforced_action']:<20} "
                  f"network {_g(m, 'network', 'delivery_status', 'choice')} · health {_g(m, 'health', 'obligation', 'choice')} "
                  f"· reviewer objection p={_g(m, 'reviewer', 'objection', 'noul')}")
            notes = [f"{r} {rv['outcome'].lower()}" + (f" ({rv['fact_check'][0]})" if rv.get("fact_check") else "")
                     for r, rv in d["reviews"].items() if rv.get("flagged")]
            print(f"           critic: {'; '.join(notes) or 'all answers accepted'}"
                  f"{' · tools ' + ','.join(x['tool'] for x in d['tool_calls']) if d['tool_calls'] else ''}")
            print(f"           coordinator {c.get('resolution', {}).get('choice')} / {c.get('conflict', {}).get('choice')}"
                  f" · rule check {d['rule_conflicts'] or 'none'}"
                  f"{'' if d['coordinator_matches_rules'] in (None, True) else '  ⚠ coordinator disagrees with the rule check'}")
        chain = rt.audit.verify_chain()[0] if rt.audit else None
        print(f"   audit {len(rt.audit.entries)} entries, hash chain valid={chain}\n")
        out.append({"scenario": sid, "source": scen_id, "final": final, "matched": ok,
                    "deliberations": [s.get("agent_deliberation") for s in rt.steps if s.get("agent_deliberation")]})
    if tot["decision_points"]:
        print(f"council: {tot['decision_points']} decision points, {tot['answers']} agent answers, {tot['tool_calls']} tool calls; "
              f"critic flagged {tot['flagged']} → {tot['corrected']} corrected, {tot['upheld']} upheld, {tot['disputed']} disputed; "
              f"coordinator matched the rule check {tot['coordinator_matches_rules']}/{tot['coordinator_checked']}; "
              f"{tot['escalations']} supervisor-review requests; {tot['unavailable']} unavailable")
    (ROOT / "evaluation" / "demo_run.json").write_text(json.dumps({"totals": tot, "runs": out}, indent=1, default=str), encoding="utf-8")
    print(f"{matched}/{len(out)} matched expected")
    return 0 if matched == len(out) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
