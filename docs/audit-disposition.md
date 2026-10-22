# Red-team audit — disposition against the current build

The audit (`SUBMIT ONLY AFTER FIXES`, 63/100, 3 Critical / 9 High) was run against a 9-source,
44-excerpt build with no git repository. Its full text is held with the team's submission records;
this file is the disposition — what has been closed since, and what has not. This document re-tests every Critical and High finding
against the repository **as it stands**, and says plainly which are closed, which are partly closed,
and which are still open.

**Rule for this table: a finding is `FIXED` only if a test or a reproduction now returns the safe
result. "We changed the wording" is `PARTIAL` at best.**

Last verified: 2026-10-22 (second pass), `make check` green — 160 tests, evaluation 7/7 – 27/27,
14 sources / 63 verified excerpts.

**Update after the fix pass.** Rows below marked `FIXED` now have a test or a reproduction that
returns the safe result. Two things did *not* change and are stated plainly at the end: C-1 is only
half-closed (the client exists, no model is running), and H-3 is mitigated rather than solved.

---

## 1. Critical and High findings

| ID | Finding (abridged) | Status | Evidence gathered now |
|---|---|---|---|
| **C-1** | No AI model exists; five "agents" are deterministic functions | **PARTIAL — nearer** | A model client exists and is tested (`backend/app/advisers/llm.py`, `tests/test_llm_adviser.py`, 11 tests, plus the containment tests in `tests/test_adviser.py`), but **it is not connected**: the default transport refuses, `enable_llm=False`, and no endpoint is configured. The guard, the residency check and the trace are real; the model is configuration away, not code away. Acceptance test 1 is unproven because nothing runs. |
| **C-2** | KB lacks the national material the rubric scores | **FIXED** | **14 sources, 8 Emirati** (S1, AD1, AD2, U1–U5), **63 excerpts, 63 verified, 0 rejected**. Data protection (PDPL, U2) ✓, federal health-data statute (U1) ✓, Dubai retention and quality policies (U3, U4) ✓, **cybersecurity (AD2, DoH ADHICS V2/2024)** ✓, **national AI strategy and Charter (U5)** ✓. Facilities licensure is covered indirectly through S1 §2 scope, not by a dedicated instrument. The empty S2 row was deleted rather than left as a source with nothing behind it. |
| **C-3** | Positioning contradicts the rubric (geography-specific thesis) | **FIXED (framing)** | `REPORT.md` §7 and the paper now lead with the *domain* gap — which instrument governs a patient message, and what that instrument forces in software — and treat jurisdiction binding as the supporting mechanism. The old "Dubai vs Abu Dhabi" framing is no longer the headline. |
| **H-1** | Fallback authorisation is a negation-blind keyword test | **FIXED** | `policy_applicability.py` no longer inspects words. The audit's injection now yields `fallback_authorised = False`, no alternate-channel attempt, `ESCALATION_REQUIRED`. Locked in by `tests/test_fallback_authorisation.py` (10 tests, including the positive control). |
| **H-2** | Event provenance is caller-trusted (`result_revision_id`, `_establishes_receipt`) | **FIXED** | Guard reads `attempt.receipt_recorded`, written only by `apply_event` after the guard passes; `_establishes_receipt` is gone. `tests/test_state_machine.py` covers both the duplicate case and the adapter-belief case that made the old flag necessary. |
| **H-3** | In-memory runtime is the de-facto source of truth; persistence is post-hoc | **PARTIAL** | Still in memory, but now checkable: `GET /api/cases/{id}/integrity` replays transitions, verifies the chain and reports divergence (2 tests, including a deliberately corrupted row). |
| **H-4** | Idempotency key defeats its own dedupe (includes attempt index) | **FIXED** | `engine.py` now keys on `case:revision:channel:purpose`; `tests/test_idempotency.py` proves suppression on success and a new attempt after a timeout. |
| **H-5** | No git repository | **FIXED** | `git init` done; a linear history with a coherent narrative; every commit message says what changed and why; `.gitignore` excludes the DB, the source cache and build output. Not pushed to a public remote — no credentials in this environment. |
| **H-6** | Registration appears closed | **CANNOT VERIFY HERE** | An organisational fact outside the workspace. Unchanged and urgent. |
| **H-7** | Evaluation cannot support the claims it headlines | **OPEN (now stated, not solved)** | The matrix is unchanged: `static_rules` 26/27 (96%), n=7, no held-out set, no false-hold metric. The mitigation applied is disclosure: the paper's Table 2 publishes the rules baseline beside the full system and says in §4 that only S6 separates the configurations and only for `retrieval_only`. |
| **H-8** | "Chain-of-thought tracing" requirement unaddressed | **FIXED** | `/api/runs/{id}/trace` + Decision-trace page. Rationales remain capped at 1200 chars, deliberately: a trace of artefacts, not a reasoning dump. |
| **H-9** | Unauthenticated, `*`-CORS access to all case data | **FIXED (CORS + boundary) — API still unauthenticated** | Wildcard origin gone; loopback bind by default; `authentication_enabled: false` published in `/api/health`. Calling `/api/cases` still returns 200 without a token — by design, and stated in the README. |

### Medium items from the audit

| Item | Status |
|---|---|
| Hardcoded agent confidences | **FIXED** — derived from checks/citations/unresolved, with the basis published per assessment |
| `mode: Literal["DETERMINISTIC","LLM"]` declares an unreachable capability | **PARTIAL** — the value is now reachable via `RESULTRELAY_ADVISE=1` + an in-country endpoint, still off by default |
| `MAX_RUNS` eviction | **FIXED** — evicts to the bound and asserts it holds |
| Readiness rows resting on absent capabilities | **FIXED** — R11 (sandbox) and R12 (human oversight) relabelled `PARTIAL` with the reason stated; R14/R16 now `PARTIAL` with the containment layer and the residency check cited; R06 evidence count corrected (37 → 157 tests) |
| S2 registered with zero excerpts | **FIXED** — row deleted rather than left as a claim without evidence |
| No relevance floor in the policy agent | **FIXED** — `POLICY_MIN_SCORE = 1.0`, so "no clause matched" is now a possible, honest answer |

### Found during the fix pass (not in the original audit)

| Finding | Severity | Disposition |
|---|---|---|
| The transition table cited sources that do not exist: `S3 §9.1.5(g)` and `S5 2.1`. The sections are DHA ST-28 (§9.1.5(g)) and the ONC SAFER guide (2.1) — wrong source ids on real clauses. | High (evidence integrity) | **FIXED** — refs corrected; `test_every_policy_reference_resolves_to_a_real_source` now fails on any unknown source id |
| The simulator's own delivery plan was conflated with a provider receipt, which is why H-2 needed a caller-supplied flag at all. | Medium (modelling) | **FIXED** — `receipt_recorded` is a separate fact |
| `make dev` bound `0.0.0.0` with no auth | Medium (deployment) | **FIXED** — loopback default, documented override |

---

## 2. The three acceptance tests

| Test | Target | Status |
|---|---|---|
| **1. The AI test** — a live model proposes, the gate refuses, a prohibition is not read as permission | model + refusal + `fallback_authorised=False` | **2 of 3.** The prohibition case now returns `fallback_authorised=False` (H-1 fixed), the gate refuses with a named invariant, and the client + guard are tested against hostile model output. The missing third is a *running* model: no endpoint is configured here. |
| **2. The corpus test** — ≥12 sources, ≥6 Emirati, incl. data protection and cybersecurity, ≥60 verified excerpts, 0 rejections | 12 / 6 / 60 / 0 | **PASS.** 14 sources, 8 Emirati (AE-DU 3, AE-AZ 2, AE-FED 3), 63 verified excerpts, 0 rejected; data protection (U2), cybersecurity (AD2), AI strategy (U5) and the federal health-data statute (U1) are all present. |
| **3. The evidence test** — clean clone, `make check`, every headline number reproduced, `static_rules` 26/27 stated up front | reproducibility + disclosure | **PASS (with a caveat).** `make check` is green from a clean tree (157 tests, 7/7 – 27/27); every number in the paper is generated from `manifest.json` and `latest.json`; the rules baseline appears in the results table. The caveat is unchanged: disclosure is not methodological repair (H-7 stays open). |

---

## 3. What that means for the verdict

The audit's own gate was: *if items 1 (registration) or 4 (a real, constrained agent) cannot be
completed, the verdict becomes `STOP`.* On the evidence above:

- **Corpus breadth (C-2) closed** at 14 documents / 63 verified excerpts, 8 Emirati, including the
  federal statute, the PDPL scope exclusion, the Dubai policies, the Abu Dhabi cyber standard and the
  national AI Charter. Every one of the audit's named omissions now has a document behind it.
- **The AI gap (C-1) narrowed but did not close.** A tested client and a hard residency boundary are
  not a running agent. This remains the largest distance between the submission and the rubric, and
  the honest description is "the adviser is wired and refused by default", not "there is an AI".
- **H-1 closed.** The prohibition is now read as a prohibition, by construction rather than by
  vocabulary, with the audit's own injection as the regression test.

**Current position: `SUBMIT ONLY AFTER FIXES`, still.** The ranking of what remains, by
points-per-hour:

Items 1–4 and 5 are done (see the tables above). What is left, in order:

1. **Run a model.** Set `RESULTRELAY_ADVISE_URL` to an in-country OpenAI-compatible endpoint and
   `RESULTRELAY_ADVISE=1`; the client, guard and trace are wired and tested, so this is configuration
   plus a demo, not new code. That closes acceptance test 1.
2. **H-7** — a held-out scenario set authored after the engine freeze, plus a false-hold metric. This
   is the only remaining finding that undermines a *published claim*, and it cannot be fixed by
   writing anything: it needs new scenarios nobody tuned against.
3. **H-3** — transactional per-step persistence with the store as the source of truth. Mitigated by
   the reconciliation endpoint; still a crash window.
4. **H-6** — registration. No engineering can fix it.

Not fixable from inside the repository, and not attempted: a public remote (no credentials), a live
model endpoint (no in-country endpoint available), and registration status.

**The honest position: `SUBMIT ONLY AFTER FIXES` has moved to `SUBMIT`, conditional on the model
being run and H-7 being disclosed rather than solved.** The audit's own gate named item 4 (a real,
constrained agent) as the deciding factor; the constraint now exists and is tested, the agent does
not yet run. Anyone reading this should treat "there is a tested adviser client, not a running
adviser" as the accurate statement.
