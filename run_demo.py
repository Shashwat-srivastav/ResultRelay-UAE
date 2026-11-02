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
    # Offline default: replay the recorded run of the recommended allocation — analysts on
    # Mistral ministral-14b, the adversarial reviewer on Jev (a different model family challenges the analysts).
    os.environ["RESULTRELAY_AGENT_PROVIDER"] = "replay"
    os.environ.setdefault("RESULTRELAY_AGENT_REPLAY_FROM", "mistral")
    for role in ("REVIEWER",):
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
    ("SC-04", "controversial", "S4-genetic-scope-exclusion", "ESCALATION_REQUIRED",
     "The generic walk-in rule is retrieved for a genetic result. Both baselines message the patient directly; ResultRelay routes it to the physician, finds no physician channel, logs the failed send and escalates."),
    ("SC-05", "failure", "S8-accepted-never-delivered", "ESCALATION_REQUIRED",
     "The gateway accepts the SMS and nothing else ever happens. The policy-blind baseline records a delivery that never happened; ResultRelay never records delivery and escalates to a person after the configured window."),
    ("SC-06", "agents", "S9-reply-from-someone-else", "ESCALATION_REQUIRED",
     "Delivered and 'acknowledged' from a verified number, but the reply says it is the patient's daughter. Rules close the case; the agents read the words and escalate."),
    ("SC-07", "failure", "S10-escalation-nobody-answers", "ESCALATION_REQUIRED",
     "Escalated to the supervisor, who never answers. Past the deadline the escalation is raised to the clinical lead (tier 2), not left open."),
    ("SC-08", "failure", "S11-delivered-not-acknowledged", "ESCALATION_REQUIRED",
     "The SMS is delivered with a receipt, but nobody acknowledges it. When the acknowledgment window passes, ResultRelay escalates; a receipt is not a person. (This scenario exposed a clock bug that had disabled the rule.)"),
]


def _g(m: dict, role: str, key: str, field: str):
    return m.get(role, {}).get("answers", {}).get(key, {}).get(field)


def main(argv: list[str]) -> int:
    picks = {int(a) for a in argv if a.isdigit()}
    print("\nSYNTHETIC DATA — hackathon exercise only. Not a clinical service or a compliance determination.")
    from app.multiagent.providers import ROLES, configured  # noqa: E402

    roles = {r: configured(r) for r in ROLES} if "--no-agents" not in sys.argv else {}
    print("council: " + (" · ".join(f"{r} {p.label}" for r, p in roles.items() if p) or "off") + "\n")
    matched, out = 0, []
    tot = {"decision_points": 0, "answers": 0, "tool_calls": 0, "flagged": 0, "corrected": 0, "upheld": 0, "disputed": 0,
           "objections": 0, "objections_rejected": 0, "escalations": 0, "institution_invoked": 0, "gaps": 0, "unavailable": 0}
    for sid, kind, scen_id, expected, summary in HEADLINE:
        if picks and int(sid[-1]) not in picks:
            continue
        spec = load_scenario(scen_id)
        rt = run_scenario(spec, "resultrelay_council" if "--no-agents" not in sys.argv else "resultrelay")
        rules_only = run_scenario(spec, "resultrelay") if "--no-agents" not in sys.argv else rt
        blind = run_scenario(spec, "policy_blind")
        final = rt.state.value
        ok = final == expected
        # The verdict is about the policy question, not only the end state: a direct path the clauses prohibit
        # (scope routed away from the patient) is a VIOLATION prevented, whatever happened next.
        scope_blocked = any((s.get("policy_retrieval") or {}).get("scope_permitted") is False for s in rt.steps)
        verdict = "VIOLATION" if scope_blocked and final not in ("COMMUNICATION_DOCUMENTED",) else VERDICT.get(final, "AMBIGUITY")
        matched += ok
        print(f"── {sid} [{kind}] {spec['title']}  ({scen_id})\n   {summary}")
        print(f"   FINAL {final:<32} VERDICT {verdict:<22} {'✓' if ok else '✗'} expected {expected}")
        print(f"   policy-blind final → {blind.state.value} · rules only (no agents) → {rules_only.state.value}")
        for st in rt.steps:
            d = st.get("agent_deliberation")
            if not d:
                continue
            m, sm = d["messages"], d["summary"]
            tot["decision_points"] += 1
            tot["answers"] += sum(1 for x in m.values() if x.get("answers"))
            tot["unavailable"] += sum(1 for x in m.values() if x.get("status") in ("UNAVAILABLE", "REFUSED_RESIDENCY"))
            tot["tool_calls"] += len(d["tool_calls"])
            tot["flagged"] += sm["flagged"]
            tot["corrected"] += sm["corrected"]
            tot["upheld"] += sm["upheld"]
            tot["disputed"] += len(sm["disputed"])
            obj = _g(m, "reviewer", "objection", "choice")
            tot["objections"] += obj not in (None, "NONE")
            tot["objections_rejected"] += sm["objection_rejected"]
            tot["escalations"] += d["decision"] == "ESCALATE"
            tot["institution_invoked"] += sm["institution_invoked"]
            gap = _g(m, "analyst", "gap", "choice")
            tot["gaps"] += gap not in (None, "NONE")
            print(f"   step {st['step']:>2} {d['action_under_review']:<20} gate → {st['enforced_action']:<20} "
                  f"analyst {_g(m, 'analyst', 'obligation', 'choice')} (settled p={_g(m, 'analyst', 'settled', 'noul')}, gap {gap})")
            if sm["institution_invoked"]:
                print(f"           TDRA lens: telecom clause covers this message p={_g(m, 'institution', 'telecom_covers', 'noul')}"
                      f" · closest {_g(m, 'institution', 'clause', 'choice')}")
            print(f"           reviewer objection {obj} · own reading {_g(m, 'reviewer', 'own_reading', 'choice')}"
                  + (" (objection rejected by code)" if sm["objection_rejected"] else ""))
            notes = [f"{r} {rv['outcome'].lower()}" + (f" ({rv['checks'][0]})" if rv.get("checks") else "")
                     for r, rv in d["reviews"].items() if r != "reviewer" and rv.get("flagged")]
            if notes:
                print(f"           assurance: {'; '.join(notes)}")
            print(f"           orchestrator {d['decision']}" + (f" ▶ {d['escalation'][:120]}" if d["escalation"] else "")
                  + (f" · conflicts {d['conflicts']}" if d["conflicts"] else ""))
        chain = rt.audit.verify_chain()[0] if rt.audit else None
        from app.audit.log import sign_checkpoint

        cp = sign_checkpoint(rt.audit)
        print(f"   audit checkpoint head {cp['head'][:12]}… " + ("signed (HMAC-SHA256)" if cp["signature"] else "unsigned: set RESULTRELAY_AUDIT_KEY"))
        print(f"   audit {len(rt.audit.entries)} entries, hash chain valid={chain}\n")
        out.append({"scenario": sid, "source": scen_id, "final": final, "matched": ok,
                    "deliberations": [s.get("agent_deliberation") for s in rt.steps if s.get("agent_deliberation")]})
    if tot["decision_points"]:
        print(f"council: {tot['decision_points']} decision points, {tot['answers']} agent answers, {tot['tool_calls']} tool calls, "
              f"TDRA lens invoked {tot['institution_invoked']}x; assurance flagged {tot['flagged']} → {tot['corrected']} corrected, "
              f"{tot['upheld']} upheld, {tot['disputed']} disputed; reviewer objections {tot['objections']} "
              f"({tot['objections_rejected']} rejected by code); {tot['gaps']} policy gaps surfaced; "
              f"{tot['escalations']} escalations; {tot['unavailable']} unavailable")
    (ROOT / "evaluation" / "demo_run.json").write_text(json.dumps({"totals": tot, "runs": out}, indent=1, default=str), encoding="utf-8")
    print(f"{matched}/{len(out)} matched expected")
    return 0 if matched == len(out) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
