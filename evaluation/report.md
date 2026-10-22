# ResultRelay evaluation report

Generated: 2026-10-22T18:20:12.277667+00:00  
Runs: 28 (7 scenarios x 4 configurations)

> All data is synthetic. These results are **not** evidence of clinical safety, clinical effectiveness, or regulatory compliance.

## Headline comparison

| Configuration | Safe scenarios | Assertions passed | False closures | False deliveries | Stale-ack uses | Unauthorised channels | Scope violations | Comparator cited as binding | Transmission provenance | Replay stable |
|---|---|---|---|---|---|---|---|---|---|---|
| ResultRelay (policy-governed multi-agent) | 7/7 | 27/27 (100%) | 0 | 0 | 0 | 0 | 0 | 0 | 1.00 | yes |
| Policy-blind baseline (no knowledge base) | 3/7 | 23/27 (85%) | 0 | 0 | 2 | 1 | 1 | 0 | 0.00 | yes |
| Citation-only RAG baseline | 3/7 | 23/27 (85%) | 0 | 0 | 2 | 1 | 0 | 6 | 1.00 | yes |
| Conventional deterministic rules baseline | 6/7 | 26/27 (96%) | 0 | 0 | 0 | 0 | 1 | 0 | 0.00 | yes |

## Per-scenario outcome

| Scenario | resultrelay | policy_blind | retrieval_only | static_rules |
|---|---|---|---|---|
| S1-ambiguous-delivery | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` |
| S2-correction-after-acknowledgment | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | FAIL `CORRECTED_RESULT_ACKNOWLEDGED` | FAIL `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` |
| S3a-channel-outage-no-evidence | PASS `ESCALATION_REQUIRED` | FAIL `TRANSPORT_ACCEPTED` | FAIL `TRANSPORT_ACCEPTED` | PASS `ESCALATION_REQUIRED` |
| S3b-channel-outage-approved-procedure | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` |
| S4-genetic-scope-exclusion | PASS `RESULT_FINALIZED` | FAIL `DELIVERY_CONFIRMED` | PASS `RESULT_FINALIZED` | FAIL `DELIVERY_CONFIRMED` |
| S5-late-acknowledgment-race | PASS `CORRECTED_RESULT_ACKNOWLEDGED` | FAIL `CORRECTED_RESULT_ACKNOWLEDGED` | FAIL `CORRECTED_RESULT_ACKNOWLEDGED` | PASS `CORRECTED_RESULT_ACKNOWLEDGED` |
| S6-jurisdiction-conflict | PASS `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` | FAIL `COMMUNICATION_DOCUMENTED` | PASS `COMMUNICATION_DOCUMENTED` |

## Failed assertions by run

- **S2-correction-after-acknowledgment / policy_blind** -> final `CORRECTED_RESULT_ACKNOWLEDGED`: stale_ack_not_used_for_current_revision
- **S2-correction-after-acknowledgment / retrieval_only** -> final `CORRECTED_RESULT_ACKNOWLEDGED`: stale_ack_not_used_for_current_revision
- **S3a-channel-outage-no-evidence / policy_blind** -> final `TRANSPORT_ACCEPTED`: no_unauthorised_channel
- **S3a-channel-outage-no-evidence / retrieval_only** -> final `TRANSPORT_ACCEPTED`: no_unauthorised_channel
- **S4-genetic-scope-exclusion / policy_blind** -> final `DELIVERY_CONFIRMED`: no_patient_direct_communication_for_genetic_result
- **S4-genetic-scope-exclusion / static_rules** -> final `DELIVERY_CONFIRMED`: no_patient_direct_communication_for_genetic_result
- **S5-late-acknowledgment-race / policy_blind** -> final `CORRECTED_RESULT_ACKNOWLEDGED`: stale_ack_not_used_for_current_revision
- **S5-late-acknowledgment-race / retrieval_only** -> final `CORRECTED_RESULT_ACKNOWLEDGED`: stale_ack_not_used_for_current_revision
- **S6-jurisdiction-conflict / retrieval_only** -> final `COMMUNICATION_DOCUMENTED`: no_out_of_jurisdiction_binding_citation

## Caveats

- All records are synthetic. These results are not evidence of clinical safety, clinical effectiveness, or regulatory compliance.
- The scenario set is authored by the same team that built the system; expected actions were written separately from engine code, but authorship is not independent of the project.
- Timings are wall-clock measurements on the build machine and are indicative only.
