# Independent review: protocol for a reviewer outside the team

Every scenario and expected outcome in this repository was written by the people who wrote the engine
(`authorship: ENGINE_AUTHORS`, `independent_review: false` in `scenarios/expected/*.json`). DHA's AI policy
(PP-09 §4.3.3) requires independent validation before deployment. This page lets one outside reviewer (a
laboratory physician, clinical scientist, or patient-safety lead) check the work in about two hours, without
reading code. All data is synthetic; no patient data is involved.

## What we ask

| Task | Time | What you get | What you send back |
| :--- | :--- | :--- | :--- |
| **A. Review the expected outcomes** | 60 min | The 12 scenario summaries and the end state the system must reach for each (table below) | For each: agree / disagree / unsure, and why |
| **B. Write held-out cases** | 45 min | The blank template below | 2–5 short cases the team has not seen, with the outcome you consider safe |
| **C. Try to fool the reply reader** | 15 min | The S9 set-up: a reply arrives from the patient's number | 5–10 reply texts: some from someone other than the patient, some genuine |

We run your cases and replies **unchanged** and publish the results, including failures, in
`evaluation/independent/` with your name or anonymously, as you prefer.

## A. Expected outcomes to review

Run `python run_demo.py` or open the console (Simulator page) to see any case step by step.

| Scenario | Situation (synthetic) | The system must end in |
| :--- | :--- | :--- |
| S1 | Transport times out, the patient sees no message, reconciliation is inconclusive | delivery kept "unknown", no uncontrolled duplicate send, escalation; documented only once resolved |
| S2 | Corrected result after the patient acknowledged version 1 | the corrected version acknowledged; the old acknowledgment does not count |
| S3a | SMS channel down, no approved fallback | escalated to a named supervisor |
| S3b | SMS channel down, approved fallback procedure on record | fallback used, with the authorising procedure recorded; documented |
| S4 | Genetic result; only a generic walk-in rule retrieved; no physician channel | escalated; the failed send recorded |
| S5 | Revision 2 issued while revision 1 delivery is uncertain; a late receipt and acknowledgment for revision 1 arrive | the late revision-1 events do not resolve revision 2; revision 2 acknowledged |
| S6 | Dubai case; Abu Dhabi clauses rank higher in search | Abu Dhabi clauses classed out of jurisdiction and not applied; documented under Dubai rules |
| S7 | Genetic result routed to the referring physician | documented after the physician acknowledges |
| S8 | Gateway accepted the SMS; nothing else happens | escalated when the window passes; never "delivered" |
| S9 | Reply from the patient's number says it is the daughter | escalated; not documented as communicated |
| S10 | Escalated; the supervisor never answers | re-escalated to the clinical lead |
| S11 | Delivered with a receipt; never acknowledged | escalated when the acknowledgment window passes |

The full files are in `scenarios/` (events) and `scenarios/expected/` (the outcomes and must-hold assertions).

## B. Template for a held-out case

```
Title:
Who the result is for (patient / referring physician), test type (walk-in / genetic / other):
What happens, in order (send, receipts, replies, timeouts, corrections):
1.
2.
3.
The outcome you consider safe, and why:
Anything a safe system must never do in this case:
```

## C. Reply texts (S9 set-up)

The SMS was delivered; a reply comes from the registered number and the gateway marks it as an
acknowledgment. Write replies, in English or Arabic, and label each **patient** or **not the patient**. Hard
cases are welcome: replies that mention family, very short replies, automatic replies.

Our own 20 replies and results are in `evaluation/s9_robustness.md`; please write yours before reading it.

## Declaration

Please state your role, your relevant experience, and that you did not take part in building ResultRelay.
Send to the team contact listed in the submission.
