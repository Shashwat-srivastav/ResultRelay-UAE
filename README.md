<div align="center">

# ResultRelay

**A policy-governed agent that refuses to call a critical lab result "communicated" until there is evidence a person received it.**
For walk-in laboratories licensed by the Dubai Health Authority: it keeps *sent*, *accepted by the
gateway*, *delivered*, *acknowledged* and *documented* apart, binds every acknowledgment to the current
result version, and refuses another jurisdiction's rule as binding.

`ITU AI for Good Sandbox Hackathon — UAE` · Healthcare track · agent roles: **policy & legal adviser · innovative AI solution**

![Standard](https://img.shields.io/badge/ITU--T-Y.3172-0ea5e9)
![Data](https://img.shields.io/badge/data-100%25%20synthetic-success)
![Tests](https://img.shields.io/badge/tests-229%20passing-success)
![KB](https://img.shields.io/badge/quotes-63%20verified-success)

</div>

> ⚠️ **Synthetic data, hackathon exercise only.** No real patient data, EHR, SMS gateway or clinical
> claim. ResultRelay does not diagnose, set thresholds, interpret results or give medical advice.

---

## The one-sentence version

A critical result is flagged, the SMS gateway says "accepted", and a dashboard turns green. Nobody knows
whether the patient has it. **ResultRelay will not close the case on a gateway acceptance, will not reuse
an acknowledgment of version 1 for a corrected version 2, and will not message a patient directly about
a genetic result** — DHA's standard routes those to the referring physician.

```console
$ python run_demo.py 4
── SC-04 [controversial] A generic walk-in rule retrieved for a genetic result  (S4-genetic-scope-exclusion)
   FINAL RESULT_FINALIZED                 VERDICT VIOLATION              ✓ expected RESULT_FINALIZED
   policy-blind final → DELIVERY_CONFIRMED
```

## Why the model advises and code decides

| | Node | Who does it | Can it change a case? |
| :--- | :--- | :--- | :--- |
| **Reasoning** | `M` | Five assessors + a policy & legal **reviewer** (TypeSafe Jev) that judges whether the shown evidence supports each proposed action, and which clause governs it ([app/advisers/jev.py](app/advisers/jev.py)) | **No** |
| **Decision** | `P` | A deterministic gate over 18 states and named invariants ([app/orchestration/gate.py](app/orchestration/gate.py)) | **Yes — only this** |

Every model proposal goes through a containment guard before the gate sees it
([app/advisers/guard.py](app/advisers/guard.py)): **residency** (Federal Law 2/2019 Art. 13 — health data
may not be processed outside the State; a synthetic case may use an offshore model, and a real case on the
same endpoint is refused), **grounding** (it may cite only chunks it was shown) and **jurisdiction** (a
comparator can inform a human, never underwrite an action). The gate computes its decision without reading
the proposal; a test asserts the decision is unchanged when a proposal is attached.

In the recorded run, all 23 reviewer proposals passed containment and 22 cite a verified clause. **The
reviewer endorsed none of the 23 workflow actions**: it consistently asks for more evidence before a
first send of a critical result. That is logged as dissent, not acted on, and it is why the gate, not the
model, decides.

## Architecture — ITU-T Y.3172, node for node

| Node (Y.3172 §8.1) | In ResultRelay | AI Readiness 2.0 dimension | Policy source |
| :--- | :--- | :--- | :--- |
| **SRC** | Synthetic result revisions, contacts, channels; the verified corpus | Data/Model Marketplace (1), Contextualization and Regional Impact (4) | DHA ST-28 §11.1 (walk-in tests) |
| **C** | Staged event streams: transport, patient and supervisor events | Level of Integration of AI in Workflows (5) | DHA ST-28 §11.1.1–3 |
| **PP** | Normalised states; report version, action id and provenance preserved | AI & Policies (10) | HL7 FHIR Task, IHE XDW (comparators) |
| **M** | Assessors + Jev policy & legal reviewer over retrieved, jurisdiction-filtered evidence | Collaboration with AI (8), Impacts of Humans in AI Integration (9) | UAE AI Charter (human oversight) |
| **P** | Gate: scope (§13.4 genetic results), version binding, reconcile-before-retry, no false closure | AI & Policies (10), Strategy Alignment (7) | DHA ST-28 §11.1, §13.4 |
| **D** | Mock transport that separates acceptance, delivery and acknowledgment; idempotency keys | Digital Infrastructure (13), Granular Priorities (12) | Federal Law 2/2019 Art. 4, 13 |
| **SINK** | Supervisor queue, React console, hash-chained audit re-verified on read | Human Interface (6), AI for Inclusion (11) | DHA ST-28 §11.1.3 (communication record) |

## The four scenarios — `python run_demo.py`

| # | Scenario | Final state | Verdict | Policy-blind |
| :--- | :--- | :--- | :--- | :--- |
| **SC-01** normal | Genetic result routed to the referring physician | `COMMUNICATION_DOCUMENTED` | `COMPLIANT` | same |
| **SC-02** failure | Primary channel down, no approved fallback | `ESCALATION_REQUIRED` | `INSUFFICIENT_EVIDENCE` | invents a channel → `DELIVERY_CONFIRMED` |
| **SC-03** failure | Corrected result after acknowledgment of version 1 | `CORRECTED_RESULT_ACKNOWLEDGED` | `COMPLIANT` | `ESCALATION_REQUIRED` |
| **SC-04** controversial | Generic walk-in rule retrieved for a genetic result | `RESULT_FINALIZED` (direct path refused) | `VIOLATION` | messages the patient → `DELIVERY_CONFIRMED` |

## Evaluation — `python scripts/run_evaluation.py`

8 scenarios × 11 configurations = 88 runs; seven configurations differ from the full system in exactly
one input.

| Configuration | Fully safe | Assertions |
| :--- | ---: | ---: |
| `resultrelay` | **8/8** | **32/32** |
| `static_rules` (competent hand-written rules) | 6/8 | 30/32 |
| `ablate_no_kb` · `ablate_ack_any` | 6/8 | 30/32 |
| `retrieval_only` | 4/8 | 28/32 |
| `policy_blind` | 3/8 | 27/32 |

What these numbers do not show, said plainly: the scenarios and expectations were written by the same
team that wrote the engine. S1 and S3b separate no configuration. `static_rules` loses only the two
genetic-scope scenarios, because it was built without a genetic rule. Two ablations
(`ablate_no_audit_agent`, `ablate_full_context`) cannot change an outcome by construction.

## Knowledge base — `GET /api/kb/search?q=…&jurisdiction=AE-DU`

**63 quotations from 14 documents**, each with issuing body, jurisdiction, section, printed page and a
claim class; only `BINDING_REQUIREMENT` can block an action, and only sources that bind the case
jurisdiction carry it. **50 are verified against the downloaded official documents** (the quote must
appear on the declared page, or the excerpt is rejected and never indexed); **13 (Federal Law 2/2019,
UAE AI Charter, ADHICS) are verified against recorded transcriptions** of portal pages that refuse
scripted downloads. The served index is pinned by SHA-256 and re-checked on load.

`python scripts/export_itu_kb.py` writes every verified excerpt to `kb/itu_inputdocs/` in the ITU
reference-code InputDocs format; `--ingest PATH/TO/ITUAIReadiness` runs the ITU `ingest.py` (ChromaDB +
Ollama `nomic-embed-text`) with clause-level provenance as metadata.

## Policy and standards gaps — [kb/gap_register.csv](kb/gap_register.csv)

| Gap | Type |
| :--- | :--- |
| No retrieved source sets an acknowledgment clock or a responsible role for patient-direct results with no ordering physician | Unclear responsibility |
| Health rules require a *record of communication*; telecom delivery receipts prove arrival at a handset, never receipt by a person — no instrument joins the two | Coordination (health ↔ telecom) |
| No standard binds an acknowledgment to a specific result revision for patient-direct notification | Standards |
| No route for a patient to report an inaccurate result | Legislative / process |
| Federal 25-year health-record retention (Law 2/2019 Art. 20) is not reflected in lab messaging workflows | Implementation |

Global comparisons used: Joint Commission NPSG.02.03.01 (critical results to the responsible caregiver),
ONC SAFER Guides 2025 (test-results follow-up), HL7 FHIR R5 Task, IHE XDW. PDPL (Federal Decree-Law
45/2021) is cited only for its scope exclusion: **Article 2, exclusion (e)** — health data governed by
its own legislation.

## Run it

```bash
python -m pip install -r requirements.txt
python -m pytest -q                          # 229 tests (one skips unless every source text is cached)
python run_demo.py                           # four scenarios; adviser replays recorded responses offline
python scripts/run_evaluation.py             # 88-run matrix → evaluation/report.md
python -m uvicorn app.main:app --port 8000   # API + built UI on http://127.0.0.1:8000  (docs at /api/docs)
python scripts/fetch_sources.py              # optional: download the official texts and re-verify every quote
```

Live adviser: set `TYPESAFE_API_KEY` and `RESULTRELAY_ADVISE=1`, `RESULTRELAY_ADVISE_PROVIDER=jev`
(PowerShell: `$env:RESULTRELAY_ADVISE='1'`). A local OpenAI-compatible model (Ollama) works through
`RESULTRELAY_ADVISE_URL=http://localhost:11434/v1`. The UI is pre-built in `app/static/app`; rebuild with
`cd web && npm ci && npm run build`. The build has no authentication: bind to 127.0.0.1 and use synthetic
data only.

## Repository

```
app/          gateway: agents/, advisers/ (guard, residency, Jev, OpenAI-compatible), orchestration/ (gate, engine),
              state_machine/, transport/, kb/ (ingest + verified retrieval), audit/, api/, static/ (built UI)
web/          React console (CaseTimeline, Simulator, Standards & gaps, Evaluation, Audit, Decision trace)
kb/           records/ (verified excerpts) · index/ (pinned) · framework/ (Y.3172 + Readiness mappings) · itu_inputdocs/
scenarios/    S1–S7 staged event streams · expected/ (assertions)
evaluation/   report.md · results/latest.json · agent_runs/ (recorded adviser responses)
submission/   technical report · design brief · build scripts
docs/         architecture, REPORT, audit disposition, design notes
tests/        229 tests
```

## License

[MIT](LICENSE). Source documents belong to their issuing bodies and are not redistributed; quotations are
minimal and attributed with section and page.
