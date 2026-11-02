# Judge-critic audit: disposition against the current repository

> This file records the disposition as of 2 Nov 2026; for current counts and results, `README.md` and `evaluation/report.md` are authoritative.

*Re-checked on 2 November 2026 against the working tree of this repository. This replaces the
earlier disposition of the first red-team audit (C-/H- findings), which described a 14-source,
63-excerpt build that no longer exists.*

The independent judge-critic audit raised findings in three series: **RJ-** (judge view) and
**RT-** (technical view) in the first pass, and **N-** (new findings) in the second pass, which
also re-scored the RJ/RT items. Many items were fixed after the second pass ran, so every row below
was re-checked against the code and data as they are now. The rule for this table: **a finding is
`FIXED` only if the fix can be pointed to in a named file, function or field.** A fix whose effect
can only be shown by an evaluation run that has not been regenerated yet is `PARTIAL`.

Statuses: `FIXED`; `PARTIAL` (part done, or done in code but not yet shown in results or in every
document); `OPEN` (not done); `LIMIT-DISCLOSED` (cannot be fixed inside the repo and is stated as
a limit); `NOTE` (an observation, not a defect).

This document gives no test counts or evaluation figures, because they are being regenerated. For
results see `README.md` and `evaluation/report.md`. Note: at the time of writing, many of the fixes
cited below are in the working tree but **not yet committed** (HEAD `bcf3593`; for example
`kb/records/G6_*.yaml` to `G9_*.yaml`, `kb/records/U10_*.yaml` and `scenarios/S9-*.json` are
untracked). They have to be committed for a clone to show them.

## Summary

| status | RJ | RT | N | total |
|---|---|---|---|---|
| FIXED | 12 | 14 | 4 | **30** |
| PARTIAL | 9 | 7 | 5 | **21** |
| OPEN | 3 | 3 | 3 | **9** |
| LIMIT-DISCLOSED | 2 | 3 | 0 | **5** |
| NOTE | 1 | 5 | 0 | **6** |
| total | 27 | 32 | 12 | **71** |

## RJ series (judge view)

| id | sev. | finding (one line) | status | evidence in the current repo |
|---|---|---|---|---|
| RJ-01 | blocker | The report lacked the required FAQ sections (requirements, Y.3172 table, Readiness table, steps, gaps). | FIXED | `submission/ResultRelay_ITU_Submission.docx` / `.pdf` contain the requirements, the node table (SRC … SINK with a policy column), steps and gaps table. |
| RJ-02 | blocker | There was no AI agent; by default no model ran and the five assessors were rules. | FIXED | `app/multiagent/council.py`: two LLM analysts and an LLM adversarial reviewer; `CONFIGS["resultrelay_council"]` in `engine.py`; a council ESCALATE opens a real escalation (`Orchestrator.escalate`). The default is recorded answers (`RECOMMENDED_REPLAY`); the five assessors are still rules, by design. |
| RJ-03 | blocker | Judges could not get or run the repo: no git remote, uncommitted restructure. | OPEN | `git remote -v` is empty; the submission still reads `github.com/<your-username>/resultrelay`; current fixes are uncommitted (see note above). |
| RJ-04 | blocker | The ITU reference pipeline (ChromaDB + Ollama) was not used. | PARTIAL | `scripts/export_itu_kb.py --ingest` runs the ITU `ingest.py`; `app/kb/vector.py` ranks with `nomic-embed-text`. But `kb/chroma/` is git-ignored and the default engine is BM25 (`RESULTRELAY_RETRIEVAL=hybrid` is opt-in). |
| RJ-05 | major | No institutional-participant agent and no protocol between agents with separate mandates. | FIXED | `MANDATES["institution"]` (TDRA lens; sources U8, U10, G6) in `council.py`; protocol in `Council.deliberate`: analyst claims → reviewer challenge → code assurance → one feedback round → `orchestrate()`. |
| RJ-06 | major | The repo argued against chain-of-thought tracing and said there was no model to reason. | FIXED | `run_trace` docstring in `app/api/routes.py` now describes agent messages with typed judgment, probability, cited clause and rationale; the phrase "no model to reason" no longer occurs in the repo. |
| RJ-07 | major | The Readiness mapping used the wrong set of dimensions. | FIXED | `kb/framework/ai_readiness_mapping.csv` rows R01–R13 use the 13 dimensions from the ITU reference code (`dimensions.json`). |
| RJ-08 | major | The Y.3172 mapping was a list of modules; its M node had no model. | FIXED | `kb/framework/itu_y3172_mapping.csv` Y4 (M) = the LLM analysts and reviewer in `council.py` / `providers.py`; the submission node table carries a per-node policy column. |
| RJ-09 | major | The PDPL health-data exclusion was cited as Article 3; it is Article 2(e). | FIXED | `kb/source_register.csv` U2: "EXCLUDED for health data by its own Article 2, exclusion (e)". |
| RJ-10 | major | "All quotations machine-verified against the official source" was false for U1, U5, AD2. | PARTIAL | Register classes U1, U5, AD2 as `VERIFIED_TRANSCRIPTION`; readiness R02 no longer claims it. `submission/DESIGN-BRIEF.md` line 11 still says "63 quotations from 14 documents machine-checked against their source pages". |
| RJ-11 | major | Coverage missed national AI/digital/cyber strategies and institutional mandates. | PARTIAL | Added U10 (Telecom Law, Art. 13 TDRA mandate) and U6 (DHA AI policy). Still absent: UAE National Strategy for AI 2031 (R07 limitation), a cyber or digital-government strategy, a DHA establishment law. See `kb/sources/MANUAL_RETRIEVAL.md`. |
| RJ-12 | major | Ordinary questions missed key articles; Arabic queries returned nothing. | PARTIAL | `ARABIC_GLOSSARY` / `expand_arabic` in `app/kb/retriever.py`: BM25 on "نقل البيانات الصحية خارج الدولة" now ranks `U1-art13-localisation` first. The paraphrase "send health data abroad cloud" still misses Art. 13 under default BM25 (see RT-25). |
| RJ-13 | major | "Sent is not delivered" was never shown to matter. | FIXED | `scenarios/S8-accepted-never-delivered.json`; its expectation requires `ESCALATION_REQUIRED` and `no_delivery_without_matched_receipt`. |
| RJ-14 | major | The advantage over rules came from a hand-typed boolean the rules baseline lacked. | FIXED | `RuntimeConfig.hardcoded_genetic_rule`; `static_rules` sets it `True`, and the engine routes a genetic case to the physician when no clause is retrieved (`hard_genetic` in `Orchestrator.step`). |
| RJ-15 | major | The gap register read like a search log; weak or missing comparators. | PARTIAL | GR-05 now cites G7 (CLIA) and G1; GR-13 retired. Still: 4 of 18 rows `NEEDS_VERIFICATION`; GR-06, GR-14, GR-18 have no comparator ("None located/retrieved"). |
| RJ-16 | major | Global examples were narrow (US-only or technical). | FIXED | Register and KB now include G5 (RCPath, UK), G6 (ETSI TS 123 040), G7 (CLIA), G8 (EU AI Act), G9 (Saudi PDPL). G8 is verified against a third-party copy. |
| RJ-17 | major | The telecom and digital-government layer was missing. | PARTIAL | U8 (TDRA Mobile Spam, third-party copy), U10 (Telecom Law Art. 13) and the TDRA-lens analyst. No digital-government or A2P/sender-ID instrument from a TDRA domain. |
| RJ-18 | major | Identity shifts between documents; the main contribution is country-specific. | PARTIAL | Identity is consistent ("walk-in labs licensed by DHA"), but the submission still frames requirements around DHA ST-28 (11 mentions in the docx). Not changed in this pass. |
| RJ-19 | major | The paper contradicted itself on ADHICS / AI Charter being absent. | FIXED | The submission no longer says they are absent; register lists AD2 and U5 as transcriptions. |
| RJ-20 | major | The README was stale on numbers and paths. | OPEN | At the time of writing `README.md` still says 248 tests (badge and two other places), "The four scenarios", "9 scenarios × 11 configurations" and "82 quotations from 18 documents"; the repo has 12 scenario files, 12 configurations, 96 quotations, 24 sources. README is being regenerated. |
| RJ-21 | major | Judges could not inject error events at runtime. | FIXED | `POST /api/runs/{run_id}/events` (`inject_event` in `app/api/routes.py`) validates against `EventType`, audits `event.injected`, runs `orchestrator.step`. |
| RJ-22 | major | Problem size never measured; why AI is needed never argued. | LIMIT-DISCLOSED | The submission quotes ONC SAFER and states "we found no published UAE figure for failed patient-direct notifications, itself a gap". S9 is the case for agents (`requires_council: true`). No local failure-rate estimate exists. |
| RJ-23 | minor | Residency treated `.ae` or loopback as in-country and ignored the implementing resolution. | LIMIT-DISCLOSED | `app/advisers/residency.py`: decisions are marked `nominal`; an operator address check (`RESULTRELAY_RESIDENCY_RESOLVED_IPS` / `_AE_CIDRS`) overrides the name; MR 51/2021 is sent to a person. Egress is not observed. |
| RJ-24 | minor | Register fields corrupted; PDPL kept as binding for a case it excludes. | PARTIAL | U2 relabelled as excluded. `local_file_path` still mixes `kb/records/*.yaml` (e.g. S1, U6, U8) and `kb/.sources/*.txt` (U1–U5, AD2). |
| RJ-25 | minor | No Arabic support. | PARTIAL | Arabic queries via `ARABIC_GLOSSARY`. No Arabic quotation stored (U10 limitations: Arabic PDF extracts with broken glyphs); UI is English; U2 is an unofficial translation. |
| RJ-26 | minor | Effort spent on 3-D pipeline and design documents. | NOTE | `web/package.json` still depends on `three`; `docs/design/` still present. |
| RJ-27 | minor | The evaluation only shows the system agrees with itself. | OPEN | All 12 files in `scenarios/expected/` have `authorship: ENGINE_AUTHORS`, `independent_review: false`. No held-out set. |

## RT series (technical view)

| id | sev. | finding (one line) | status | evidence in the current repo |
|---|---|---|---|---|
| RT-01 | blocker | KB not built with the ITU reference stack; no vectors. | PARTIAL | As RJ-04: `scripts/export_itu_kb.py`, `app/kb/vector.py`; store not shipped (`kb/chroma/` in `.gitignore`); BM25 default. |
| RT-02 | blocker | A clean clone cannot re-verify quotations: sources are not scriptable. | PARTIAL | `tests/test_kb.py` skips with a reason when the cache is absent; `scripts/fetch_sources.py` marks U1, U10, G8 `kind: manual`; U5 and AD2 have no entry in `SOURCES` at all. Manual steps now documented in `kb/sources/MANUAL_RETRIEVAL.md`. |
| RT-03 | blocker | The restructure was staged but not committed. | PARTIAL | The `app/` layout is committed. At the time of writing the working tree again holds uncommitted fixes and untracked records (G6–G9, U10, S9). |
| RT-04 | blocker | No AI agent exercised anywhere; the evaluation called no model. | FIXED | `resultrelay_council` is in `CONFIGS`, and `app/evaluation/runner.py` runs all of `CONFIGS` by default; recorded model answers are replayed (`providers.Provider.ask`). |
| RT-05 | major | "Machine-verified" is circular for the 13 transcribed excerpts. | LIMIT-DISCLOSED | 13 chunks (U1 6, U5 5, AD2 2) carry `verification_status: VERIFIED_TRANSCRIPTION` in `kb/index/chunks.json`; the official portals refuse scripted clients. |
| RT-06 | major | Acceptance ≠ delivery never tested. | FIXED | S8 (see RJ-13). |
| RT-07 | major | Stated evaluation results did not match `latest.json`. | NOTE | Results are being regenerated; README and `evaluation/report.md` must be re-checked against `evaluation/results/latest.json` after the run. |
| RT-08 | major | `static_rules` was not a fair baseline (no genetic rule). | FIXED | As RJ-14: `hardcoded_genetic_rule=True` on `static_rules`. |
| RT-09 | major | Two ablations are null by construction. | LIMIT-DISCLOSED | `ablate_no_audit_agent` and `ablate_full_context` remain in `CONFIGS`; the audit assessor runs after the gate and cannot change an outcome. Kept as labelled null results. |
| RT-10 | major | Thin evidence: few scripted linear streams, all author-written. | OPEN | As RJ-27. |
| RT-11 | major | No reasoning content: answers held only choice and confidence. | FIXED | `providers.SYSTEM` asks for a `rationale`; `Provider.ask` stores `answers["rationale"]` (model text, or the typed judgment with probabilities for Jev); it is in the `agent.message` audit payload. Recordings are being regenerated with it. |
| RT-12 | major | The residency model left out MR 51/2021, which implements Art. 13. | LIMIT-DISCLOSED | `MR51` constant in `residency.py` ("official text not retrieved - human determination"); cited in refusals and in GR-19. Not in the KB (no official text found). |
| RT-13 | major | The UAE health-AI layer was missing. | PARTIAL | U6 (DHA AI policy PP-09, 8 excerpts) and U7 (NABIDH Audit Policy) in the KB. No MOHAP or national health-AI instrument: none identified as published (see `kb/sources/MANUAL_RETRIEVAL.md`). |
| RT-14 | major | The paper contradicted itself and the corpus. | FIXED | As RJ-19. |
| RT-15 | major | Published counts did not match the build. | OPEN | `README.md` says 248 tests; `submission/DESIGN-BRIEF.md` line 11 says 229 tests, 63 quotations, 14 documents, 8 scenarios. |
| RT-16 | major | README quick start used `cd backend`. | FIXED | README "Run it" uses `python -m uvicorn app.main:app`; no `cd backend` in README. |
| RT-17 | major | Other docs used the old layout and commands. | PARTIAL | `docs/architecture.md` and this file rewritten. `docs/REPORT.md` still has `cd backend && …` and "113 tests" (it carries a reading note saying it predates the current build). |
| RT-18 | major | No LICENSE although readiness claimed MIT. | FIXED | `LICENSE` (MIT) at the root. `pyproject.toml` has no `license` field. |
| RT-19 | major | No Dockerfile, yet readiness claimed single-container deployment. | FIXED | `Dockerfile` at the root; readiness R13 cites it; no `docker-compose` reference remains in `kb/framework/`. |
| RT-20 | major | Windows judges could not follow a `make`-based path. | FIXED | README uses plain `python` commands with a PowerShell environment example. |
| RT-21 | minor | Two DB paths; `/api/health` reported the wrong one. | FIXED | `app/models/db.py`: `DB_PATH = Path(_settings.db_path)`, the same setting `/api/health` reports. |
| RT-22 | minor | Generated run JSONs (~16 MB) committed. | PARTIAL | `evaluation/results/run-*.json` is in `.gitignore` and the files are staged for removal from the index; they remain in git history. |
| RT-23 | minor | Audit re-verification on read holds. | NOTE | `verify_entries()` in `app/audit/log.py` recomputes from stored rows; unchanged. |
| RT-24 | minor | The adviser can be pointed at local Ollama. | NOTE | The council's `ollama` preset (`qwen2.5:14b`, `http://localhost:11434/v1`) in `providers.PRESETS`. |
| RT-25 | major | Retrieval is lexical and misses paraphrases of the core legal question. | PARTIAL | Under BM25, "send health data abroad cloud" returns U2-art1, U1-art4 (×2), U2-art2, U1-art20, not Art. 13. Hybrid retrieval exists but is opt-in and needs a locally built store. |
| RT-26 | minor | Chunk `verification_status` held a file path. | FIXED | `app/kb/ingest.py` `build_chunks` writes the register class; `chunks.json` holds only class values (`VERIFIED_OFFICIAL`, `VERIFIED_TRANSCRIPTION`, …). |
| RT-27 | minor | Spot checks of quotations were positive. | NOTE | No change needed; all 93 chunks report `VERIFIED_AGAINST_SOURCE` at the last ingest. |
| RT-28 | minor | README said "no authentication" while optional API-key middleware exists. | OPEN | `README.md` still says "The build has no authentication"; `app/main.py` `_require_api_key` implements `RESULTRELAY_API_KEY` / `X-API-Key`. `docs/architecture.md` §9 now states it correctly. |
| RT-29 | minor | The served manifest went stale ("63 chunks across 14 sources"). | FIXED | `app/static/app/data/manifest.json` and `web/public/data/manifest.json` are identical, with `chunk_count: 96`, and contain no "63" counts. |
| RT-30 | minor | An external draft did not match the build. | NOTE | Superseded by `submission/ResultRelay_ITU_Submission.docx`. |
| RT-31 | minor | Framework mappings overclaimed (no external API, no proprietary dependency). | FIXED | Those phrases no longer occur in `kb/framework/*.csv`; R08 and Y4 state that hosted Mistral/Jev are used for synthetic cases and that the local 14B model has not been run end to end. |
| RT-32 | minor | Informational events were shown as BLOCKED transitions. | FIXED | `transitions.evaluate`: `INFORMATIONAL_EVENTS` return status `RECORDED` with audit event `event.informational`. |

## N series (second pass)

| id | sev. | finding (one line) | status | evidence in the current repo |
|---|---|---|---|---|
| N-01 | major | In S4 a physician-routed send with no physician channel reached nobody, unaudited and unescalated. | FIXED | `FAILED_TOOL_OUTCOMES` in `engine.py`; a failed tool outcome is audited as `action.failed` and escalated via `Orchestrator.escalate`; `scenarios/expected/S4-genetic-scope-exclusion.json` now expects `ESCALATION_REQUIRED`. |
| N-02 | major | The council could not change any outcome and its contribution was never measured. | PARTIAL | Mechanism fixed: a council ESCALATE opens a real escalation or replaces the proposal with `ESCALATE_HUMAN`; `resultrelay_council` vs `resultrelay` is a one-input comparison; S9 is a case the rules miss (`requires_council: true`). The measured result is pending the regenerated run. |
| N-03 | major | The reviewer's objection was 0.0 at every decision point. | PARTIAL | The reviewer now raises a typed `objection` from `OBJECTIONS`, verified by `fact_check` (rejected as `OBJECTION_REJECTED` if it does not fit) and acted on in `orchestrate()`. Whether it fires on the recorded runs is not shown until the recordings are regenerated. |
| N-04 | minor | The rule cross-check (`rule_conflicts`) was wrong, so the "matched" metric was unsound. | PARTIAL | `rule_conflicts` is gone; `detect_conflicts()` checks the recipient route for `SCOPE_CONFLICT`, and the reviewer's `ACCEPTANCE_AS_DELIVERY` objection covers accepted-only. `README.md` still reports the old "matched the rule check 12/16" figure. |
| N-05 | major | The ITU reference model stack (Ollama qwen2.5:14b) was never run end to end. | OPEN | `ollama` preset exists in `providers.PRESETS`; no `agent-ollama-*` recording; Y4 and R08 state it. |
| N-06 | major | The KB's own framework mappings were stale and contradicted the README. | PARTIAL | Both CSVs regenerated (13 dimensions; Y4 = council; R07 says AI Strategy 2031 is not in the KB). Residuals: R10 says "19-entry policy gap register" but `kb/gap_register.csv` has 18 rows; R12 cites `escalation_response_minutes` "in the profile", but `app/policies/profile.py` does not set it (the engine default of 30 minutes applies). |
| N-07 | major | No reasoning content to trace; the trace API said there was no model. | FIXED | `rationale` in `providers.py` (see RT-11) and the `run_trace` docstring. The rationale is logged, but code checks the typed answers, not the rationale text. |
| N-08 | minor | The report has no figure and lists a Step-6 demo `run_demo.py` lacks. | OPEN | The docx contains no media files although `submission/figure1_pipeline.png` exists; it still lists "Step-6 (reuse and residency)". |
| N-09 | minor | Stale documents next to the submission. | PARTIAL | `docs/architecture.md` and this file rewritten. Still stale: `submission/DESIGN-BRIEF.md` (63 / 14 / 8 scenarios / 229 tests), `submission/measure_length.py` (points at the absent `ResultRelay_ITU_paper.docx`), `docs/REPORT.md` (reading note only). |
| N-10 | minor | The global examples in the gap table (CLIA, 3GPP, EU AI Act) were not in the KB; all were Western. | FIXED | `kb/records/G6_etsi_ts123040.yaml`, `G7_clia_493_1291.yaml`, `G8_eu_ai_act.yaml`, `G9_saudi_pdpl.yaml`; cited in GR-05, GR-15, GR-17, GR-19. G9 (Saudi PDPL) is the non-Western comparator. |
| N-11 | minor | Council headline claims rest on one run each; a Jev-confidence anecdote reads as promotion. | OPEN | `README.md` still has "Jev, asked beforehand, had only been 49% sure"; no repeated runs with ranges. |
| N-12 | minor | The audit recorded what the gate allowed, not what happened. | FIXED | `engine.py` appends `action.performed` or `action.failed` with the tool outcome after every executed action. |

## Found during this re-check (not in the audit)

These are small and are listed so that they are not mistaken for things already checked:

1. **Fallback approval shown wrongly to the council.** `_case_view` in `engine.py` sets
   `approved_fallback_procedure` from `bool(profile["fallback_channel_id"])`. The default profile
   sets `fallback_channel_id: "PORTAL-PATIENT"` even when `fallback_channel_approved` is `False`
   (as in S3a), so the agents are told a fallback procedure is approved, and a correct
   `UNAPPROVED_CHANNEL` objection would be rejected by the code check. The gate is unaffected:
   INV-9 reads `fallback_channel_approved`.
2. **Stale configuration label.** `CONFIGS["resultrelay_council"].label` still reads "network,
   health, reviewer, critic, coordinator", the role names of the earlier council.
3. **Readiness rows R10 and R12** carry the count and profile-key errors listed under N-06.
4. **Vocabulary drift.** `scripts/fetch_sources.py` documents an `UNVERIFIED_THIS_RUN` label;
   `app/kb/ingest.py` uses `UNVERIFIED_NO_CACHE`.

## Still open, and why

| item | why it is still open | what would close it |
|---|---|---|
| Local reference model (N-05) | `qwen2.5:14b` needs a GPU this environment does not have; a 3B local model returned malformed answers. | One recorded council run on a local open model (e.g. on a cloud GPU), replayed as the default. |
| UAE National Strategy for AI 2031 (RJ-11, R07) | Not retrieved by script. The official PDFs are listed in `kb/sources/MANUAL_RETRIEVAL.md`. | Manual download, transcription with page markers, excerpts in `kb/records/`, re-ingest. |
| Ministerial Resolution 51/2021 (RT-12) | No official text located on a government domain; only law-firm commentary. Residency therefore sends exceptions to a person. | The official text from the UAE Legislation Portal or MOHAP, added as a source. |
| Transcribed sources U1, U5, AD2 (RT-05) | The portals refuse scripted clients, so verification is against an author transcription. | Re-verify against a downloaded official file; change the class to `VERIFIED_OFFICIAL`. |
| Independent scenarios (RJ-27, RT-10) | Every scenario and expectation is written by the engine authors; no one else has written one. | A held-out set written by someone who has not seen the engine, run unchanged. |
| Single model runs (N-11, N-02, N-03) | Council results come from few recorded runs of non-deterministic models; recordings are being regenerated. | Repeat runs with ranges; report what the council adds over `resultrelay`. |
| Public repository (RJ-03, RT-03) | No remote configured; fixes uncommitted at the time of writing. | Commit, push, and replace the placeholder link in the submission. |
| Stale prose (RJ-20, RT-15, RT-28, N-04, N-08, N-09, N-11) | README, DESIGN-BRIEF, `docs/REPORT.md` and the submission were not part of this pass. | Regenerate them from `evaluation/results/latest.json` and `kb/index/chunks.json` after the run. |
| Hybrid retrieval by default (RJ-04, RT-01, RT-25) | The ChromaDB store needs Ollama and a local build; it is not shipped. | Ship the store or make the build step part of setup, then default to hybrid. |
| Arabic (RJ-25) | Arabic PDF text layers tried did not extract cleanly; quotations are English. | A clean Arabic text source (see U10 in `kb/sources/MANUAL_RETRIEVAL.md`) and Arabic excerpts. |
