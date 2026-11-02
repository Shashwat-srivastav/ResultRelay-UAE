<div align="center">

# ResultRelay

**A policy-governed agent that refuses to call a critical lab result "communicated" until there is evidence a person received it.**
For walk-in laboratories licensed by the Dubai Health Authority: it keeps *sent*, *accepted by the
gateway*, *delivered*, *acknowledged* and *documented* apart, binds every acknowledgment to the current
result version, and refuses another jurisdiction's rule as binding.

`ITU AI for Good Sandbox Hackathon — UAE` · Healthcare track · agent roles: **policy & legal adviser · institutional participants (DHA, TDRA) · multi-agent coordination**

![Standard](https://img.shields.io/badge/ITU--T-Y.3172-0ea5e9)
![Data](https://img.shields.io/badge/data-100%25%20synthetic-success)
![Tests](https://img.shields.io/badge/tests-248%20passing-success)
![KB](https://img.shields.io/badge/quotes-82%20verified-success)

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

## Multi-agent orchestration — who does what at every decision point

```
 event chunk  ── from a scenario file, or injected by a judge:  POST /api/runs/{id}/events
      │
      ▼
 ORCHESTRATOR (Y.3172 MLFO) ─ records the event in the hash-chained audit log
      │
      ├─▶ 5 ASSESSORS (rules) ─ lab workflow · KB applicability · network delivery · escalation timers · audit
      │        └─▶ proposed action for this step, e.g. RECONCILE_ATTEMPT
      │
      ├─▶ COUNCIL  (app/multiagent/council.py — any LLM: Ollama, Mistral, OpenAI-compatible, Jev)
      │     ① NETWORK agent   TDRA lens    "what does the transport evidence show?"
      │     ② HEALTH agent    DHA lens     "where does the duty to communicate this result stand?"
      │     ③ REVIEWER        policy/legal "is there a concrete objection to the proposed action?"
      │         each sees only its own authority's clauses; each may call one read-only tool
      │         (transport_ledger · kb_search) and answer again with the result in view
      │     ④ FACT CHECK (code) ─ every claim vs the case record ─────────┐  flagged answers get the
      │     ⑤ CRITIC agent      ─ supported by facts + cited clause? ─────┘  critique and ONE revision
      │         still contradicts the record after revision → DISPUTED (kept, not trusted, supervisor told)
      │     ⑥ COORDINATOR agent ─ PROCEED / GATHER_EVIDENCE / ESCALATE_HUMAN + the conflict it sees
      │     ⑦ RULE CROSS-CHECK (code) ─ recomputes the conflicts; a coordinator that misses one is visible
      │
      ├─▶ GATE (P node, code) ─ decides the transition from 18 states and named invariants.
      │        It never reads the council. Agents can only ADD a supervisor-review request.
      │
      └─▶ AUDIT ─ agent.message · agent.tool_call · critic.review · coordinator.resolution · gate decision,
                  all in one hash chain re-verified on read: the step's reasoning trace
```

| # | Actor | Kind | Sees | Produces | Can change the case? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| ① | Network agent | LLM | TDRA Mobile Spam policy; attempts; ledger (tool) | delivery status (receipt / accepted-only / unknown / failed / not sent) + cited clause | No |
| ② | Health agent | LLM | DHA ST-28, AI policy PP-09, NABIDH, ICT Health Law; acknowledgments | obligation status (communicated / awaiting ack / must go to physician / not sent / insufficient) + clause | No |
| ③ | Policy & legal reviewer | LLM | all clauses that bind the case | objection probability + alternative action + clause | No |
| ④ | Fact check | code | case record | contradictions between a claim and the record | No — **authoritative** over the critic |
| ⑤ | Critic | LLM | each answer, its cited text, the case | supported? (probability) + issue type | No — triggers a revision only |
| ⑥ | Coordinator | LLM | trusted answers + critic verdicts | resolution + named conflict | Only adds a supervisor-review request |
| ⑦ | Rule cross-check | code | trusted answers | the conflicts, recomputed | No |
| — | Gate | code | invariants, case state | **the transition** | **Yes — only this** |

**Why a critic, and why two layers.** Agents hallucinate. The fact check catches claims that contradict
the record; it is code, so it cannot hallucinate, and it overrules the critic. The critic agent catches
what code cannot: an answer whose cited clause does not say what the answer relies on. A critic can be
wrong too, so its flag only ever buys a revision. Each flagged agent sees the critique and answers once
more; the outcome is `CORRECTED`, `UPHELD` or `DISPUTED`.

**Recorded run** (`python run_demo.py`, five scenarios, provider Jev, replayed offline from
`evaluation/agent_runs/`):

| Measure | Result |
| :--- | :--- |
| Final state matches expected | **5/5** |
| Decision points deliberated · agent answers · tool calls | 16 · 48 · 28 |
| Answers flagged by fact check or critic | 18 → **6 corrected**, 12 upheld, 0 disputed |
| Coordinator agrees with the rule cross-check | 10/16 |
| Supervisor-review requests raised by the coordinator | 14/16 (over-cautious: logged, never acted on by the gate) |

What the critic caught, for example (SC-05, step 4): the health agent claimed the result was
*communicated*; the fact check found no acknowledgment of the current revision; shown the finding, the
agent corrected itself to *awaiting acknowledgment*. On SC-04 it caught the reviewer objecting to an
action while proposing the same action as its alternative.

```console
   step  4 ESCALATE_HUMAN       gate → ESCALATE_HUMAN       network ACCEPTED_ONLY · health AWAITING_ACK · reviewer objection p=0.52
           critic: network corrected; health corrected (claims the result was communicated, but no one acknowledged the current revision); reviewer upheld · tools transport_ledger,kb_search,kb_search
           coordinator ESCALATE_HUMAN / DELIVERY_WITHOUT_COMMUNICATION · rule check ['REVIEWER_OBJECTS']  ⚠ coordinator disagrees with the rule check
```

**Any model.** One setting picks the provider; every agent asks typed questions (named options or a
probability), and a chat model's JSON answer is validated against them — an option that is not on the
list is rejected, never repaired.

| `RESULTRELAY_AGENT_PROVIDER` | Endpoint | Residency (Federal Law 2/2019 Art. 13) |
| :--- | :--- | :--- |
| `ollama` | `http://localhost:11434/v1`, e.g. `qwen2.5:14b` (ITU reference model) | local: real cases allowed |
| `mistral` | `https://api.mistral.ai/v1` (`MISTRAL_API_KEY`) | outside the State: synthetic `SYN-*` cases only |
| `openai` | any OpenAI-compatible server (`RESULTRELAY_AGENT_URL`) | decided by the endpoint |
| `jev` | TypeSafe Jev (`TYPESAFE_API_KEY`) | outside the State: synthetic cases only |
| `replay` | recorded answers (default offline); refused if the case view changed | no request leaves the machine |

Keys go in `.env` at the repo root (git-ignored; see `.env.example`). On a 6 GB laptop a 3B local model
(`qwen2.5:3b`) ran end to end but returned malformed answers and out-of-memory errors; the 14B reference
model needs the ITU Lab compute requested in [submission/DESIGN-BRIEF.md](submission/DESIGN-BRIEF.md).

**Containment.** A separate single-adviser path ([app/advisers/guard.py](app/advisers/guard.py)) applies
residency, grounding (cite only what was shown) and jurisdiction (a comparator can inform a human, never
underwrite an action) checks to any model proposal before the gate sees it; a test asserts the gate's
decision is unchanged when a proposal is attached.

## Architecture — ITU-T Y.3172, node for node

| Node (Y.3172 §8.1) | In ResultRelay | AI Readiness 2.0 dimension | Policy source |
| :--- | :--- | :--- | :--- |
| **SRC** | Synthetic result revisions, contacts, channels; the verified corpus | Data/Model Marketplace (1), Contextualization and Regional Impact (4) | DHA ST-28 §11.1 (walk-in tests) |
| **C** | Staged event streams: transport, patient and supervisor events | Level of Integration of AI in Workflows (5) | DHA ST-28 §11.1.1–3 |
| **PP** | Normalised states; report version, action id and provenance preserved | AI & Policies (10) | HL7 FHIR Task, IHE XDW (comparators) |
| **M** | Council: network, health and reviewer agents, fact check + critic, coordinator (any LLM); hybrid retrieval | Collaboration with AI (8), Impacts of Humans in AI Integration (9) | DHA AI policy PP-09 §4.3.1, §4.4.2; UAE AI Charter |
| **P** | Gate: scope (§13.4 genetic results), version binding, reconcile-before-retry, no false closure | AI & Policies (10), Strategy Alignment (7) | DHA ST-28 §11.1, §13.4 |
| **D** | Mock transport that separates acceptance, delivery and acknowledgment; idempotency keys | Digital Infrastructure (13), Granular Priorities (12) | Federal Law 2/2019 Art. 4, 13; TDRA Mobile Spam §1-23 |
| **SINK** | Supervisor queue, React console, hash-chained audit re-verified on read | Human Interface (6), AI for Inclusion (11) | DHA ST-28 §11.1.3; NABIDH Audit Policy §3.2.10–11 |

## The four scenarios — `python run_demo.py`

| # | Scenario | Final state | Verdict | Policy-blind |
| :--- | :--- | :--- | :--- | :--- |
| **SC-01** normal | Genetic result routed to the referring physician | `COMMUNICATION_DOCUMENTED` | `COMPLIANT` | same |
| **SC-02** failure | Primary channel down, no approved fallback | `ESCALATION_REQUIRED` | `INSUFFICIENT_EVIDENCE` | invents a channel → `DELIVERY_CONFIRMED` |
| **SC-03** failure | Corrected result after acknowledgment of version 1 | `CORRECTED_RESULT_ACKNOWLEDGED` | `COMPLIANT` | `ESCALATION_REQUIRED` |
| **SC-04** controversial | Generic walk-in rule retrieved for a genetic result | `RESULT_FINALIZED` (direct path refused) | `VIOLATION` | messages the patient → `DELIVERY_CONFIRMED` |
| **SC-05** failure | Gateway accepts the SMS; no receipt ever arrives | `ESCALATION_REQUIRED` | `INSUFFICIENT_EVIDENCE` | records delivery → `DELIVERY_CONFIRMED` |

## Evaluation — `python scripts/run_evaluation.py`

9 scenarios × 11 configurations = 99 runs; seven configurations differ from the full system in exactly
one input.

| Configuration | Fully safe | Assertions |
| :--- | ---: | ---: |
| `resultrelay` | **9/9** | **38/38** |
| `static_rules` (competent hand-written rules) | 7/9 | 36/38 |
| `ablate_optimistic_transport` (acceptance recorded as delivery) | 7/9 | 36/38 |
| `ablate_no_kb` · `ablate_ack_any` | 7/9 | 36/38 |
| `retrieval_only` | 3/9 | 32/38 |
| `policy_blind` | 2/9 | 31/38 |

"Acceptance is not delivery" is now tested: the delivery check reads the transport ledger, so a conflated
receipt fails S1, and S8 (accepted, never delivered) fails every configuration that conflates.

What these numbers do not show, said plainly: the scenarios and expectations were written by the same
team that wrote the engine, and every expectation file says so (`"authorship": "ENGINE_AUTHORS"`).
`static_rules` loses only the two genetic-scope scenarios, because it was built without a genetic rule.
Two ablations (`ablate_no_audit_agent`, `ablate_full_context`) cannot change an outcome by construction.
DHA's AI policy (PP-09 §4.3.3) requires independent third-party validation; this system has had none.

## Knowledge base — `GET /api/kb/search?q=…&jurisdiction=AE-DU`

**82 quotations from 18 documents**, each with issuing body, jurisdiction, section, printed page and a
claim class; only `BINDING_REQUIREMENT` can block an action, and only sources that bind the case
jurisdiction carry it. **65 are verified against downloaded official PDFs** (the quote must appear on the
declared page, or the excerpt is rejected and never indexed); **4 (TDRA Mobile Spam policy v9.0) against a
third-party copy** of the policy, because tdra.gov.ae refuses scripted clients; **13 (Federal Law 2/2019,
UAE AI Charter, ADHICS) against recorded transcriptions** of portal pages. The served index is pinned by
SHA-256 and re-checked on load.

| Layer | Sources |
| :--- | :--- |
| Dubai (binding) | DHA ST-28 laboratory standards · DHA AI in Healthcare policy PP-09 · NABIDH Audit Policy · DHA health-information and data-quality policies |
| Federal | Federal Law 2/2019 (ICT in health) · PDPL (scope exclusion only) · UAE AI Charter · TDRA Mobile Spam policy |
| Comparators | DoH Abu Dhabi lab standard and ADHICS · RCPath G158 (UK, 2026) · Joint Commission NPSG · ONC SAFER Guide 8 · HL7 FHIR R5 Task · IHE XDW · ITU-T Y.3172 · ITU AI Readiness 2.0 |

**Vector KB built with the ITU reference code.** `python scripts/export_itu_kb.py --ingest
PATH/TO/ITUAIReadiness` writes every verified excerpt to `kb/itu_inputdocs/` in the ITU InputDocs format
and runs the ITU `ingest.py` (Ollama `nomic-embed-text`, ChromaDB, cosine) into `kb/chroma`: 82 clauses,
each carrying clause id, authority, jurisdiction, section, page and URL as metadata. With
`RESULTRELAY_RETRIEVAL=hybrid` the retriever fuses BM25 with the vector ranking (reciprocal-rank fusion).
The vector store only *ranks*: the text always comes from the verified, SHA-pinned index, so a vector hit
that is not a verified clause cannot be cited. Without the store or Ollama it falls back to BM25.

On seven plain-language questions ([evaluation/retrieval_check.md](evaluation/retrieval_check.md)), the
expected clause is in the top 5 for **hybrid 4/7, BM25 1/7**. For example, "send health data abroad cloud"
now finds Federal Law 2/2019 Art. 13. The questions are ours, so this is a smoke test, not a benchmark.

## Policy and standards gaps — [kb/gap_register.csv](kb/gap_register.csv)

| Gap | Type | Global comparison |
| :--- | :--- | :--- |
| **GR-15** TDRA's policy defines "delivery" only for marketing SMS, as network delivery to the subscriber (§1-23, §8-1); DHA ST-28 §11.1.3 needs a record of communication. Nothing joins them, or assigns responsibility for an accepted-but-lost clinical SMS | Coordination (health ↔ telecom) | RCPath G158 §5 (UK): alerts need feedback on whether "received, read, understood" |
| **GR-16** DHA ST-28 §11.1 provides for walk-in results to the patient, with no acknowledgment standard for a lay recipient of a critical value | Conflict between objectives | RCPath G158 §8: critical results "only communicated with the requesting clinical team" |
| **GR-11** Is the communication record an audit log (NABIDH §3.2.11: 3 years) or health data (Law 2/2019 Art. 20: 25 years)? | Standards ambiguity | RCPath G158 §7 names the record's fields, leaves retention local |
| **GR-17** DHA PP-09 requires agreed accountability, independent validation and AI-incident reporting, but names no default owner, validator or deadline; its revision date (1 July 2026) has passed | AI governance | EU AI Act (Reg. 2024/1689) Art. 14, 26, 73 |
| **GR-03** No retrieved source sets an acknowledgment clock for walk-in results | Unclear responsibility | Joint Commission NPSG.02.03.01 leaves the time frame to the organisation |
| **GR-18** No route for a clinical SMS to show it is not marketing (quiet hours 9pm–7am, §8-3) | Implementation | none retrieved |

17 entries in total; each lists the sources reviewed, what they establish, what remains unclear and the
product control that follows. PDPL (Federal Decree-Law
45/2021) is cited only for its scope exclusion: **Article 2, exclusion (e)** — health data governed by
its own legislation.

## Run it

```bash
python -m pip install -r requirements.txt
python -m pytest -q                          # 248 tests (one skips unless every source text is cached)
python run_demo.py                           # five scenarios; the agent council replays recorded answers offline
python scripts/run_evaluation.py             # 99-run matrix → evaluation/report.md
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
`cd web && npm ci && npm run build`. The build has no authentication: bind to 127.0.0.1 and use synthetic
data only.

## Repository

```
app/          gateway: agents/, multiagent/ (council, providers), advisers/ (guard, residency), orchestration/ (gate, engine),
              state_machine/, transport/, kb/ (ingest + verified retrieval), audit/, api/, static/ (built UI)
web/          React console (CaseTimeline, Simulator, Standards & gaps, Evaluation, Audit, Decision trace)
kb/           records/ (verified excerpts) · index/ (pinned) · framework/ (Y.3172 + Readiness mappings) · itu_inputdocs/
scenarios/    S1–S8 staged event streams · expected/ (assertions)
evaluation/   report.md · results/latest.json · agent_runs/ (recorded adviser responses)
submission/   technical report · design brief · build scripts
docs/         architecture, REPORT, audit disposition, design notes
tests/        248 tests
```

## License

[MIT](LICENSE). Source documents belong to their issuing bodies and are not redistributed; quotations are
minimal and attributed with section and page.
