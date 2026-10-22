# ResultRelay — technical report

Generated from `evaluation/results/latest.json` (2026-10-22 17:32:21 UTC). 28 runs: 7 scenarios x 4 configurations.

> **These results are not evidence of clinical safety, clinical effectiveness or regulatory compliance.** All data is synthetic. The scenarios were authored by the same team that built the engine.

## 1. Summary

| configuration | safe scenarios | assertions | false closure | false delivery | stale ack | unauthorised channel | scope violation | comparator as binding | send provenance | replay |
|---|---|---|---|---|---|---|---|---|---|---|
| ResultRelay (policy-governed multi-agent) | 7/7 | 27/27 (100%) | 0 | 0 | 0 | 0 | 0 | 0 | 1.00 | stable |
| Policy-blind baseline (no knowledge base) | 3/7 | 23/27 (85%) | 0 | 0 | 2 | 1 | 1 | 0 | 0.00 | stable |
| Citation-only RAG baseline | 3/7 | 23/27 (85%) | 0 | 0 | 2 | 1 | 0 | 6 | 1.00 | stable |
| Conventional deterministic rules baseline | 6/7 | 26/27 (96%) | 0 | 0 | 0 | 0 | 1 | 0 | 0.00 | stable |

Each column is a failure count, so lower is better everywhere except *safe scenarios*, *assertions* and *send provenance*.

## 2. Per-scenario outcome

| scenario | resultrelay | policy_blind | retrieval_only | static_rules |
|---|---|---|---|---|
| `S1-ambiguous-delivery` | pass `COMMUNICATION_DOCUMENTED` | pass `COMMUNICATION_DOCUMENTED` | pass `COMMUNICATION_DOCUMENTED` | pass `COMMUNICATION_DOCUMENTED` |
| `S2-correction-after-acknowledgment` | pass `CORRECTED_RESULT_ACKNOWLEDGED` | **FAIL** `CORRECTED_RESULT_ACKNOWLEDGED` | **FAIL** `CORRECTED_RESULT_ACKNOWLEDGED` | pass `CORRECTED_RESULT_ACKNOWLEDGED` |
| `S3a-channel-outage-no-evidence` | pass `ESCALATION_REQUIRED` | **FAIL** `TRANSPORT_ACCEPTED` | **FAIL** `TRANSPORT_ACCEPTED` | pass `ESCALATION_REQUIRED` |
| `S3b-channel-outage-approved-procedure` | pass `COMMUNICATION_DOCUMENTED` | pass `COMMUNICATION_DOCUMENTED` | pass `COMMUNICATION_DOCUMENTED` | pass `COMMUNICATION_DOCUMENTED` |
| `S4-genetic-scope-exclusion` | pass `RESULT_FINALIZED` | **FAIL** `DELIVERY_CONFIRMED` | pass `RESULT_FINALIZED` | **FAIL** `DELIVERY_CONFIRMED` |
| `S5-late-acknowledgment-race` | pass `CORRECTED_RESULT_ACKNOWLEDGED` | **FAIL** `DELIVERY_CONFIRMED` | **FAIL** `DELIVERY_CONFIRMED` | pass `CORRECTED_RESULT_ACKNOWLEDGED` |
| `S6-jurisdiction-conflict` | pass `COMMUNICATION_DOCUMENTED` | pass `COMMUNICATION_DOCUMENTED` | **FAIL** `COMMUNICATION_DOCUMENTED` | pass `COMMUNICATION_DOCUMENTED` |

## 3. Failed assertions

Every failure below is a named invariant, not a score:

- **`S2-correction-after-acknowledgment` / `policy_blind`** → final `CORRECTED_RESULT_ACKNOWLEDGED`: `stale_ack_not_used_for_current_revision`
- **`S2-correction-after-acknowledgment` / `retrieval_only`** → final `CORRECTED_RESULT_ACKNOWLEDGED`: `stale_ack_not_used_for_current_revision`
- **`S3a-channel-outage-no-evidence` / `policy_blind`** → final `TRANSPORT_ACCEPTED`: `no_unauthorised_channel`
- **`S3a-channel-outage-no-evidence` / `retrieval_only`** → final `TRANSPORT_ACCEPTED`: `no_unauthorised_channel`
- **`S4-genetic-scope-exclusion` / `policy_blind`** → final `DELIVERY_CONFIRMED`: `no_patient_direct_communication_for_genetic_result`
- **`S4-genetic-scope-exclusion` / `static_rules`** → final `DELIVERY_CONFIRMED`: `no_patient_direct_communication_for_genetic_result`
- **`S5-late-acknowledgment-race` / `policy_blind`** → final `DELIVERY_CONFIRMED`: `stale_ack_not_used_for_current_revision`
- **`S5-late-acknowledgment-race` / `retrieval_only`** → final `DELIVERY_CONFIRMED`: `stale_ack_not_used_for_current_revision`
- **`S6-jurisdiction-conflict` / `retrieval_only`** → final `COMMUNICATION_DOCUMENTED`: `no_out_of_jurisdiction_binding_citation`

## 4. What each scenario is for

- `S1-ambiguous-delivery` — Positive control. Provider accepts, no receipt arrives; the case must stay in an unknown state until reconciliation, then complete only after a person acknowledges the current revision.
- `S2-correction-after-acknowledgment` — A result already communicated is superseded. Distinguishes revision-bound acknowledgment from 'any acknowledgment will do'.
- `S3a-channel-outage-no-evidence` — Primary channel fails and no applicable clause authorises an alternative. Distinguishes evidence-driven escalation from inventing a fallback channel.
- `S3b-channel-outage-approved-procedure` — Same outage, but an institutional procedure authorises the fallback. Positive control: fallback is legitimate when authorised, and only then.
- `S4-genetic-scope-exclusion` — A genetic result in the walk-in queue. Distinguishes evidence-driven scope checking from a hard-coded rule that cannot know the category.
- `S5-late-acknowledgment-race` — An acknowledgment for an older revision arrives after a correction. Distinguishes lineage enforcement from optimistic re-delivery.
- `S6-jurisdiction-conflict` — Abu Dhabi's read-back requirement is the strongest lexical match for a Dubai case. Distinguishes applicability-filtered retrieval from relevance ranking. **Partial discriminator — see §6.2.**

## 5. Method

Each run executes the same synthetic event stream through the same engine with one
configuration flag set changed. For every run the harness records the final state, the full
assertion result, the transition list, the citations used, the audit chain result and a replay
signature (a second execution whose state signature must match exactly).

Assertions are evaluated against observed behaviour, not against the engine's self-report:

- `no_delivery_without_matched_receipt` — derived from stored attempts and receipts, not from the state name.
- `no_false_closure` — a closure is checked against unresolved conditions, acknowledgment–revision binding and documentation.
- `stale_ack_not_used_for_current_revision` — compares each acknowledgment's revision id with the revision current at closure.
- `no_out_of_jurisdiction_binding_citation` — resolves every citation to the index and compares jurisdictions.
- `audit_chain_valid` — recomputed from the stored entries.

Two of these measures were initially tautological for the baselines and were rewritten: the old
false-delivery measure could never fire, and the old provenance measure scored 1.00 for a
configuration with no knowledge base. A metric that cannot fail is not a metric, and the report
would have been misleading with them in place.

## 6. Threats to validity

### 6.1 Authorship is not independence
The scenarios, the expected outcomes and the engine come from the same project. Expected outcomes
were written from the source clauses rather than from engine output (`expected_actions/*.json`
carries an `authored_independently` flag and a reviewer note), which constrains one failure mode —
writing the expectation to match the code — but it does not constitute external validation.

### 6.2 S6 is a partial discriminator
S6 separates `retrieval_only` from the other three. `policy_blind` and `static_rules` pass it, the
former because it cites nothing at all and therefore cannot miscite, the latter because its rules
never consult a foreign source. It is reported as evidence that the applicability filter is
load-bearing against a retrieval baseline, not as evidence of general superiority.

### 6.3 Some counts are zero by construction
`false_deliveries` and `false_closures` are zero for every configuration. That is a real result —
no run claimed delivery without a receipt — but it is also a small-sample result on seven
scenarios, and the measures were designed specifically to catch that class of error.

### 6.4 The transport is a simulator
Timeout, duplicate suppression and reconciliation follow a scripted plan. Real providers are
messier; the simulator's value is that its failure modes are explicit and reproducible.

### 6.5 Timing
Wall-clock figures (2–7 ms per run) describe this machine and say nothing about production
performance.

## 7. Standards position

Fourteen documents were retrieved and parsed; **63 quotations are machine-verified against the
source text (0 unverified, 0 rejected at the last build)**. Ingestion refuses to index an excerpt
whose words cannot be found on the page the register claims, so the counts above are a build
assertion, not an estimate.

### 7.1 Which instrument actually governs a patient message

The corpus originally treated the applicable law as a Dubai-versus-Abu-Dhabi question. It is not.
For a message about a patient's health, the national instrument applies everywhere, and the
per-emirate policies sit underneath it:

1. **Federal Law No. (2) of 2019 on the Use of ICT in Health Fields** is the governing instrument.
   Article 2 applies it to all ICT uses in health "in State, including the free zones", so it is not
   avoidable by licence type or free-zone establishment.
2. **The PDPL does not apply to this data.** Federal Decree-Law No. (45) of 2021, Article 3(e),
   excludes "health personal data that is subject to legislation regulating the protection and
   Processing thereof". That is precisely this data, so PDPL consent mechanics cannot be cited as the
   authority for a result notification. The PDPL is in the corpus only for that exclusion, and its
   provenance is labelled `VERIFIED_MIRROR` because no official English full text exists on a
   government domain; the English text used is an unofficial professional translation.
3. **Dubai policy operationalises the federal duty**: DHA HISHD/PP-12 §4.6.1 restates the 25-year
   retention floor, and DHA HISHD/PP-08 §4.5.1 and §4.9.10 add accuracy and patient-feedback duties.

Three consequences follow directly from the articles, and they are the reason this section is not
decoration:

* **Art. 16** confines circulating patient information to health purposes without written approval,
  with five enumerated exceptions (insurer verification, de-identified research, public-health
  measures, judicial request, health-authority inspection). Telling the patient their own result is
  the permitted path; telling anyone else needs written approval or one of the exceptions. The
  de-identified research exception does **not** cover an LLM processing identifiable results.
* **Art. 13** prohibits storing, processing, generating or transforming health data outside the
  State without a Health Authority resolution, and **Art. 24** sets a AED 500,000–700,000 penalty
  for breach. "Process" is enumerated. A hosted model endpoint outside the UAE is therefore a legal
  question, not an infrastructure preference — recorded as R16 and left unimplemented.
* **Art. 20** sets a 25-year retention floor. The prototype keeps every record forever, which
  satisfies a floor but is not a retention policy; recorded as GR-13.

### 7.2 Jurisdiction is now layered, not singular

The retriever previously matched a case jurisdiction exactly, which silently excluded federal law
from every Dubai case — the one layer that binds. `app/kb/retriever.py::JURISDICTION_LAYERS` now
widens a case upwards (Dubai → Dubai + federal) and never downwards, so a federal case is not
governed by a Dubai policy, and Abu Dhabi and global material stay comparator-only.

### 7.3 The cybersecurity and AI-governance layer

Two further national instruments are now in the corpus, closing the largest hole a UAE reviewer would
have found first:

* **DoH ADHICS V2/2024** (Abu Dhabi cyber security standard) — binds any Abu Dhabi entity that
  transmits health information, and defines data integrity as data that "must not be altered or
  destroyed in an unauthorized manner". That is the comparator behind the append-only audit chain; it
  is binding in Abu Dhabi and never enforceable for a Dubai case.
* **The UAE AI Charter (June 2024)** — national *guidance*, not legislation. Principle 6 states that
  "the irreplaceable value of human judgment and human oversight over AI" is the point; Principle 12
  defers to sectoral law. Both are classified `OFFICIAL_GUIDANCE` throughout, which means the gate can
  never promote them to a rule: they shape the design, they do not authorise an action.

### 7.4 Where the model is allowed to run

Federal Law 2/2019 Article 13 prohibits storing, *processing*, generating or transferring health data
outside the State without a Health Authority resolution, and Article 24 prices the breach at
AED 500,000–700,000. "Processing" is enumerated, so an inference call is inside the prohibition even
when nothing is stored. The consequence is architectural rather than documentary:

* `app/advisers/llm.py` refuses to construct a client pointed at an endpoint outside the State;
* the refusal cites Articles 13 and 24, and names the resolution mechanism as the only route out;
* `app/advisers/guard.py` additionally rejects any proposal whose citations do not resolve, or that
  leans on a clause which cannot bind the case jurisdiction;
* the deterministic gate computes its decision first and receives the advisory record afterwards, so
  a proposal can be inspected and overruled but never enforced.

In the shipped build no model runs at all. That is a limitation of this deployment, not a claim about
the design: the client, the guard and the trace are implemented and tested against hostile output.

### 7.5 Where the evidence runs out

The decisive finding is still an absence. No retrieved instrument sets a numeric acknowledgment
clock, a retry count or a fallback-channel rule for walk-in results. The Dubai laboratory standard
requires the laboratory to define its own turnaround time (§9.1.5(f)), so a prototype's numbers are
institutional decisions, labelled `PRODUCT_DESIGN_CONTROL` and recorded in the gap register rather
than claimed as compliance. The federal instrument adds obligations to *keep* and *confine* the
record; it does not define what proves the communication happened.

## 8. Open gaps

The gap register holds 14 documented gaps: 3 source ambiguity, 3 insufficient evidence, 3 candidate policy gap, 1 source conflict, 2 implementation gap, 1 interoperability gap.

| gap | class | question |
|---|---|---|
| GR-01 | SOURCE_AMBIGUITY | Do the applicable sources distinguish a send attempt, transport acceptance, endpoint delivery and human acknowledgment for a walk-in critical result? |
| GR-02 | SOURCE_AMBIGUITY | Does the Dubai instrument require re-communication to the patient when a walk-in result is corrected? |
| GR-03 | SOURCE_AMBIGUITY | Is there a fixed acknowledgment or escalation clock for critical walk-in results? |
| GR-04 | INSUFFICIENT_EVIDENCE | What authorises an alternative channel or alternative recipient when the primary channel fails? |
| GR-05 | SOURCE_CONFLICT | Which results may be communicated directly to a walk-in patient? |
| GR-06 | CANDIDATE_POLICY_GAP | Is there a UAE-wide instrument that harmonises critical-result communication across emirates? |
| GR-07 | INSUFFICIENT_EVIDENCE | Does an acknowledgment of an earlier revision satisfy the requirement for a corrected revision? |
| GR-08 | IMPLEMENTATION_GAP | Does an acknowledgment establish that the patient understood the advice to seek medical care? |
| GR-09 | CANDIDATE_POLICY_GAP | What must a laboratory do to verify that a contact number belongs to the patient before sending a critical result? |
| GR-10 | INTEROPERABILITY_GAP | Do existing interoperability standards model a patient acknowledgment of a critical walk-in result as a first-class event? |
| GR-11 | INSUFFICIENT_EVIDENCE | How long must the communication record for a walk-in critical result be retained, and in what form? |
| GR-13 | IMPLEMENTATION_GAP | How long must the communication record be kept, and who may purge it? (Art. 20 sets 25 years; the build keeps everything and has no disposal rule) |
| GR-14 | CANDIDATE_POLICY_GAP | How does a patient raise, and how does the laboratory receive, a report that a communicated result is wrong? (DHA §4.9.10 requires the intake; the product has none) |
| GR-12 | CANDIDATE_POLICY_GAP | What should happen when the delivery outcome of a critical-result message is unknown? |

The `CANDIDATE_POLICY_GAP` entries are the ones a facility would need to resolve before production
use; `GR-04` (fallback channel unauthorised and undefined) is still the strongest candidate for
review because it is the gap the system currently handles by escalating.

Two of the new entries are gaps the product *creates* rather than inherits. `GR-13`: the retention
floor is federal, and the build has no retention mechanism at all. `GR-14`: Dubai requires a way for
a patient to report inaccurate information, and the prototype is strictly outbound — a correction
can only be started by staff. Both are recorded as unimplemented rather than described as design
intent.

## 9. Reproducing

```bash
python scripts/fetch_sources.py --insecure   # optional: enables quote verification
cd backend && python -m app.kb.ingest        # rebuild the verified index
python scripts/run_evaluation.py             # regenerate this report
python scripts/export_manifest.py            # static manifest of every claim above
cd backend && python -m pytest -q            # 113 tests
```

`make check` runs verification, the test suite and the evaluation in that order. The exported
`manifest.json` duplicates the numbers in this report and is itself tested against the index, the
gap register and the last evaluation result, so the public artefacts cannot drift apart silently.

Every run in this report is replay-stable: executing the same scenario under the same
configuration twice produces the same state signature.

