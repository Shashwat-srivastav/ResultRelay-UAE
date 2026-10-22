# Red-team audit — disposition against the current build

The audit (`SUBMIT ONLY AFTER FIXES`, 63/100, 3 Critical / 9 High) was run against a 9-source,
44-excerpt build with no git repository. Its full text is held with the team's submission records;
this file is the disposition — what has been closed since, and what has not. This document re-tests every Critical and High finding
against the repository **as it stands**, and says plainly which are closed, which are partly closed,
and which are still open.

**Rule for this table: a finding is `FIXED` only if a test or a reproduction now returns the safe
result. "We changed the wording" is `PARTIAL` at best.**

Last verified: 2026-10-22, `make check` green (129 tests, evaluation 7/7 – 27/27).

---

## 1. Critical and High findings

| ID | Finding (abridged) | Status | Evidence gathered now |
|---|---|---|---|
| **C-1** | No AI model exists; five "agents" are deterministic functions | **PARTIAL** | The containment layer now exists and is tested (`backend/app/advisers/`, 15 tests), but **there is still no model**: `core/config.py:49` `enable_llm=False`, no model SDK in `pyproject.toml`. What was added is the *ability to safely add one*, not the AI. Acceptance test 1 still fails. |
| **C-2** | KB lacks the national material the rubric scores | **PARTIAL** | 13 sources, **7 Emirati** (S1, S2, AD1, U1, U2, U3, U4), 56 excerpts, 0 rejected. Data protection now present (PDPL, U2); health-data law present (U1); Dubai retention/quality policies present (U3, U4). **Still missing:** cybersecurity standard (DoH ADHICS — `doh.gov.ae` fails TLS from this environment), national AI strategy (`ai.gov.ae` returns 403), facility licensure mandate. Excerpt count is 56 against a ≥60 target. |
| **C-3** | Positioning contradicts the rubric (geography-specific thesis) | **FIXED (framing)** | `REPORT.md` §7 and the paper now lead with the *domain* gap — which instrument governs a patient message, and what that instrument forces in software — and treat jurisdiction binding as the supporting mechanism. The old "Dubai vs Abu Dhabi" framing is no longer the headline. |
| **H-1** | Fallback authorisation is a negation-blind keyword test | **OPEN — re-reproduced today** | `policy_applicability.py:130-139` unchanged. Re-ran the injection against the **new 56-chunk corpus**: a chunk reading "under no circumstances shall an alternative channel … be used" still yields `fallback_authorised = True`, channels used `['SMS-PATIENT', 'PORTAL-PATIENT']`, final state `TRANSPORT_ACCEPTED`. The larger corpus did not fix it, because the defect is the test, not the data. |
| **H-2** | Event provenance is caller-trusted (`result_revision_id`, `_establishes_receipt`) | **OPEN** | `engine.py` `apply_event` unchanged; receipts are not verified against stored attempts. Not remotely reachable (only the simulator calls it), but the internal trust boundary is as described. |
| **H-3** | In-memory runtime is the de-facto source of truth; persistence is post-hoc | **OPEN** | `api/runs.py` still holds `_RUNS`; `_persist` still runs after each step. No reconciliation between store and audit chain. |
| **H-4** | Idempotency key defeats its own dedupe (includes attempt index) | **OPEN** | `engine.py:422` still `f"{case_id}:{revision}:{channel}:{attempt_index}"`. |
| **H-5** | No git repository | **FIXED** | `git init` done; three commits with a coherent narrative; 122 tracked files; `.gitignore` excludes the DB, the source cache and build output. Not pushed to a public remote — no credentials in this environment. |
| **H-6** | Registration appears closed | **CANNOT VERIFY HERE** | An organisational fact outside the workspace. Unchanged and urgent. |
| **H-7** | Evaluation cannot support the claims it headlines | **OPEN (now stated, not solved)** | The matrix is unchanged: `static_rules` 26/27 (96%), n=7, no held-out set, no false-hold metric. The mitigation applied is disclosure: the paper's Table 2 publishes the rules baseline beside the full system and says in §4 that only S6 separates the configurations and only for `retrieval_only`. |
| **H-8** | "Chain-of-thought tracing" requirement unaddressed | **OPEN** | No decision-trace surface. Rationales are still capped at 1200 chars (`schemas.py`). |
| **H-9** | Unauthenticated, `*`-CORS access to all case data | **OPEN — re-verified today** | `curl /api/cases` → `200` with no auth; `Access-Control-Allow-Origin: *` present. |

### Medium items from the audit

| Item | Status |
|---|---|
| Hardcoded agent confidences (0.75 / 0.8 / 0.85 / 0.9) | **OPEN** — unchanged |
| `mode: Literal["DETERMINISTIC","LLM"]` declares an unreachable capability | **OPEN** — `schemas.py:78` |
| `MAX_RUNS` eviction frees 8 at the threshold then grows past 40 | **OPEN** — `api/runs.py:16-20` |
| Readiness rows resting on absent capabilities | **FIXED** — R11 (sandbox) and R12 (human oversight) relabelled `PARTIAL` with the reason stated; R14/R16 already `PARTIAL`; R06 evidence count corrected (37 → 129 tests) |
| S2 registered with zero excerpts | **OPEN** — still a register entry without retrievable content |
| No relevance floor in the policy agent (`top_k=3`, `min_score=0`) | **OPEN** |

---

## 2. The three acceptance tests

| Test | Target | Status |
|---|---|---|
| **1. The AI test** — a live model proposes, the gate refuses, a prohibition is not read as permission | model + refusal + `fallback_authorised=False` | **FAIL.** Two of three parts exist: the gate refuses, and the advisory guard rejects foreign or unresolvable citations. There is still no model, and the prohibition case is still misread (H-1). |
| **2. The corpus test** — ≥12 sources, ≥6 Emirati, incl. data protection and cybersecurity, ≥60 verified excerpts, 0 rejections | 12 / 6 / 60 / 0 | **PARTIAL.** 13 sources ✓, 7 Emirati ✓, 56 verified ✓, 0 rejected ✓, data protection ✓. **Cybersecurity ✗** (host unreachable from here), **AI strategy ✗**, excerpt count 56 < 60. |
| **3. The evidence test** — clean clone, `make check`, every headline number reproduced, `static_rules` 26/27 stated up front | reproducibility + disclosure | **PASS (with a caveat).** `make check` is green from a clean tree; every number in the paper is generated from `manifest.json` and `latest.json` rather than typed; the rules baseline appears in the paper's own results table. The caveat is H-7: disclosure is not methodological repair. |

---

## 3. What that means for the verdict

The audit's own gate was: *if items 1 (registration) or 4 (a real, constrained agent) cannot be
completed, the verdict becomes `STOP`.* On the evidence above:

- **Corpus breadth (C-2)** moved from "8 documents, 2 Emirati, no data protection" to "13 documents,
  7 Emirati, with the governing federal statute and the PDPL scope exclusion". The flagship legal
  finding is now stronger than the one the audit scored.
- **The AI gap (C-1)** did not close. A containment wrapper is not an agent. This is the largest
  remaining distance between the submission and the rubric.
- **H-1** is unchanged and is now the single most damaging open defect, because it is the one the
  clinical reviewer predicted would be dismissed in the room and matter in production.

**Current position: `SUBMIT ONLY AFTER FIXES`, still.** The ranking of what remains, by
points-per-hour:

1. **H-1** — add a structured `authorises_fallback` field to excerpts and delete the keyword test.
   Small, self-contained, and it converts the weakest control into a defensible one.
2. **H-9** — bind to loopback by default and declare the no-auth boundary in the README. An hour.
3. **H-4** — key idempotency on `(case, revision, channel, purpose)`; let the state machine prevent
   duplicates. Small, and removes a claim the code does not honour.
4. **H-8** — publish ordered decision traces (proposal → gate → transition → evidence). Directly
   scores on an explicit criterion.
5. **C-2 remainder** — cybersecurity and AI-strategy documents, once a route to those hosts exists.
6. **C-1** — a real model behind the existing guard, with the demo the audit asked for: the agent
   proposes, the gate refuses, the clause and page are shown.

Registration (H-6) still outranks all of it if it is unresolved.
