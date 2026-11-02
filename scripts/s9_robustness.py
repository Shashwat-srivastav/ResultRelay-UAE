"""How reliably does the agent council catch a reply that contradicts the record — and how often does it
escalate a genuine reply? (S9 robustness: detection rate and false-positive escalation rate.)

    RESULTRELAY_AGENT_PROVIDER=mistral RESULTRELAY_AGENT_MODEL=ministral-14b-2512 RESULTRELAY_REVIEWER_PROVIDER=jev \
        python scripts/s9_robustness.py --repeats 3

Each variant is S9 with a different reply text (English and Arabic): five replies that contradict the
structured acknowledgment (someone other than the patient) and five genuine replies from the patient. Every
variant runs in the resultrelay_council configuration, live, --repeats times. A contradicting reply is
DETECTED when the case ends in ESCALATION_REQUIRED; a genuine reply is a FALSE POSITIVE when it does. The
rules-only configuration is run once per variant for reference. Model answers are recorded under
evaluation/robustness_runs/ (kept apart from the demo recordings). Reply texts were written by the authors.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("RESULTRELAY_AGENT_RUNS_DIR", str(ROOT / "evaluation" / "robustness_runs"))
sys.path.insert(0, str(ROOT))

from app.orchestration.engine import load_scenario, run_scenario  # noqa: E402

CONTRADICTING = {
    "C1-daughter-en": "This is his daughter. My father is in hospital abroad and does not have his phone. I will tell him when he calls.",
    "C2-wrong-number-en": "Wrong number. I do not know anyone by that name.",
    "C3-colleague-en": "I am his colleague. He left his phone at the office. I will let him know tomorrow.",
    "C4-wife-ar": "أنا زوجته، هو مسافر وليس معه هاتفه. سأخبره لاحقاً.",
    "C5-reception-en": "This is the clinic reception desk. The patient gave us this number. We will pass the message on.",
}
GENUINE = {
    "G1-going-now-en": "Received, thank you. I am going to the emergency department now.",
    "G2-call-doctor-en": "Got it, thanks. I will call my doctor this morning.",
    "G3-received-ar": "تم الاستلام، شكراً. سأذهب إلى الطبيب اليوم.",
    "G4-understood-en": "OK, understood. I am booking an appointment for today.",
    "G5-this-is-me-en": "Yes, this is me. Thank you for letting me know.",
}


def variant(base: dict, key: str, text: str) -> dict:
    s = copy.deepcopy(base)
    s["scenario_id"] = f"S9v-{key}"
    for st in s["steps"]:
        if st.get("type") == "clinical.acknowledgment":
            st["summary"] = ("Reply from the registered number, marked by the gateway as an acknowledgment from a verified "
                             f"number: '{text}'")
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args()
    base = load_scenario("S9-reply-from-someone-else")
    rows, tally = [], {"contradicting": [0, 0], "genuine": [0, 0]}
    for group, texts in (("contradicting", CONTRADICTING), ("genuine", GENUINE)):
        for key, text in texts.items():
            spec = variant(base, key, text)
            rules = run_scenario(spec, "resultrelay").state.value
            finals = []
            for _ in range(a.repeats):
                rt = run_scenario(spec, "resultrelay_council")
                finals.append(rt.state.value)
                esc = rt.state.value == "ESCALATION_REQUIRED"
                tally[group][0] += esc
                tally[group][1] += 1
            rows.append({"variant": key, "group": group, "reply": text, "rules_only": rules, "council_runs": finals})
            print(f"{key:<22} rules={rules:<26} council={finals}", flush=True)
    det = tally["contradicting"]
    fp = tally["genuine"]
    summary = {"repeats": a.repeats, "detected": det[0], "contradicting_runs": det[1],
               "false_positives": fp[0], "genuine_runs": fp[1],
               "detection_rate": round(det[0] / det[1], 3) if det[1] else None,
               "false_positive_rate": round(fp[0] / fp[1], 3) if fp[1] else None,
               "providers": {k: os.environ.get(k) for k in ("RESULTRELAY_AGENT_PROVIDER", "RESULTRELAY_AGENT_MODEL",
                                                           "RESULTRELAY_REVIEWER_PROVIDER")}}
    out = ROOT / "evaluation"
    (out / "s9_robustness.json").write_text(json.dumps({"summary": summary, "runs": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# S9 robustness: does the council catch a reply from someone else, without escalating genuine replies?", "",
          f"Council: analysts {summary['providers']['RESULTRELAY_AGENT_PROVIDER']} `{summary['providers']['RESULTRELAY_AGENT_MODEL']}`, "
          f"reviewer {summary['providers']['RESULTRELAY_REVIEWER_PROVIDER']}; {a.repeats} live runs per reply; reply texts written by the authors.", "",
          f"- **Detection rate** (reply contradicts the record → escalated): **{det[0]}/{det[1]}**",
          f"- **False-positive rate** (genuine reply → escalated): **{fp[0]}/{fp[1]}**",
          "- Rules only: never escalates either kind (it reads only the structured acknowledgment).",
          "- Limits: models run at temperature 0, so repeats test run-to-run variation of the hosted models, not sampling diversity; the variety comes from the ten reply texts. Ten authored replies are a small, non-adversarial sample. Only the last repeat's answers are kept in `evaluation/robustness_runs/`.", "",
          "| Variant | Group | Reply | Rules only | Council runs |", "| :--- | :--- | :--- | :--- | :--- |"]
    for r in rows:
        md.append(f"| {r['variant']} | {r['group']} | {r['reply']} | `{r['rules_only']}` | "
                  + ", ".join(f"`{x}`" for x in r["council_runs"]) + " |")
    (out / "s9_robustness.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
