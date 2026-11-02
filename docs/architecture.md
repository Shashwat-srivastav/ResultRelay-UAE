# Architecture

*Current as of 2 November 2026. Every claim below can be checked against the file it names. For
results (scenario pass rates, council-on vs council-off, retrieval checks) see `README.md` and
`evaluation/report.md`. This document gives no numbers that depend on an evaluation run.*

## 1. Purpose

ResultRelay governs one narrow, high-risk administrative act: telling a walk-in patient of a
DHA-licensed laboratory (or, for a genetic result, the referring physician) that a critical result
is ready, and proving that the right person received the current revision of that result. It does
not interpret results, decide what is critical, or give clinical advice. It decides **whether,
through which channel, to whom and on what evidence** a communication may happen, and it will not
call a communication complete until a named person has acknowledged the specific revision that was
sent. A deterministic core (state machine, gate, invariants, simulated transport, hash-chained
audit) decides every transition. A council of LLM agents reads the policy text and what people
said, and its only possible effect on a case is to open an escalation to a person.

All data is synthetic (`SYN-*` references). The transport is simulated and contacts no network
(`REAL_NETWORK_ACCESS = False` in `app/transport/simulator.py`).

## 2. Component view

```
 scenario steps (scenarios/*.json)          runtime-injected events
 POST /api/runs  · /step · /play            POST /api/runs/{id}/events
            \                                   /
             v                                 v
 +------------------------------------------------------------------+
 | EVENT GATEWAY  app/api/routes.py, app/orchestration/engine.py     |
 | event validated against EventType; event.received / .injected    |
 | appended to the audit chain before it is applied                  |
 +------------------------------------------------------------------+
             |
             v
 +------------------------------------------------------------------+
 | DETERMINISTIC CASE SERVICES                                       |
 | state machine (app/state_machine/)  transport (app/transport/)    |
 | five rule-based assessors (app/agents/): lab_workflow,            |
 | policy_applicability, network_delivery, escalation_coordinator,   |
 | audit_governance -> one PROPOSAL (no authority)                   |
 +------------------------------------------------------------------+
             |                         ^
             v                         | verified chunks only
 +---------------------------+   +--------------------------------+
 | EVIDENCE RETRIEVAL        |<--| KNOWLEDGE BASE                 |
 | app/kb/retriever.py       |   | kb/source_register.csv (23)    |
 | BM25 + jurisdiction filter|   | kb/records/*.yaml              |
 | optional hybrid ChromaDB  |   | kb/index/chunks.json (93,      |
 | (app/kb/vector.py)        |   | each verified at ingest)       |
 +---------------------------+   +--------------------------------+
             |
             v      (configuration resultrelay_council only)
 +------------------------------------------------------------------+
 | AGENT COUNCIL  app/multiagent/council.py (providers.py)           |
 |  1 Policy Evidence Analyst (LLM, DHA lens)                        |
 |  2 Institutional analyst (LLM, TDRA lens) - only if transport     |
 |    is unresolved                                                  |
 |  3 Adversarial reviewer (LLM, by default another model family)    |
 |  [residency guard app/advisers/residency.py before every live     |
 |   model call]                                                     |
 +------------------------------------------------------------------+
             |
             v
 +------------------------------------------------------------------+
 | INDEPENDENT ASSURANCE (code): fact_check, policy-rules check,     |
 | detect_conflicts; one feedback round -> CORRECTED/UPHELD/DISPUTED |
 +------------------------------------------------------------------+
             |
             v
 +------------------------------------------------------------------+
 | DETERMINISTIC ORCHESTRATOR  council.orchestrate()                 |
 | PROCEED (the gate decides) or ESCALATE (named owner, deadline)    |
 +------------------------------------------------------------------+
             |
             v
 +------------------------------------------------------------------+
 | GATE  app/orchestration/gate.py  -- reads structured fields only, |
 | never agent text; applies invariants; maps proposal -> event      |
 +------------------------------------------------------------------+
             |
             v
 +------------------------------------------------------------------+
 | EXECUTION + AUDIT  engine.perform_action / escalate,              |
 | action.performed | action.failed | action.blocked,                |
 | escalation.overdue; app/audit/log.py hash chain; SQLite store     |
 | (app/models/db.py); console in app/static/app (built from web/)   |
 +------------------------------------------------------------------+
```

Module responsibilities:

| module | responsibility | may not |
|---|---|---|
| `app/state_machine/` | define the 18 states, 17 event types, which transitions exist and which are forbidden | know about policies, models or channels |
| `app/agents/` | five rule-based assessors, each reading a declared subset of the case (`allowed_fields`) | change state, call the transport |
| `app/orchestration/gate.py` | decide whether a proposed action may proceed | read free text; be overridden by an agent |
| `app/orchestration/engine.py` | run one step: record event, assess, deliberate, gate, execute, audit | execute an action the gate did not permit |
| `app/multiagent/` | the council and its model providers | send, close or change a case |
| `app/advisers/` | residency guard (used by the council); an older single-adviser path behind `RESULTRELAY_ADVISE`, off by default | let a model output become an action |
| `app/kb/` | ingest and verify quotations; retrieve with an applicability filter | index a quote it cannot find on the declared page |
| `app/transport/simulator.py` | simulate an asynchronous network | report acceptance as delivery |
| `app/audit/log.py` | append hash-chained entries; re-verify on read | update or delete an entry |

## 3. ITU-T Y.3172 mapping

The mapping is descriptive, not a conformance claim. It matches
`kb/framework/itu_y3172_mapping.csv` (rows Y1–Y11); clause references are to F1 (ITU-T Y.3172
(06/2019)) in the KB.

| Y.3172 node | ResultRelay component | code |
|---|---|---|
| SRC (source) | synthetic laboratory, transport and human event streams; the verified policy corpus | `scenarios/*.json`, `kb/index/chunks.json`, `POST /api/runs/{id}/events` |
| C (collector) | event ingestion: each event is recorded in the hash chain before it is applied | `app/orchestration/engine.py` |
| PP (preprocessor) | normalisation into case state, revision binding, transport reconciliation, jurisdiction-filtered retrieval; the case view given to agents (`_case_view`) | `engine.py`, `app/kb/retriever.py`, `app/transport/simulator.py` |
| M (model) | Policy Evidence Analyst and conditional TDRA-lens analyst (LLMs), adversarial reviewer (LLM); typed judgments with probabilities | `app/multiagent/council.py`, `app/multiagent/providers.py` |
| P (policy) | deterministic assurance (fact check, policy-rules check, conflicts) and the gate's invariants decide what may happen | `council.py`, `app/orchestration/gate.py` |
| D (distributor) | execution of permitted actions to the right sink; failed actions audited and escalated | `engine.py` (`perform_action`, `FAILED_TOOL_OUTCOMES`) |
| SINK | mock transport, supervisor queue with owner and deadline, communication record | `app/transport/simulator.py`, `app/api/routes.py` |
| MLFO (ML function orchestrator) | deterministic orchestrator: chains SRC to SINK per step, decides when the council runs and whether to escalate; no LLM coordinator | `engine.py`, `council.py` |

The CSV adds three rows outside the eight nodes: Y9 (ML sandbox as containment: residency guard,
gate, replay), Y10 (P constrained by an external legal layer: only clauses that bind the case
jurisdiction can block or authorise), and Y11 (audit of the pipeline, which Y.3172 does not
specify).

## 4. The deterministic core

### 4.1 States

`app/state_machine/states.py` defines 18 states in four families that are deliberately kept apart:

| family | states |
|---|---|
| laboratory record | `RESULT_DRAFT`, `RESULT_FINALIZED` |
| sender intent | `TRANSMISSION_QUEUED`, `TRANSMISSION_ATTEMPTED` |
| network-observed | `TRANSPORT_ACCEPTED`, `DELIVERY_CONFIRMED`, `DELIVERY_FAILED`, `DELIVERY_STATE_UNKNOWN` |
| human-observed | `CLINICAL_ACKNOWLEDGMENT_CONFIRMED`, `COMMUNICATION_DOCUMENTED` |
| workflow control | `RETRY_PENDING`, `ESCALATION_REQUIRED`, `ESCALATION_IN_REVIEW`, `CORRECTION_PENDING` |
| corrected result | `CORRECTED_RESULT_FINALIZED`, `CORRECTED_RESULT_DELIVERY_PENDING`, `CORRECTED_RESULT_ACKNOWLEDGED` |
| terminal record | `SUPERSEDED` |

Only `COMMUNICATION_DOCUMENTED` and `CORRECTED_RESULT_ACKNOWLEDGED` count as complete
(`is_complete`). `DELIVERY_STATE_UNKNOWN` is a first-class state: an absence of information, not
an error.

### 4.2 How a (state, event) pair is resolved

`transitions.evaluate()` applies, in order:

1. **Forbidden pairs** (`FORBIDDEN`, 2 rules) win over any permissive rule.
2. **Informational events** (`patient.callback_no_access`, `channel.fallback_proposed`,
   `policy.source_updated`) are recorded with status `RECORDED` and never move the state.
3. **Transition rules** (`TRANSITIONS`, 22 rules): the first rule whose guard passes applies,
   unless its target is forbidden for that event by a **conflation rule** (`CONFLATIONS`, 5 rules),
   which blocks it even if a future edit adds a permissive rule.
4. Otherwise `NO_RULE`: the case is unchanged and the event is kept for human review.

### 4.3 Invariants

The invariant identifiers below are the ones used in `app/state_machine/transitions.py` and
`app/orchestration/gate.py`. (There is no `INV-7` in the code.)

| id | rule | where enforced |
|---|---|---|
| INV-1 | a transmission request or provider acceptance cannot establish delivery or acknowledgment | `CONFLATIONS` (`transport.accepted`, `transmission.requested`) |
| INV-2 | an endpoint receipt is not human acknowledgment | `CONFLATIONS` (`transport.delivery_receipt`) |
| INV-3 | a timeout is an absence of information; an unmatched receipt cannot confirm delivery | `CONFLATIONS` (`transport.timeout`), `g_receipt_matches_attempt` |
| INV-4 | no new transmission from `DELIVERY_STATE_UNKNOWN`; no retry before the prior attempt is reconciled | `FORBIDDEN`, `g_retry_reconciled` |
| INV-5 | idempotency: a duplicate receipt is refused; the attempt's stored state, not the payload, decides novelty | `g_receipt_matches_attempt`; idempotency keys in the simulator |
| INV-6 | a corrected result must reference the revision it supersedes; a receipt for an older revision cannot confirm the current one | `g_correction_reference`, `g_receipt_matches_attempt` |
| INV-8 | an acknowledgment counts only for the current revision; an acknowledgment arriving while delivery is unconfirmed cannot close the loop | `g_ack_matches_current_revision`, `FORBIDDEN` |
| INV-9 | an unavailable channel never authorises an alternative by itself: a fallback needs a declared excerpt field (`DECLARED_EXCERPT_FIELD`) or an approved institutional procedure | `MachineContext.fallback_authorised`, gate step 2 |
| INV-10 | a case cannot close while conditions are unresolved; an acknowledgment alone is not a communication record | `g_documentation_complete`, `CONFLATIONS` |
| SCOPE_EXCLUSION | a send is blocked when the policy evidence says direct patient communication is not permitted for the scope and the recipient is not the physician | gate step 2b |
| HUMAN_APPROVAL | a transition marked `requires_approval` (e.g. re-communicating a superseded result) is withheld until a named approval is recorded | gate, end of `_enforce` |

The gate also requires an evidence basis for high-risk actions (`SEND_PRIMARY`,
`RETRY_SAME_CHANNEL`, `PROPOSE_FALLBACK`, `RECORD_DOCUMENTATION`): an applicable source citation
or a declared `PRODUCT_DESIGN_CONTROL`. Reconciliation is always permitted because it is a
read-only query of the transport ledger.

### 4.4 The rule-based assessors

Five deterministic assessors in `app/agents/` each read only their declared `allowed_fields` and
return a validated `AgentAssessment`. The orchestrator ranks their proposals with a conservative
ordering (`_proposal_order` in `gate.py`: escalation first) and forms one proposal. The policy
assessor (`policy_applicability.py`) sets `scope_permitted`, `recipient` and fallback evidence
from **declared fields on verified excerpts** (`routes_to_physician`, `authorises_fallback`), not
from keyword matching. The gate sees only those structured values.

### 4.5 Transport and revisions

`app/transport/simulator.py` records provider acceptance, endpoint receipt and failure as separate
facts per attempt; a timeout produces no delivery evidence; every send carries an idempotency key
and a repeat returns the original attempt; reconciliation is the only way to turn an unknown
outcome into evidence. `receipt_recorded` is set only when a receipt *event* is applied, which is
what the duplicate-receipt guard reads. Every attempt, receipt and acknowledgment is bound to a
result revision id.

### 4.6 Configurations

`CONFIGS` in `engine.py` holds 12 configurations: the full system `resultrelay`; three compound
baselines (`policy_blind`, `retrieval_only`, `static_rules`); seven one-flag ablations of
`resultrelay` (`ablate_no_kb`, `ablate_no_applicability_filter`, `ablate_no_invariants`,
`ablate_no_audit_agent`, `ablate_full_context`, `ablate_ack_any`,
`ablate_optimistic_transport`); and `resultrelay_council`, which differs from `resultrelay` in
one input, the council. `static_rules` has the genetic-results rule hard-coded
(`hardcoded_genetic_rule=True`), as a competent rules engine would. **The council runs only in
`resultrelay_council`**; baselines and ablations never call a model (`Orchestrator._council`).
The evaluation runner (`app/evaluation/runner.py`) runs all of `CONFIGS` by default.

## 5. The agent council

### 5.1 Protocol, step by step

`Council.deliberate()` runs at every decision point (`kind: action`; `RESULTRELAY_AGENT_STEPS=all`
for every step). Agents answer **typed questions** (a choice among named options, a probability, or
a score) over a JSON case view; `providers.validate()` rejects any answer that is not one of the
named options or not a probability in [0, 1], and the question is marked invalid rather than
repaired.

| # | actor | sees | produces | can change |
|---|---|---|---|---|
| 1 | **Policy Evidence Analyst** (LLM, DHA lens) | `_case_view` (scope, jurisdiction, state, this step's event, current revision, recipient route, last 4 attempts, recent non-decision events (from the last 4) in the reporter's words, acknowledgments, elapsed minutes, configured window); the action under review; up to 4 clauses from sources S1, U1, U3, U6, U7 | `obligation` (COMMUNICATED / AWAITING_ACK / DIRECT_NOT_PERMITTED / NOT_YET_SENT / INSUFFICIENT_EVIDENCE), governing `clause`, `settled` probability, `gap` (GR-linked), optional one extra `kb_search` (read-only), rationale | nothing directly |
| 2 | **Institutional analyst** (LLM, TDRA lens) — only when `transport_unresolved()` (attempts for the current revision, none with a receipt) | same case view; clauses from U8, U10, G6 | `telecom_covers` probability, closest telecom `clause`, rationale | nothing directly |
| 3 | **Adversarial reviewer** (LLM; by default a different model family) | case view, applicable clauses, and each analyst's claim with the cited clause text | typed `objection` (ACCEPTANCE_AS_DELIVERY, STALE_REVISION_ACK, SCOPE_ROUTES_ELSEWHERE, UNAPPROVED_CHANNEL, RETRY_BEFORE_RECONCILE, ACK_WINDOW_EXPIRED, UNVERIFIED_RECIPIENT, TEXT_CONTRADICTS_RECORD or NONE), `own_reading` of the obligation, per-claim `<role>_supported` and `<role>_issue`, an `alternative` action | nothing directly |
| 4 | **Independent assurance** (code) | all answers and the case view | `fact_check` (claims against the record, e.g. "communicated" with no acknowledgment of the current revision); policy-rules check (a comparator or out-of-jurisdiction clause cannot govern); verification of the reviewer's objection against the record (`OBJECTION_REJECTED` if it does not fit) | marks claims as flagged |
| 5 | **Feedback** (one round) | a flagged analyst gets its previous answer plus the findings | revised answer → `CORRECTED`, `UPHELD`, or `DISPUTED` (still failing a check; kept in the trace, never relied on) | the analyst's own answer |
| 6 | **Deterministic orchestrator** (`orchestrate()`) | messages, reviews, `detect_conflicts()` output | `PROCEED` or `ESCALATE` with a reason | see 5.2 |

`detect_conflicts()` reports `READINGS_DIFFER`, `OBJECTION` (surviving the code check),
`UNSETTLED_HIGH_RISK`, `TELECOM_GAP` (GR-15) and `SCOPE_CONFLICT` (which now checks the recipient
route, so a physician-routed send is not a conflict). `orchestrate()` escalates on: a surviving
reviewer objection with confidence ≥ 0.5 (≥ 0.7 for `TEXT_CONTRADICTS_RECORD`, which code cannot
verify); a disputed analyst claim on a high-risk step; or a high-risk step the binding clauses do
not settle **and** on which analyst and reviewer readings differ. A gap on its own is recorded in
`rt.unresolved`, not escalated. There is no LLM coordinator.

### 5.2 What the agents can and cannot do

The gate never reads council output. If the orchestrator says `ESCALATE` and the case is not
already with a person or documented (`COUNCIL_NO_ESCALATE_STATES`), the engine either replaces the
proposal at a decision point with `ESCALATE_HUMAN` (which the gate then evaluates like any other
proposal) or opens a named escalation via `Orchestrator.escalate()`. **The agents can never send,
close or change a case: their only possible effect is an escalation.** Every agent message, tool
call, assurance review and orchestrator decision is appended to the hash chain (`agent.message`,
`agent.tool_call`, `assurance.review`, `orchestrator.decision`, `council.escalation`).

Scenario S9 (`scenarios/S9-reply-from-someone-else.json`) is the case the rules cannot see: a
structurally valid acknowledgment whose words show the reply came from someone else. Its expected
file sets `requires_council: true`.

### 5.3 Providers

`app/multiagent/providers.py` offers `ollama` (local; preset `qwen2.5:14b` at
`http://localhost:11434/v1`), `mistral` (`mistral-small-latest`), `openai` (any OpenAI-compatible
endpoint), `jev` (TypeSafe Jev, which answers typed questions natively) and `replay` (recorded
answers only). `RESULTRELAY_AGENT_PROVIDER` sets every role; `RESULTRELAY_ANALYST_PROVIDER`,
`RESULTRELAY_INSTITUTION_PROVIDER` and `RESULTRELAY_REVIEWER_PROVIDER` (with matching `_MODEL`,
`_URL`, `_REPLAY_FROM`) override one role. With nothing configured, `resultrelay_council` uses
`RECOMMENDED_REPLAY`: recorded Mistral answers for the analysts and recorded Jev answers for the
reviewer.

Chat models are asked for one JSON object plus a top-level `rationale` (one or two sentences
citing case facts and the clause id). A Jev answer has no prose; its rationale is the typed
judgment with probabilities (`source: typed-judgment`). Every live request and response is written
to `evaluation/agent_runs/agent-<kind>-<digest>.json`, keyed on a hash of the exact state and
questions; a replay is refused, not guessed, if either changed.

## 6. Failure handling

| failure | handling | where |
|---|---|---|
| a permitted action cannot be carried out (`NO_PHYSICIAN_CHANNEL`, `CHANNEL_NOT_AUTHORISED`, `NOT_AUTHORISED`, `NO_FALLBACK_CONFIGURED`) | logged as `action.failed` (not `action.performed`), added to `rt.unresolved`, and escalated | `FAILED_TOOL_OUTCOMES`, `Orchestrator.step` in `engine.py` |
| blocked proposal | `action.blocked` with the invariant | `engine.py` |
| unknown delivery (timeout, status unknown) | `DELIVERY_STATE_UNKNOWN`; new sends forbidden (INV-4); only reconciliation or escalation | `transitions.py`, simulator `reconcile` |
| accepted, never delivered | stays `TRANSPORT_ACCEPTED`; never becomes delivered or communicated (S8) | `CONFLATIONS` |
| escalation not answered | each escalation carries `role`, `due_by_minutes` and `tier`; the deadline is `escalation_response_minutes` from the profile, which `app/policies/profile.py` does not set, so the engine default of 30 minutes applies; past the deadline a tier-2 escalation is raised (profile `escalation_role_tier2`, default `CLINICAL_LEAD`) and `escalation.overdue` is audited | `Orchestrator.escalate`, start of `Orchestrator.step` |
| model provider unavailable, error or invalid JSON | that agent's message is `UNAVAILABLE` (or answers `PARTIAL` with invalid ids); the council proceeds with what is trusted; the gate is unaffected | `Council._ask` |
| residency refusal | message `REFUSED_RESIDENCY`; no request is sent | `providers.Provider.ask`, `residency.authorise` |
| replay miss | `ProviderError` → `UNAVAILABLE` | `providers.Provider.ask` |

Because the gate never depends on the council, a council that is degraded, refused or absent can
only mean fewer escalations from the agents; it cannot unblock anything.

## 7. Data residency

Before any live model call, `Provider.ask` calls `app/advisers/residency.authorise()`. The rule
is Federal Law No. 2 of 2019, Art. 13 (no storing, processing, generating or transferring health
data outside the State without a Health Authority resolution; penalty in Art. 24):

- a case whose case, patient and contact references are all `SYN-*` is `SYNTHETIC` and may use a
  hosted endpoint; the same endpoint is refused for a real case;
- loopback hosts and `.ae` names are treated as in country, but the decision is marked `nominal`:
  a name is not a location. If the operator supplies resolved addresses and in-country ranges
  (`RESULTRELAY_RESIDENCY_RESOLVED_IPS`, `RESULTRELAY_RESIDENCY_AE_CIDRS`), the address check
  decides, and an out-of-range address overrides an in-country name;
- anything else is refused unless a resolution reference is recorded
  (`RESULTRELAY_RESIDENCY_RESOLUTION`);
- whether a Ministerial Resolution No. 51 of 2021 exception applies is never decided in code: the
  official text was not retrieved, so the reason text sends that determination to a person.

The guard checks residency only. It cannot see network egress, proxies, or a model runtime's own
network access.

## 8. Knowledge base

| artefact | content |
|---|---|
| `kb/source_register.csv` | 24 sources with issuer, jurisdiction, version, official URL, legal status, verification class and limitations |
| `kb/records/*.yaml` | the committed excerpts: verbatim quotation, section, printed page, claim classification, topics, declared fields |
| `kb/.sources/<ID>.txt` | page-marked full texts (`===== PAGE n =====`), git-ignored, not redistributed; fetched by `scripts/fetch_sources.py` |
| `kb/index/chunks.json` | 93 chunks, each verified at ingest; pinned by `kb/index/pinned.sha256` |
| `kb/gap_register.csv` | policy gaps (GR-01 … GR-19; GR-13 retired) with sources, comparator and consequence |
| `kb/framework/itu_y3172_mapping.csv`, `kb/framework/ai_readiness_mapping.csv` | Y.3172 node mapping; the 13 AI Readiness dimensions as listed in the ITU reference code (`dimensions.json`) |

**Verification at ingest.** `app/kb/ingest.py` normalises each quotation (NFKC, punctuation,
case, all whitespace removed) and requires it to appear contiguously on the declared page(s). A
quote on the wrong page or absent is excluded from the index; a quote whose source text is not
cached is indexed as `UNVERIFIED_NO_CACHE` and never counted as verified. Each chunk carries
`excerpt_status` (the result of this check) and `verification_status` (the source's class from
the register).

**Verification classes** (register column `verification_status`):

| class | meaning | sources |
|---|---|---|
| `VERIFIED_OFFICIAL` | checked against the issuer's own published file | S1, AD1, G1–G7, G9, F1, F2, U3, U4, U6, U7 |
| `VERIFIED_OFFICIAL_REPOSITORY` | checked against an official repository copy (WIPO Lex) | U10 |
| `VERIFIED_MIRROR` | checked against an unofficial translation on a third-party mirror | U2 (PDPL; excluded for health data by its Art. 2(e)) |
| `VERIFIED_THIRD_PARTY_COPY` | checked against a copy hosted by a third party | U8 (TDRA Mobile Spam), G8 (EU AI Act) |
| `VERIFIED_TRANSCRIPTION` | checked against a hand-recorded transcription of the official page; this check is circular | U1, U5, AD2 |

`kb/sources/MANUAL_RETRIEVAL.md` lists the sources that cannot be downloaded by script and how to
add them.

**Claim classification.** Every excerpt carries one of `BINDING_REQUIREMENT`, `OFFICIAL_GUIDANCE`,
`INSTITUTIONAL_PROCEDURE`, `GLOBAL_COMPARATOR`, `PRODUCT_DESIGN_CONTROL`, `RESEARCH_HYPOTHESIS`,
`UNRESOLVED`. Only binding material for the case's jurisdiction can block or authorise an action.

**Retrieval** (`app/kb/retriever.py`): BM25 (k1 = 1.5, b = 0.75) by default. `scope="applicable"`
returns only jurisdictions that can bind the case (`JURISDICTION_LAYERS`: AE-DU → AE-DU + AE-FED;
AE-AZ → AE-AZ + AE-FED); `scope="comparator"` returns the rest, labelled as never applicable.
`RESULTRELAY_RETRIEVAL=hybrid` fuses BM25 with the ChromaDB store built by the ITU reference ingest
(`scripts/export_itu_kb.py --ingest`, Ollama `nomic-embed-text`, `app/kb/vector.py`); vector hits
only rank, and the text always comes from the verified index. If ChromaDB or Ollama is missing,
retrieval falls back to BM25 and says so. Arabic questions are expanded with English terms from
`ARABIC_GLOSSARY`; no Arabic quotation is stored, because the Arabic PDF text layers tried did not
extract cleanly.

## 9. Persistence, API and audit

- **Store.** SQLite via SQLAlchemy (`app/models/db.py`), one path for the whole app
  (`settings.db_path`, overridable with `RESULTRELAY_DB`), which is the path `/api/health` reports.
  Runs are also held in an in-memory registry bounded by `MAX_RUNS` (`app/api/runs.py`).
- **API** (`app/api/routes.py`, prefix `/api`): runs (`POST /runs`, `/runs/{id}/step`,
  `/runs/{id}/play`, `POST /runs/{id}/events` for runtime-injected events validated against
  `EventType`), traces (`GET /runs/{id}/trace`), audit (`/runs/{id}/audit`,
  `/cases/{id}/audit`, `/cases/{id}/integrity`, `/cases/{id}/bundle`), KB (`/kb/sources`,
  `/kb/search`, `/kb/chunks/{id}`), `/gaps`, `/mappings/{name}`, evaluation endpoints and
  `/health`.
- **Audit chain** (`app/audit/log.py`): each entry is SHA-256 over the previous hash and the
  canonical body, which includes `kb_index_sha256`, so the corpus in force is bound to each record.
  `verify_entries()` recomputes the chain from stored rows, so integrity is re-verified on read,
  not assumed.
- **Auth.** None by default. If `RESULTRELAY_API_KEY` is set, `app/main.py` requires `X-API-Key`
  (constant-time comparison) on every `/api` path except `/api/health` and the docs. There are no
  user accounts or roles. CORS has no wildcard; the default bind is `127.0.0.1`.

## 10. Known limits

- **Synthetic data only.** Every case is synthetic; the residency guard permits hosted models only
  for that reason.
- **Simulated transport.** No SMS gateway, LIS or EHR is contacted; latency and provider behaviour
  are scripted.
- **Author-written scenarios.** S1, S2, S3a, S3b, S4–S11 (twelve files) and their expectations in
  `scenarios/expected/` were written by the engine authors (`authorship: ENGINE_AUTHORS`,
  `independent_review: false`). There is no held-out or independently written set.
- **Hosted models, synthetic only.** Recorded runs use Mistral (hosted outside the UAE) and
  TypeSafe Jev (proprietary). The local reference model `qwen2.5:14b` is supported by the `ollama`
  preset but has **not yet been run end to end**.
- **Model runs are few.** Council results come from a small number of recorded runs; hosted models
  are not fully deterministic even at temperature 0.
- **Rule-based assessors.** The five assessors in `app/agents/` are deterministic rules; the
  invariants are written by the authors and not independently validated.
- **Audit integrity.** The audit is a hash chain without signatures or trusted timestamps: it
  detects edits to stored rows but not a rewrite of the whole chain by someone with write access.
- **Transcribed sources.** For U1, U5 and AD2 the verification is against a transcription made by
  the authors, so it proves consistency with that transcription, not with the official text.
- **Arabic.** Queries in Arabic work through a glossary; the stored quotations and the UI are
  English.
- **Residency.** Name-based unless addresses are supplied; MR 51/2021 exceptions are not decided.
- **Hybrid retrieval is opt-in.** `kb/chroma/` is git-ignored and built locally.
- **Auth.** No authentication by default; the optional API key is a shared secret, not an
  authorisation model.
