# Architecture

ResultRelay is a policy-governed workflow for one narrow, high-risk administrative act: telling a
patient that a laboratory result they are waiting for is ready. It does not interpret results, it
does not decide what is critical, and it does not give advice. It decides **whether, through
which channel, and with what evidence** a communication may happen — and it refuses to call that
communication complete until a person has acknowledged the specific result that was sent.

That narrowness is the design. Every interesting failure in this domain is a confusion between
things that are adjacent: *accepted* versus *delivered*, *delivered* versus *acknowledged*,
*relevant* versus *applicable*, *a design decision* versus *a legal requirement*.

---

## 1. Shape of the system

```
                       ┌───────────────────────────────────────────┐
   scenario (JSON)     │            orchestration                  │
  ────────────────────▶│  engine ──▶ agents ──▶ gate ──▶ machine    │
   synthetic events    │    │                    │           │     │
                       │    │                    │           ▼     │
                       │    │                    │    state transition
                       │    ▼                    ▼           │     │
                       │  event store      audit chain       │     │
                       │  (SQLite)         (SHA-256)         │     │
                       └────┬───────────────────┬───────────┬┘     │
                            │                   │           │      │
        ┌───────────────────┴───┐   ┌───────────┴────┐  ┌───┴──────┐
        │ knowledge base        │   │ transport      │  │ REST API │
        │ 44 verified excerpts  │   │ simulator      │  │ + React  │
        │ BM25 + scope filter   │   │ (no network)   │  │ UI       │
        └───────────────────────┘   └────────────────┘  └──────────┘
```

Six modules, each with one job and no upward dependencies:

| module | responsibility | may not |
|---|---|---|
| `kb/` | hold verified quotations; retrieve with an applicability filter | invent text, rank a foreign rule as binding |
| `agents/` | produce a typed assessment from a *declared subset* of the case | change state, call the transport, see other agents' outputs |
| `orchestration/gate.py` | decide whether a proposed action may proceed | be overridden by an agent |
| `state_machine/` | define which transitions exist and which are forbidden | know about policies or channels |
| `transport/` | simulate an asynchronous network honestly | report acceptance as delivery |
| `audit/` | append hash-chained entries | allow update or deletion |

The rule that keeps this honest: **policy rules live in exactly one place** (the evidence, plus
the gate that consumes it) and **state rules live in exactly one place** (the transition table).
An earlier iteration put a `case_scope == "GENETIC"` branch inside an agent; every baseline then
"passed" the genetic scenario by construction, because the check followed the baseline rather
than the case. The scope decision now comes from evidence (`scope_permitted`) and is enforced by
the gate.

---

## 2. Request path, step by step

A scenario step is one released event. For each one:

1. **Event is stored** (`events`) with a sequence number, actor and layer, and appended to the
   audit chain as `event.received`.
2. **Contexts are built.** Each agent receives a named subset of case facts
   (`information_available` records exactly what it got). The delivery agent never sees patient
   identity; the clinical agent never sees the transport ledger.
3. **Agents run** and return a validated `AgentAssessment` — status, recommended action, citations,
   conditions checked and unresolved, confidence, and a one-paragraph rationale. A malformed
   assessment is rejected rather than repaired.
4. **The orchestrator forms one proposal.** It is a *proposal*: it has no authority.
5. **The gate decides.** `enforce()` checks evidence basis, fallback authorisation, revision
   consistency, acknowledgment scope, approval requirements and the scope flag, then maps the
   decision onto the transition table. An agent cannot widen its own permissions; the gate reads
   the case, not the agent's confidence.
6. **The state machine resolves** the (state, event) pair. Forbidden pairs win over permissive
   rules; conflations (transport observation → human completion) are structurally unreachable.
7. **Effects are applied** — a tool call to the simulated transport, a revision change, an
   approval record — and both the transition and its reason are stored.
8. **Downstream events** produced by the tool (provider acceptance, receipt, timeout) re-enter at
   step 1 as new events with their own layer. That is why an accepted message cannot silently
   become a delivered one: they are different events, in a different layer, requiring a different
   guard.

A case can leave this loop only through a state that requires a current-revision acknowledgment
and recorded documentation, or by being escalated to a named human role. There is no
"give up and close" path.

---

## 3. The three distinctions the system is built around

### 3.1 Acceptance, delivery, acknowledgment

| fact | produced by | proves |
|---|---|---|
| transmission accepted | provider API returned an id | a message was taken by the gateway |
| delivery confirmed | endpoint receipt bound to an attempt id | the channel reached the patient's device |
| acknowledged | a human act, bound to a specific revision | a person has the content |

The transport simulator produces the first two, never the third. The transition table has a
`CONFLATIONS` check that refuses any rule mapping a transport event onto a human-completion
state, so the distinction survives future edits rather than relying on reviewers to notice.

The simulated transport models timeout as **absence of information**, not failure: a timeout sets
`accepted = False`, `delivered = False`, `failed = False`, and only reconciliation can resolve it.

### 3.2 Unknown is a state, not an error

`DELIVERY_STATE_UNKNOWN` is a first-class state with an inbound rule and no outbound shortcut.
From it, the only permitted actions are reconciliation or escalation; a new transmission is
forbidden (`INV-4`) because sending again while the first message may have arrived is how
patients get two conflicting results.

### 3.3 Revisions, not "the result"

A result is a lineage. A corrected result creates a new revision that supersedes the old one, and
**every downstream artefact is bound to a revision id**: the attempt, the receipt, the
acknowledgment, the documentation. An acknowledgment of revision 1 says nothing about revision 2,
which is the failure the S2 and S5 scenarios exist to expose. Re-communicating a superseded
result also requires a named human approval, because the first message already left the building.

---

## 4. Standards

### 4.1 Why standards are classified before they are used

The system talks about Dubai-licensed laboratories, but most of the world's explicit text on
critical-result reporting comes from elsewhere. Mixing those up is the single most common way a
policy prototype becomes misleading: a US accreditation goal gets quoted as if it applied in
Dubai, and the artefact looks more authoritative than the evidence behind it.

Every excerpt therefore carries a claim classification, and only one class can bind:

| classification | meaning | may block an action |
|---|---|---|
| `BINDING_REQUIREMENT` | in force for this jurisdiction and facility type | yes |
| `OFFICIAL_GUIDANCE` | issued by an authority but advisory | no (informs wording) |
| `INSTITUTIONAL_PROCEDURE` | the facility's own written process | yes, as an institutional control |
| `GLOBAL_COMPARATOR` | another jurisdiction or a voluntary standard | no — never |
| `PRODUCT_DESIGN_CONTROL` | a build decision with no upstream source | recorded as such |
| `RESEARCH_HYPOTHESIS` | a claim to be tested | no |
| `UNRESOLVED` | sources conflict or are silent | no (raises a gap) |

Only `S1` (DHA Standards for Clinical Laboratory Services, Issue 2) and `AD1` (HAAD/DoH Abu Dhabi
Clinical Laboratory Standards) are binding, each inside its own emirate; for a Dubai case `AD1`
is a comparator. A test asserts this: *only the local and federal layers can be binding for a Dubai
case*.

Jurisdiction is layered, not a single label. `retriever.JURISDICTION_LAYERS` widens a case upwards:

| case jurisdiction | material that can bind it |
|---|---|
| AE-DU | `AE-DU`, `AE-FED` |
| AE-AZ | `AE-AZ`, `AE-FED` |
| AE-FED | `AE-FED` |

The widening is one-directional — a Dubai policy never binds an Abu Dhabi case — and it exists
because the instrument that actually governs health data in the UAE is federal (Federal Law 2/2019),
so exact-match filtering would have excluded the governing law from every case.

### 4.2 What the binding evidence actually says — and does not say

Verified excerpts (all 44 are machine-checked against the source text; see §4.4):

- **§11.1** — Dubai laboratories may accept walk-in patients only for tests that do not require a
  physician's order, per a permitted list (Appendix 3).
- **§11.1.1** — critical results shall be reported clearly to the patient.
- **§11.1.2** — the laboratory *should* direct the patient to seek further medical advice
  (advisory, and the reason the patient message contains no interpretation).
- **§11.1.3** — the laboratory shall keep a record of the communication.
- **§9.1.5(e)** — a policy for identifying and reporting critical results.
- **§9.1.5(f)** — the laboratory shall define the expected turnaround time *in its own internal
  policy*. This is the clause that decides how the no-clock finding is written: the instrument
  delegates the clock, so the prototype must not invent a statutory one.
- **§9.1.5(g)** — corrections must identify the corrected result as revised, with date and time,
  and both original and corrected reports must be retained.
- **§13.3–13.5, Appendix 3** — genetic tests require a prescription, a consultant is involved
  before and after testing, and genetic results **shall not be communicated to patients directly**.

That last clause is why scope is an evidence-driven input rather than a setting: a genetic result
in the same walk-in queue may not take the patient-direct path at all, and the system must be able
to prove it knew that.

**What is absent matters too.** No retrieved Dubai clause sets a numeric acknowledgment clock, a
retry count, or a fallback-channel rule for walk-in results. Those values exist in
`app/policies/profile.py` and are labelled `PRODUCT_DESIGN_CONTROL`; the gap register records the
absence (`GR-01`, `GR-03`, `GR-04`). "We did not find it" is written as a gap, never as
"therefore it is permitted".

### 4.3 Comparators are kept, not discarded

US and international sources are retained because they show how other regimes solved the same
problem — ONC SAFER asks whether the record tracks a result to *acknowledged*; Joint Commission
NPSG.02.03.01 requires the organisation to define timeliness and to evaluate it; IHE XDW names the
race conditions that workflow documents must handle. They are cited as `GLOBAL_COMPARATOR` and the
UI renders that class next to the clause. One scenario (S6) exists specifically because a
retrieval-only system will present the Abu Dhabi read-back requirement as binding for a Dubai
case; the isolation test fails the moment the filter is removed.

### 4.4 Provenance is mechanical

`backend/app/kb/ingest.py` normalises each quotation (case, curly punctuation, and *all*
whitespace, because PDF extractors break words mid-token) and requires it to appear as a
contiguous substring of the declared page. A quote on the wrong page fails even if it exists
elsewhere in the document. Excerpts that fail are excluded from the index, so retrieval cannot
cite them. Sources are fetched at build time into `~/.cache/resultrelay/sources` from the issuing
bodies and are not redistributed; only minimal necessary quotations are committed.

Current state: **44 excerpts, 44 verified, 0 unverified, 0 rejected.**

ITU-T Y.3172 §8.1 is used descriptively to name the components (source, collection, preprocessing,
model, policy, decision, sink). No conformance claim is made, and the mapping file records two
requirements as `NOT IMPLEMENTED` rather than stretching them.

---

## 5. The four configurations

The same engine runs four ways so that a reviewer can see which control is doing the work. They
are not strawmen: each is a plausible way to build this system.

| configuration | knowledge base | applicability filter | invariants | acknowledgment scope | transport semantics |
|---|---|---|---|---|---|
| `resultrelay` | yes | yes | yes | revision-bound | strict |
| `policy_blind` | no | n/a | no | any | optimistic |
| `retrieval_only` | yes | **no** | no | any | optimistic |
| `static_rules` | no | n/a | yes | revision-bound | strict |

`static_rules` is the fair comparison: a competent hand-coded rules engine. It gets the ordering
and the acknowledgment binding right and fails only where hard-coded rules cannot know something —
that a genetic result may not go to the patient, and that a clause belongs to another jurisdiction.

---

## 5b. The advisory boundary (a model may propose, never decide)

`backend/app/advisers/` is the only place a model is allowed to exist, and by default nothing does.

```
case snapshot ──► advisers.guard.advise() ──► AdvisoryRecord ──► gate.enforce(advisory=...)
                          │                                            │
                refuse before the model runs                 decision already computed
                (residency / disabled)                       (advisory attached afterwards)
```

| check | rule | failure status |
|---|---|---|
| boundary | closed unless `RESULTRELAY_ENABLE_LLM` is set *and* an adviser is supplied | `DISABLED` |
| residency | Art. 13: out-of-country endpoints refused unless a named Health Authority resolution is recorded | `REFUSED_RESIDENCY` |
| citations resolve | every cited chunk id must exist in the corpus | `REJECTED_UNGROUNDED` |
| citations apply | every cited chunk must be from the applicable jurisdiction set (Dubai + federal for a Dubai case) | `REJECTED_OUT_OF_JURISDICTION` |
| shape | the proposal must be over the known action set; an exception is not authority | `REJECTED_MALFORMED` |
| classification | whatever survives is `PRODUCT_DESIGN_CONTROL`, never policy | `ADVISORY_ONLY` |

The gate computes its decision first and receives the advisory record afterwards, in
`gate.enforce`. When the adviser disagreed, the record says so (`advisory_overruled`) and the
conditions list states that the proposal was not read while deciding. The test that matters is
`test_the_gate_decision_is_identical_with_and_without_an_adviser`: it asserts the enforced action,
the permitted flag, the invariant and the blocked-action list are unchanged when an accepted
proposal is attached.

Two honesty notes. The residency check reads the endpoint string; it cannot see DNS, a proxy, or a
model shipped inside a desktop binary. And no model client is implemented: the only adviser in the
tree is a deterministic stub, so what is tested is the *guard*, not the quality of any model.

## 6. Persistence and audit

SQLite via SQLAlchemy, twelve tables: cases, result revisions, events, communication attempts,
delivery receipts, acknowledgments, policy assessments, agent messages, source citations, state
transitions, escalation requests, audit log, evaluation runs.

Two implementation notes that matter for trust:

- **Rows are keyed per run.** Attempt ids restart at `ATT-001` each run, so the store namespaces
  them (`run_id:attempt_id`). Without this, a second run silently dropped its own acknowledgments
  behind a primary-key collision — found by looking at the database rather than the engine.
- **The audit chain is re-verified when read.** `verify_entries()` recomputes every hash from the
  stored rows; the API never reports "valid" merely because the writer said so. Editing one
  summary or deleting one entry changes the reported broken sequence numbers.

An exported bundle contains the scenario, configuration, event stream, assessments, gate
decisions, attempts, receipts, acknowledgments, approvals, citations and the chain — enough for a
reviewer to re-run the same scenario and compare state signatures.

---

## 7. What this architecture does not claim

- It is not a medical device and performs no clinical function.
- Passing a scenario shows internal consistency with a cited clause, not compliance with a
  regulation, and certainly not patient safety in the real world.
- The transport is simulated; latency, retries and provider behaviour are scripted.
- The agent set is deterministic. No model is called at runtime, which is a deliberate choice for
  reproducibility — the LLM boundary is a defined interface (`mode: "DETERMINISTIC" | "LLM"`) that
  remains unused.
- Coverage is the scenario set, authored by the same team that built the engine, and reported as
  such in `evaluation/report.md`.
