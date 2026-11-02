<div align="center">

# ResultRelay

**A policy-governed agent that refuses to call a critical lab result "communicated" until there is evidence a person received it.**
For walk-in laboratories licensed by the Dubai Health Authority: it keeps *sent*, *accepted by the
gateway*, *delivered*, *acknowledged* and *documented* apart, binds every acknowledgment to the current
result version, and refuses another jurisdiction's rule as binding.

`ITU AI for Good Sandbox Hackathon — UAE` · Healthcare track · agent roles: **policy & legal adviser · institutional participants (DHA, TDRA) · multi-agent coordination**

![Standard](https://img.shields.io/badge/ITU--T-Y.3172-0ea5e9)
![Data](https://img.shields.io/badge/data-100%25%20synthetic-success)
![Tests](https://img.shields.io/badge/tests-257%20passing-success)
![KB](https://img.shields.io/badge/quotes-96%20verified-success)

</div>

> ⚠️ **Synthetic data, hackathon exercise only.** No real patient data, EHR, SMS gateway or clinical
> claim. ResultRelay does not diagnose, set thresholds, interpret results or give medical advice.

---

## Team

**Team Aabyss** — submission to the
[ITU AI for Good Sandbox Hackathon — United Arab Emirates](https://aiforgood.itu.int/), healthcare track.

| | |
| :--- | :--- |
| **Team** | Team Aabyss |
| **Leader** | Priya Singh |
| **Members** | Shashwat Srivastava · Divyansh Vishwakarma · Anushka Gupta |
| **Hosts / partners** | ITU · TDRA (Telecommunications and Digital Government Regulatory Authority) |

---

## The one-sentence version

A critical result is flagged, the SMS gateway says "accepted", and a dashboard turns green. Nobody knows
whether the patient has it. **ResultRelay will not close the case on a gateway acceptance, will not reuse
an acknowledgment of version 1 for a corrected version 2, and will not message a patient directly about
a genetic result** — DHA's standard routes those to the referring physician.

```console
$ python run_demo.py 4
── SC-04 [controversial] A generic walk-in rule retrieved for a genetic result  (S4-genetic-scope-exclusion)
   FINAL ESCALATION_REQUIRED              VERDICT VIOLATION              ✓ expected ESCALATION_REQUIRED
   policy-blind final → DELIVERY_CONFIRMED · rules only (no agents) → ESCALATION_REQUIRED
```

## Multi-agent orchestration — LLMs only where reasoning is needed

The design rule: **use a language model only where the problem needs probabilistic reasoning** (reading
policy, reading what people said); decide everything else in code — transport status, revision binding,
idempotency, and whether to escalate.

```
 event chunk  ── from a scenario file, or injected by a judge:  POST /api/runs/{id}/events
      │
      ▼
 DETERMINISTIC CASE SERVICES  revision binding · transport reconciliation · recipient routing · applicability
      │                       5 rule-based assessors propose the step's action
      ▼
 EVIDENCE RETRIEVAL  BM25 (+ ChromaDB via the ITU ingest) · jurisdiction filter · 96 verified quotations
      │
      ├─▶ ① POLICY EVIDENCE ANALYST   (LLM, DHA lens)   obligation status · governing clause · settled? · policy gap
      ├─▶ ② INSTITUTIONAL ANALYST     (LLM, TDRA lens)  only when transport is unresolved: does any telecom
      │                                                 clause cover delivery of this message to a person?
      └─▶ ③ ADVERSARIAL REVIEWER      (LLM, a different model family)  challenges each claim, reads the case
                                                        independently, raises a typed objection
      ▼
 ④ INDEPENDENT ASSURANCE (code)  fact check vs the case record · policy-rules check (a comparator can never
      │                          govern) · conflict detection · one feedback round: CORRECTED / UPHELD / DISPUTED
      ▼
 ⑤ DETERMINISTIC ORCHESTRATOR    PROCEED, or ESCALATE to a named owner with a deadline — on a verified
      │                          objection or a disputed claim. Gaps and differing readings are recorded.
      ▼
 GATE (P node, code)  18 states, named invariants — decides the transition; never reads the agents
      ▼
 EXECUTION & AUDIT    failed actions logged and escalated · overdue escalations re-escalated to tier 2 ·
                      every message, check and decision in a hash chain · HMAC-signed checkpoints
```

| Actor | Kind | Produces | Can it change the case? |
| :--- | :--- | :--- | :--- |
| ① Policy Evidence Analyst | LLM | obligation status, governing clause, "settled?", policy gap, rationale | No |
| ② Institutional analyst (TDRA) | LLM, conditional | whether a telecom clause covers this message | No |
| ③ Adversarial reviewer | LLM, independent model family | typed objection, own reading, per-claim support | No |
| ④ Assurance | code | fact/policy-rule findings; rejects objections the record contradicts | No |
| ⑤ Orchestrator | code | PROCEED or ESCALATE | Only an escalation to a person |
| Gate | code | the transition | **Yes — only this** |

Why this shape: in an earlier version an LLM "network agent" re-derived transport facts the system already
knew and **hallucinated delivery receipts**, and an LLM coordinator over-escalated and decided nothing a
rule could not; both were replaced by code. A reviewer from a different model family was kept because it
measurably caught more: with the critic on the same family as the agents it reviewed, 5 answers were
corrected; on a different family, 11 (same scenarios, one run each).

**Recorded run** — `python run_demo.py` replays it offline (Mistral `ministral-14b-2512` analysts, TypeSafe
Jev reviewer; synthetic cases only):

| | Result |
| :--- | :--- |
| Final state as expected | **6/6** scenarios |
| Decision points · agent answers · TDRA lens invoked | 18 · 41 · 5 |
| Analyst claims flagged by assurance | 15 → 7 corrected after feedback, 8 upheld, 0 disputed |
| Reviewer objections | 13 → 10 rejected by code (each contradicted the case record), 3 acted on |
| Policy gaps surfaced per case | 13 (e.g. no acknowledgment clock, delivery evidence undefined) |
| Escalations raised by the agents | 3: S9 (the only one rules miss) and twice in SC-02, an unapproved fallback channel the gate also refuses |

**What the agents add that rules cannot (SC-06, scenario S9).** The SMS is delivered with a receipt and a
reply arrives from the registered number, marked as an acknowledgment from a verified number. The reply
says: *"This is his daughter. My father is in hospital abroad…"*. Rules read the structured fields and close
the case; the policy-blind baseline does too. The reviewer read the words, raised
`TEXT_CONTRADICTS_RECORD` (confidence 0.93), and the orchestrator escalated:

```console
   FINAL ESCALATION_REQUIRED   ✓ expected ESCALATION_REQUIRED
   policy-blind final → COMMUNICATION_DOCUMENTED · rules only (no agents) → COMMUNICATION_DOCUMENTED
           reviewer objection TEXT_CONTRADICTS_RECORD · own reading COMMUNICATED
           orchestrator ESCALATE ▶ verified reviewer objection TEXT_CONTRADICTS_RECORD
```

Said plainly: an earlier recording of this design missed S9 because one assurance rule rejected the
objection on a consistency heuristic (the reviewer named the same action as its "alternative"); that rule
was changed after seeing that run, so only checks against the case record can now reject an objection. The
recording above was made after the change and caught S9 on its own. Each figure comes from a single
recorded run of a non-deterministic model.

**Any model, per role.** Agents ask typed questions (named options or a probability); a chat model's JSON
answer is validated against them and anything off-list is rejected, never repaired. Every request passes the
residency guard first.

| `RESULTRELAY_AGENT_PROVIDER` | Endpoint | Residency (Federal Law 2/2019 Art. 13) |
| :--- | :--- | :--- |
| `ollama` | `http://localhost:11434/v1`, e.g. `qwen2.5:14b` (ITU reference model) | local: real cases allowed |
| `mistral` | `https://api.mistral.ai/v1` (`MISTRAL_API_KEY`) | outside the State: synthetic `SYN-*` cases only |
| `openai` | any OpenAI-compatible server (`RESULTRELAY_AGENT_URL`) | decided by the endpoint |
| `jev` | TypeSafe Jev (`TYPESAFE_API_KEY`) | outside the State: synthetic cases only |
| `replay` | recorded answers (default offline); refused if the case view changed | no request leaves the machine |

Each role can run on its own model with `RESULTRELAY_<ANALYST|INSTITUTION|REVIEWER>_PROVIDER` / `_MODEL`.
Recommended (and the recorded run):

```bash
RESULTRELAY_AGENT_PROVIDER=mistral
RESULTRELAY_AGENT_MODEL=ministral-14b-2512     # analysts; open weights, the size class of qwen2.5:14b
RESULTRELAY_REVIEWER_PROVIDER=jev              # the adversarial reviewer on a different model family
```

Keys go in `.env` at the repo root (git-ignored; see `.env.example`). The council runs in the
`resultrelay_council` configuration only, so the council-off configurations stay a clean comparison. On a
6 GB laptop a 3B local model ran but returned malformed answers and out-of-memory errors; the 14B reference
model needs the ITU Lab compute requested in [submission/DESIGN-BRIEF.md](submission/DESIGN-BRIEF.md).

## Architecture — ITU-T Y.3172, node for node

| Node (Y.3172 §8.1) | In ResultRelay | AI Readiness 2.0 dimension | Policy source |
| :--- | :--- | :--- | :--- |
| **SRC** | Synthetic result revisions, contacts, channels; the verified corpus | Data/Model Marketplace (1), Contextualization and Regional Impact (4) | DHA ST-28 §11.1 (walk-in tests) |
| **C** | Staged event streams: transport, patient and supervisor events | Level of Integration of AI in Workflows (5) | DHA ST-28 §11.1.1–3 |
| **PP** | Normalised states; report version, action id and provenance preserved | AI & Policies (10) | HL7 FHIR Task, IHE XDW (comparators) |
| **M** | Policy Evidence Analyst (DHA lens), conditional TDRA-lens analyst, adversarial reviewer (any LLM, per role); deterministic assurance | Collaboration with AI (8), Impacts of Humans in AI Integration (9) | DHA AI policy PP-09 §4.3.1, §4.4.2; UAE AI Charter |
| **P** | Gate: scope (§13.4 genetic results), version binding, reconcile-before-retry, no false closure | AI & Policies (10), Strategy Alignment (7) | DHA ST-28 §11.1, §13.4 |
| **D** | Mock transport that separates acceptance, delivery and acknowledgment; idempotency keys | Digital Infrastructure (13), Granular Priorities (12) | Federal Law 2/2019 Art. 4, 13; TDRA Mobile Spam §1-23 |
| **SINK** | Supervisor queue, React console, hash-chained audit re-verified on read | Human Interface (6), AI for Inclusion (11) | DHA ST-28 §11.1.3; NABIDH Audit Policy §3.2.10–11 |

## The six scenarios — `python run_demo.py`

| # | Scenario | Final state | Verdict | Rules only · policy-blind |
| :--- | :--- | :--- | :--- | :--- |
| **SC-01** normal | Genetic result routed to the referring physician | `COMMUNICATION_DOCUMENTED` | `COMPLIANT` | same · same |
| **SC-02** failure | Primary channel down, no approved fallback | `ESCALATION_REQUIRED` | `INSUFFICIENT_EVIDENCE` | same · invents a channel → `DELIVERY_CONFIRMED` |
| **SC-03** failure | Corrected result after acknowledgment of version 1 | `CORRECTED_RESULT_ACKNOWLEDGED` | `COMPLIANT` | same · `ESCALATION_REQUIRED` |
| **SC-04** controversial | Generic walk-in rule retrieved for a genetic result; no physician channel | `ESCALATION_REQUIRED` (failed send logged and escalated) | `VIOLATION` (prevented) | same · messages the patient |
| **SC-05** failure | Gateway accepts the SMS; no receipt ever arrives | `ESCALATION_REQUIRED` | `INSUFFICIENT_EVIDENCE` | same · records delivery |
| **SC-06** agents | Delivered and "acknowledged", but the reply is from the patient's daughter | `ESCALATION_REQUIRED` | `INSUFFICIENT_EVIDENCE` | **closes the case** · closes the case |

Every run prints the audit checkpoint; set `RESULTRELAY_AUDIT_KEY` to sign it (HMAC-SHA256 over the chain
head): a rebuilt, internally consistent chain passes the hash check but not the signed checkpoint.
`python scripts/timestamp_audit.py S8-accepted-never-delivered` anchors a checkpoint in time with an RFC 3161
token from an independent Time-Stamping Authority (FreeTSA by default; only the hash leaves the machine) —
example in `evaluation/timestamps/`. The console's decision trace shows the council at each step: each
agent's answers and rationale, assurance outcomes, and the orchestrator's decision.

## Where the scenarios come from

The scenarios are **synthetic adaptations of published patient-safety incidents** and clinical-workflow studies:
the failure mode is taken from the published case, the facts, names and timings are invented, and the
source is cited as provenance in each scenario file (`"provenance"`), not reproduced.

| Scenario | Failure mode in the published case | Match | Source |
| :--- | :--- | :--- | :--- |
| S1 | notification reached a device or intermediary; the responsible person never acknowledged | strong | [AHRQ PSNet WebM&M (2017)](https://psnet.ahrq.gov/web-mm/delayed-recognition-positive-blood-culture) · [BMJ Open Quality (2021)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8442100/) |
| S8 | outgoing notification counted as done; acknowledgment by a person absent | strong | [BMJ Open Quality (2021)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8442100/) · [AHRQ PSNet WebM&M (2017)](https://psnet.ahrq.gov/web-mm/delayed-recognition-positive-blood-culture) |
| S9 | a relative receives or answers for the patient; consent and identity decide, not the phone number | very strong | [Medical Protection Asia Casebook, July 2017, Case 2](https://www.medicalprotection.org/docs/medicalprotectioninternationallibraries/pdfs/casebook-pdfs/asia-casebook-pdfs/july-2017.pdf) · [Medical Protection](https://www.medicalprotection.org/uk/articles/digital-dilemmas-communicating-with-patients-by-text) |
| S2 | an amended result reached a unit, not the clinician who had acted on the first version | almost exact | [AHRQ PSNet WebM&M (2012)](https://psnet.ahrq.gov/web-mm/amended-lab-results-communication-slip) |
| S5 | an acknowledgment that belongs to an earlier version must not close the amended one | related | [AHRQ PSNet WebM&M (2012)](https://psnet.ahrq.gov/web-mm/amended-lab-results-communication-slip) |
| S3a | the intended recipient could not be reached and no escalation path was followed | almost exact | [CRICO / Harvard Risk Management Foundation (2023)](https://rmfcd1-prod.rmf.harvard.edu/Risk-Prevention-and-Education/Case-Study-Catalog-Page/Case-Study/2023/Discharged-Patient-with-Pending-Test-Results) · [American Journal of Clinical Pathology (2011)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7065418/) |
| S3b | an approved escalation path (on-call pathologist) reaches a responsible clinician | close | [American Journal of Clinical Pathology (2011)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7065418/) |
| S4 | genetic results need consent-aware routing and counselling | related, not exact | [Adverse events in genetic testing](https://pubmed.ncbi.nlm.nih.gov/31335384/) · [Illustrative case studies in the return of exome and genome sequencing results (2015, PMC4607287)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4607287/) |
| S7 | who receives a genetic result is planned in advance, not decided by the channel | related, not exact | [Illustrative case studies in the return of exome and genome sequencing results (2015, PMC4607287)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4607287/) · [Adverse events in genetic testing](https://pubmed.ncbi.nlm.nih.gov/31335384/) |

S6 (a clause from another jurisdiction) has no incident source: it tests the applicability filter. The
genetic-routing sources show that genetic results need consent-aware, planned routing; they do not establish
that every genetic result must go to a particular specialist — that routing comes from DHA ST-28 §13.4.

## Evaluation — `python scripts/run_evaluation.py`

10 scenarios × 12 configurations = 120 runs. *Fully safe* = every must-hold assertion passed **and** the case
ended in a state its expectation allows (assertions alone had scored a case closed on the daughter's reply
as safe).

| Configuration | Fully safe | Assertions | Provenance |
| :--- | ---: | ---: | ---: |
| `resultrelay_council` (rules + agent council) | **10/10** | **42/42** | 1.00 |
| `resultrelay` (rules, no agents) | 9/10 — misses S9 | 42/42 | 1.00 |
| `static_rules` (competent hand-written rules, genetic rule hard-coded) | 9/10 — misses S9 | 42/42 | 0.00 |
| `ablate_no_applicability_filter` | 8/10 | 41/42 | 1.00 |
| `ablate_no_kb` · `ablate_ack_any` · `ablate_optimistic_transport` · `ablate_no_invariants` | 7/10 | 40–41/42 | 0.00–1.00 |
| `retrieval_only` | 3/10 | 36/42 | 1.00 |
| `policy_blind` | 2/10 | 35/42 | 0.00 |

What this shows, and does not: a competent rules engine with the same state machine is as safe as
ResultRelay's rules on structured events — ResultRelay's added value there is **provenance** (every
decision cites a verified clause; 1.00 vs 0.00) and jurisdiction gating. The agents add the one case rules
cannot read (S9). `ablate_no_audit_agent` and `ablate_full_context` are **controls**: they cannot change an
outcome by construction and score 9/10 like `resultrelay`. All scenarios and expectations were written by
the team that wrote the engine (each file says so); the council figures come from one recorded run. DHA's
AI policy (PP-09 §4.3.3) requires independent third-party validation; this system has had none.

## Knowledge base — `GET /api/kb/search?q=…&jurisdiction=AE-DU`

**96 quotations from 24 documents**, each with issuing body, jurisdiction, section, printed page and a
claim class; only `BINDING_REQUIREMENT` can block an action, and only sources that bind the case
jurisdiction carry it. **74 are verified against official downloads** (PDF, eCFR, ETSI, WIPO Lex, Dubai Legal Portal); **2 against a mirror** (the PDPL's unofficial English translation) (the quote must appear on the
declared page, or the excerpt is rejected and never indexed); **7 against third-party copies** (TDRA Mobile Spam policy; EU AI Act articles) because the official sites refuse scripted clients; **13 (Federal Law 2/2019,
UAE AI Charter, ADHICS) against recorded transcriptions** of portal pages. The served index is pinned by
SHA-256 and re-checked on load.

| Layer | Sources |
| :--- | :--- |
| Dubai (binding) | DHA establishment law (Law No. 6 of 2018 as amended, Art. 5–6: DHA's mandate) · DHA ST-28 laboratory standards · DHA AI in Healthcare policy PP-09 · NABIDH Audit Policy · DHA health-information and data-quality policies |
| Federal | Federal Law 2/2019 (ICT in health) · Telecom Law (Decree-Law 3/2003, Art. 13: TDRA's mandate) · PDPL (scope exclusion only) · UAE AI Charter · TDRA Mobile Spam policy |
| Comparators | DoH Abu Dhabi lab standard and ADHICS · RCPath G158 (UK) · US CLIA 42 CFR 493.1291 · EU AI Act Arts 14/26/73 · Saudi PDPL (GCC) · ETSI TS 123 040 (3GPP SMS) · Joint Commission NPSG · ONC SAFER Guide 8 · HL7 FHIR R5 Task · IHE XDW · ITU-T Y.3172 · ITU AI Readiness 2.0 |

**Vector KB built with the ITU reference code — shipped in `kb/chroma`.** `python scripts/export_itu_kb.py
--ingest PATH/TO/ITUAIReadiness` writes every verified excerpt to `kb/itu_inputdocs/` in the ITU InputDocs
format and runs the ITU `ingest.py` (Ollama `nomic-embed-text`, ChromaDB, cosine), with clause id, authority,
jurisdiction, section, page and URL as metadata. **Search is hybrid by default** (BM25 fused with the vector
ranking); it falls back to BM25 with a note when Ollama is not running. The vector store only *ranks*: text
always comes from the verified, SHA-pinned index. The agent council retrieves with BM25 explicitly, so its
recorded answers replay exactly on any machine.

On seven plain-language questions ([evaluation/retrieval_check.md](evaluation/retrieval_check.md)) the
expected clause is in the top 5 for **hybrid 4/7, BM25 1/7**; Arabic questions are mapped to the English
clauses ("نقل البيانات الصحية خارج الدولة" → Law 2/2019 Art. 13 first). The questions are ours: a smoke test.

**Sources a script cannot download** — the UAE National Strategy for AI 2031, Ministerial Resolution 51/2021,
the National Cybersecurity Strategy, a MOHAP health-AI instrument, and the official texts behind the
transcriptions — are listed with official links and the steps to add them in
[kb/sources/MANUAL_RETRIEVAL.md](kb/sources/MANUAL_RETRIEVAL.md).

## Policy and standards gaps — [kb/gap_register.csv](kb/gap_register.csv)

| Gap | Type | Global comparison |
| :--- | :--- | :--- |
| **GR-15** TDRA's policy defines "delivery" only for marketing SMS, as network delivery to the subscriber (§1-23, §8-1); DHA ST-28 §11.1.3 needs a record of communication. Nothing joins them, or assigns responsibility for an accepted-but-lost clinical SMS | Coordination (health ↔ telecom) | ETSI TS 123 040 §9.2.3.15: SMS status stops at "received by the SME" (the receiving entity: a handset or application, not a person); RCPath G158 §5 (UK): feedback on "received, read, understood" |
| **GR-16** DHA ST-28 §11.1 provides for walk-in results to the patient, with no acknowledgment standard for a lay recipient of a critical value | Conflict between objectives | RCPath G158 §8: critical results "only communicated with the requesting clinical team" |
| **GR-11** Is the communication record an audit log (NABIDH §3.2.11: 3 years) or health data (Law 2/2019 Art. 20: 25 years)? | Standards ambiguity | RCPath G158 §7 names the record's fields, leaves retention local |
| **GR-17** DHA PP-09 requires agreed accountability, independent validation and AI-incident reporting, but names no default owner, validator or deadline; its revision date (1 July 2026) has passed | AI governance | EU AI Act Art. 26(2) requires deployers to assign oversight to competent persons; Art. 73(2) sets a 15-day serious-incident deadline |
| **GR-03** No retrieved source sets an acknowledgment clock for walk-in results | Unclear responsibility | Joint Commission NPSG.02.03.01 leaves the time frame to the organisation |
| **GR-18** No route for a clinical SMS to show it is not marketing (quiet hours 9pm–7am, §8-3) | Implementation | none retrieved |
| **GR-19** The exceptions to the UAE ban on processing health data abroad sit in Ministerial Resolution 51/2021, which no official portal served | AI governance / residency | Saudi PDPL Art. 29: lists transfer purposes in the law and delegates the rest, and the adequacy test, to Regulations (GCC) |

18 entries in total; each lists the sources reviewed, what they establish, what remains unclear and the
product control that follows. Gaps that rest on an absence say what was searched (the full corpus, 2 Nov 2026):
an absence cannot be proven, only searched for. PDPL (Federal Decree-Law
45/2021) is cited only for its scope exclusion: **Article 2, exclusion (e)** — health data governed by
its own legislation.

## Run it

```bash
python -m pip install -r requirements.txt
python -m pytest -q                          # 257 tests (one skips unless every source text is cached)
python run_demo.py                           # six scenarios; the agent council replays recorded answers offline
python scripts/run_evaluation.py             # 120-run matrix → evaluation/report.md
python -m uvicorn app.main:app --port 8000   # API + built UI on http://127.0.0.1:8000  (docs at /api/docs)
python scripts/fetch_sources.py              # optional: download the official texts and re-verify every quote

# optional: vector KB with the ITU reference stack (pip install -r requirements-itu.txt; Ollama running)
ollama pull nomic-embed-text
python scripts/export_itu_kb.py --ingest PATH/TO/ITUAIReadiness
RESULTRELAY_RETRIEVAL=hybrid python scripts/retrieval_check.py
```

Live adviser: set `TYPESAFE_API_KEY` and `RESULTRELAY_ADVISE=1`, `RESULTRELAY_ADVISE_PROVIDER=jev`
(PowerShell: `$env:RESULTRELAY_ADVISE='1'`). A local OpenAI-compatible model (Ollama) works through
`RESULTRELAY_ADVISE_URL=http://localhost:11434/v1`. The UI is pre-built in `app/static/app`; rebuild with
`cd web && npm ci && npm run build`. Authentication is off by default (set `RESULTRELAY_API_KEY` to require an `X-API-Key` header): bind to 127.0.0.1 and use synthetic
data only.

## Repository

```
app/          gateway: agents/, multiagent/ (council, providers), advisers/ (guard, residency), orchestration/ (gate, engine),
              state_machine/, transport/, kb/ (ingest + verified retrieval), audit/, api/, static/ (built UI)
web/          React console (CaseTimeline, Simulator, Standards & gaps, Evaluation, Audit, Decision trace)
kb/           records/ (verified excerpts) · index/ (pinned) · framework/ (Y.3172 + Readiness mappings) · itu_inputdocs/
scenarios/    S1–S9 staged event streams · expected/ (assertions)
evaluation/   report.md · results/latest.json · agent_runs/ (recorded adviser responses)
submission/   technical report · design brief · build scripts
docs/         architecture, REPORT, audit disposition, design notes
tests/        257 tests
```

## License

[MIT](LICENSE). Source documents belong to their issuing bodies and are not redistributed; quotations are
minimal and attributed with section and page.
