# ResultRelay evaluation report

Generated: 2026-10-22T19:31:24.772889+00:00  
Runs: 88 (8 scenarios x 11 configurations)

> All data is synthetic. These results are **not** evidence of clinical safety, clinical effectiveness, or regulatory compliance.

## How to read this table

The rows answer two different questions and are separated for that reason.

**One-flag ablations** differ from `ResultRelay` in exactly one runtime input. A difference in a column is therefore attributable to that input, and the table below names which one. This is the only part of the report that supports a causal claim about a single mechanism.

**Compound baselines** change several inputs at once. They answer "what does a system without any of this look like?" and nothing finer: a difference between a compound baseline and the full configuration cannot be attributed to any one of its parts. `static_rules` is the closest honest comparator - a competent hand-written rule set - and it is the row to beat.

### One-flag ablations (primary evidence)

| Configuration | Safe scenarios | Assertions passed | False closures | False deliveries | Stale-ack uses | Unauthorised channels | Scope violations | Comparator cited as binding | Transmission provenance | Replay stable |
|---|---|---|---|---|---|---|---|---|---|---|
| ResultRelay (policy-gated assessors, deterministic) | 8/8 | 32/32 (100%) | 0 | 0 | 0 | 0 | 0 | 0 | 1.00 | yes |
| Ablation: knowledge base off (one flag) | 6/8 | 30/32 (94%) | 0 | 0 | 0 | 0 | 2 | 0 | 0.00 | yes |
| Ablation: jurisdiction filter off (one flag) | 7/8 | 31/32 (97%) | 0 | 0 | 0 | 0 | 0 | 6 | 1.00 | yes |
| Ablation: invariant gate off (one flag) | 7/8 | 31/32 (97%) | 0 | 0 | 0 | 1 | 0 | 0 | 1.00 | yes |
| Ablation: audit assessor off (one flag) | 8/8 | 32/32 (100%) | 0 | 0 | 0 | 0 | 0 | 0 | 1.00 | yes |
| Ablation: full context to every assessor (one flag) | 8/8 | 32/32 (100%) | 0 | 0 | 0 | 0 | 0 | 0 | 1.00 | yes |
| Ablation: acknowledgement scope any revision (one flag) | 6/8 | 30/32 (94%) | 0 | 0 | 2 | 0 | 0 | 0 | 1.00 | yes |
| Ablation: optimistic transport semantics (one flag) | 8/8 | 32/32 (100%) | 0 | 0 | 0 | 0 | 0 | 0 | 1.00 | yes |

| Ablation | Single input changed | Full configuration | Ablation | Isolates |
|---|---|---|---|---|
| Ablation: knowledge base off (one flag) | `use_kb` | `True` | `False` | ResultRelay with the gate's evidence requirement removed; retrieval still runs. |
| Ablation: jurisdiction filter off (one flag) | `applicability_filter` | `True` | `False` | Retrieves across jurisdictions and presents the highest-scoring clause as governing. |
| Ablation: invariant gate off (one flag) | `use_invariants` | `True` | `False` | Proposals are executed as proposed: the deterministic gate is replaced by a naive one. |
| Ablation: audit assessor off (one flag) | `use_audit_agent` | `True` | `False` | The fifth assessor is skipped (the engine already gates it on this flag). |
| Ablation: full context to every assessor (one flag) | `asymmetric_context` | `True` | `False` | Every assessor sees the whole case snapshot, so no assessor has to work from less information than another. |
| Ablation: acknowledgement scope any revision (one flag) | `acknowledgement_scope` | `revision` | `any` | Any acknowledgment closes the case, including one for a superseded revision. |
| Ablation: optimistic transport semantics (one flag) | `transport_semantics` | `strict` | `optimistic` | A provider acceptance is treated as delivery; the unknown state is never entered. |

### Compound baselines (secondary; not causal evidence)

| Configuration | Safe scenarios | Assertions passed | False closures | False deliveries | Stale-ack uses | Unauthorised channels | Scope violations | Comparator cited as binding | Transmission provenance | Replay stable |
|---|---|---|---|---|---|---|---|---|---|---|
| Policy-blind baseline (no knowledge base) | 3/8 | 27/32 (84%) | 0 | 0 | 2 | 1 | 2 | 0 | 0.00 | yes |
| Citation-only RAG baseline | 4/8 | 28/32 (88%) | 0 | 0 | 2 | 1 | 0 | 6 | 1.00 | yes |
| Conventional deterministic rules baseline | 6/8 | 30/32 (94%) | 0 | 0 | 0 | 0 | 2 | 0 | 0.00 | yes |

| Baseline | Inputs that differ from the full configuration |
|---|---|
| Policy-blind baseline (no knowledge base) | 7: `use_kb`, `applicability_filter`, `use_invariants`, `use_audit_agent`, `acknowledgement_scope`, `transport_semantics`, `agents` |
| Citation-only RAG baseline | 6: `applicability_filter`, `use_invariants`, `use_audit_agent`, `acknowledgement_scope`, `transport_semantics`, `agents` |
| Conventional deterministic rules baseline | 4: `use_kb`, `applicability_filter`, `use_audit_agent`, `agents` |

## Per-scenario outcome

| Scenario | resultrelay | policy_blind | retrieval_only | ablate_no_kb | ablate_no_applicability_filter | ablate_no_invariants | ablate_no_audit_agent | ablate_full_context | ablate_ack_any | ablate_optimistic_transport | static_rules |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1-ambiguous-delivery | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` |
| S2-correction-after-acknowledgment | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | FAIL `ESCALATION_REQUIRED` | FAIL `ESCALATION_REQUIRED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `ESCALATION_REQUIRED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | FAIL `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` |
| S3a-channel-outage-no-evidence | PASS `ESCALATION_REQUIRED` | FAIL `DELIVERY_CONFIRMED` | FAIL `DELIVERY_CONFIRMED` | PASS `ESCALATION_REQUIRED` | PASS `ESCALATION_REQUIRED` | FAIL `TRANSPORT_ACCEPTED` | PASS `ESCALATION_REQUIRED` | PASS `ESCALATION_REQUIRED` | PASS `ESCALATION_REQUIRED` | PASS `ESCALATION_REQUIRED` | PASS `ESCALATION_REQUIRED` |
| S3b-channel-outage-approved-procedure | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` |
| S4-genetic-scope-exclusion | PASS `RESULT_FINALIZED` | FAIL `DELIVERY_CONFIRMED` | PASS `RESULT_FINALIZED` | FAIL `DELIVERY_CONFIRMED` | PASS `RESULT_FINALIZED` | PASS `RESULT_FINALIZED` | PASS `RESULT_FINALIZED` | PASS `RESULT_FINALIZED` | PASS `RESULT_FINALIZED` | PASS `RESULT_FINALIZED` | FAIL `DELIVERY_CONFIRMED` |
| S5-late-acknowledgment-race | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | FAIL `CORRECTED_RESULT_ACKNOWLEDGED` | FAIL `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | FAIL `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` |
| S6-jurisdiction-conflict | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | FAIL `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | FAIL `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` |
| S7-genetic-physician-route | PASS `COMMUNICATION_DOCUMENTED` | FAIL `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | FAIL `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | FAIL `COMMUNICATION_DOCUMENTED` |

## Failed assertions by run

- **S2-correction-after-acknowledgment / policy_blind** -> final `ESCALATION_REQUIRED`: stale_ack_not_used_for_current_revision
- **S2-correction-after-acknowledgment / retrieval_only** -> final `ESCALATION_REQUIRED`: stale_ack_not_used_for_current_revision
- **S2-correction-after-acknowledgment / ablate_ack_any** -> final `CORRECTED_RESULT_ACKNOWLEDGED`: stale_ack_not_used_for_current_revision
- **S3a-channel-outage-no-evidence / policy_blind** -> final `DELIVERY_CONFIRMED`: no_unauthorised_channel
- **S3a-channel-outage-no-evidence / retrieval_only** -> final `DELIVERY_CONFIRMED`: no_unauthorised_channel
- **S3a-channel-outage-no-evidence / ablate_no_invariants** -> final `TRANSPORT_ACCEPTED`: no_unauthorised_channel
- **S4-genetic-scope-exclusion / policy_blind** -> final `DELIVERY_CONFIRMED`: no_patient_direct_communication_for_genetic_result
- **S4-genetic-scope-exclusion / ablate_no_kb** -> final `DELIVERY_CONFIRMED`: no_patient_direct_communication_for_genetic_result
- **S4-genetic-scope-exclusion / static_rules** -> final `DELIVERY_CONFIRMED`: no_patient_direct_communication_for_genetic_result
- **S5-late-acknowledgment-race / policy_blind** -> final `CORRECTED_RESULT_ACKNOWLEDGED`: stale_ack_not_used_for_current_revision
- **S5-late-acknowledgment-race / retrieval_only** -> final `CORRECTED_RESULT_ACKNOWLEDGED`: stale_ack_not_used_for_current_revision
- **S5-late-acknowledgment-race / ablate_ack_any** -> final `CORRECTED_RESULT_ACKNOWLEDGED`: stale_ack_not_used_for_current_revision
- **S6-jurisdiction-conflict / retrieval_only** -> final `COMMUNICATION_DOCUMENTED`: no_out_of_jurisdiction_binding_citation
- **S6-jurisdiction-conflict / ablate_no_applicability_filter** -> final `COMMUNICATION_DOCUMENTED`: no_out_of_jurisdiction_binding_citation
- **S7-genetic-physician-route / policy_blind** -> final `COMMUNICATION_DOCUMENTED`: no_patient_direct_communication_for_genetic_result
- **S7-genetic-physician-route / ablate_no_kb** -> final `COMMUNICATION_DOCUMENTED`: no_patient_direct_communication_for_genetic_result
- **S7-genetic-physician-route / static_rules** -> final `COMMUNICATION_DOCUMENTED`: no_patient_direct_communication_for_genetic_result

## Caveats

- All records are synthetic. These results are not evidence of clinical safety, clinical effectiveness, or regulatory compliance.
- The scenario set is authored by the same team that built the system; expected actions were written separately from engine code, but authorship is not independent of the project.
- Timings are wall-clock measurements on the build machine and are indicative only.
