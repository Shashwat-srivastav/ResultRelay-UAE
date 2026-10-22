# ResultRelay

**A policy-governed workflow for communicating critical laboratory results to walk-in patients —
built to show where the workflow should refuse to proceed.**

> Demonstration prototype. All patients, results and channels are synthetic. This is not a
> clinical service, not a medical device, and not evidence of clinical safety, effectiveness or
> regulatory compliance. It does not diagnose, interpret results, set clinical thresholds or give
> medical advice.

---

## The problem in one paragraph

A laboratory finalises a result that has been flagged critical. Someone has to tell the patient.
The hard part is not sending a message — it is knowing, afterwards, what actually happened:
whether the message was *accepted by a gateway*, *delivered to a device*, or *acknowledged by a
person who now has the content*; whether the result the patient acknowledged is still the current
one; whether the clause being relied on actually applies in this jurisdiction to this type of
test; and whether re-sending would duplicate a message that already arrived. Most prototypes
collapse those questions into "sent". This one does not, and the evaluation is designed to show
the difference.

## What it does

- Runs a 18-state workflow over synthetic laboratory events, with every transition either
  permitted by a guard or explicitly forbidden.
- Uses five **assessors** with declared, asymmetric context — four are fixed rule sets and one retrieves
  from the policy corpus. None of them can change state and none of them can send anything. Calling that
  "multi-agent" would oversell it: there is one deterministic planner and no agent-to-agent negotiation.
- Puts a deterministic **gate** between every proposal and every effect. The gate is not an agent,
  cannot be persuaded, and cites the invariant it applied.
- Grounds policy in **63 quotations across 14 documents, each machine-verified against the official source text at build time** (and, since this review, re-verified at load against a committed pin),
  with an applicability filter that refuses to present another jurisdiction's rule as binding.
- Simulates an asynchronous transport that separates provider acceptance, endpoint delivery and
  human acknowledgment, and treats a timeout as *unknown* rather than *failed*.
- Writes a SHA-256 hash-chained audit log that is **re-verified when read**.
- Ships a React console that keeps the clinical, transport, human and policy layers visibly apart.

## Quick start

```bash
# backend + frontend dependencies
make setup

# fetch the official sources and rebuild the verified index (optional but recommended)
make kb

# build the UI and serve API + UI on :8000
make build
cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open <http://localhost:8000>. API documentation is at `/api/docs`.

```bash
make test      # 113 backend tests
make eval      # 8 scenarios x 11 configurations -> evaluation/report.md
make verify    # re-check every quotation against the source PDFs
make manifest  # export frontend/public/data/manifest.json (served at /data/manifest.json)
```

## What to look at first

| if you have | look at | why |
|---|---|---|
| 2 minutes | the **Console** page, then **Simulator** → run `S1` under `resultrelay`, press *Step* | watch an accepted message fail to become a delivered one |
| 5 minutes | **Simulator** → `S3a` under `resultrelay`, then again under `policy_blind` | the full system escalates; the baseline invents a channel |
| 10 minutes | **Evaluation** → *Run the matrix* | which single input changes which outcome, and where the rule baseline still ties |
| sceptical | **Standards & gaps** → *Retrieval* with the scope filter off | the Abu Dhabi clause outranks the Dubai one, and the UI shows it |
| audit-minded | **Audit trail** → *Export bundle* | the chain, the citations, and every decision that produced the state |

## The configurations

The same engine runs eleven ways, because a number means nothing without a comparison. Seven of them are
**one-flag ablations** — each differs from the full system in exactly one input, so a difference in an
outcome is attributable to that input. Three are **compound baselines**, kept because they answer a
different question ("what does a system without any of this look like?") and labelled as such.

| configuration | knowledge base | applicability filter | invariants | acknowledgment | transport |
|---|---|---|---|---|---|
| `resultrelay` | yes | yes | yes | bound to the current revision | acceptance ≠ delivery |
| `ablate_no_kb` | **no** | yes | yes | bound | strict |
| `ablate_no_applicability_filter` | yes | **no** | yes | bound | strict |
| `ablate_no_invariants` | yes | yes | **no** | bound | strict |
| `ablate_no_audit_agent` | yes | yes | yes (4 assessors) | bound | strict |
| `ablate_full_context` | yes | yes | yes | bound | strict (every assessor sees the whole case) |
| `ablate_ack_any` | yes | yes | yes | **any ack closes the case** | strict |
| `ablate_optimistic_transport` | yes | yes | yes | bound | **acceptance = delivery** |
| `policy_blind` (compound) | no | — | no | any ack | optimistic |
| `retrieval_only` (compound) | yes | no | no | any ack | optimistic |
| `static_rules` (compound) | no | — | yes | bound | strict |

`static_rules` is not a strawman: it is a competent hand-written rules engine, and it scores
30/32 (`evaluation/results/latest.json`). It fails exactly where a static rule cannot know something — that a genetic result may not
be communicated to the patient directly, and that a clause belongs to another jurisdiction. Three of
the seven ablations change no outcome on this scenario set (`ablate_no_audit_agent`,
`ablate_full_context`, `ablate_optimistic_transport`); all three null results are reported rather than dropped,
and the last one exposed a flag that had no behaviour at all until it was implemented.

## How the evidence works

```
official document ──fetch──▶ page-marked text ──verify──▶ excerpt ──ingest──▶ index
                    (build time)                (quote must appear
                                                 on the declared page)
```

- Sources are downloaded from the issuing bodies at build time into
  `~/.cache/resultrelay/sources/` and **are not redistributed**. Only the minimum necessary
  quotations are committed, in `knowledge_base/excerpts/`.
- Each quote is normalised (case, curly punctuation, all whitespace removed) and must appear as a
  contiguous substring of the declared page. Wrong page = rejected. Misquote = rejected.
- A rejected excerpt never reaches the index, so no agent can cite it.
- Every excerpt carries a claim class. Only `BINDING_REQUIREMENT` can block an action, and for a
  Dubai case only Dubai sources carry that class.

Current build: **63 excerpts across 14 documents, 63 verified, 0 unverified, 0 rejected.**

The same figures are exported to `frontend/public/data/manifest.json` and served at
`/data/manifest.json`, so the claims can be checked with `curl` and `jq` without running the
application — and a test asserts the manifest cannot drift from the index, the gap register or the
last evaluation.

## Repository map

```
backend/app/
  core/config.py            runtime settings, safe defaults, no credentials
  api/routes.py             REST surface (also serves the built UI and /data/manifest.json)
  models/schemas.py         typed agent messages, gate decisions, evidence chunks
  models/db.py              12-table SQLite store
  kb/ingest.py              quote verification + index build
  kb/retriever.py           BM25 + the applicability filter
  agents/                   five assessors (four rule sets, one retriever), declared context scopes
  orchestration/gate.py     the deterministic gate (the only path to an effect)
  orchestration/engine.py   event loop, configurations, release policy
  state_machine/            18 states, 17 events, guards, forbidden pairs, conflations
  transport/simulator.py    asynchronous network without a network
  audit/log.py              hash-chained, append-only
  api/routes.py             REST surface
  evaluation/               metrics that can fail, and the runner that proves it
  static/app/               built frontend (served by the API process)
evaluation/
  scenarios/                7 synthetic event streams
  expected_actions/         independently authored acceptable outcomes
  report.md, results/       generated artefacts
knowledge_base/
  source_register.csv      14 sources, with licence and verification status
  excerpts/*.yaml           minimal necessary quotations
  gap_register.csv          12 documented gaps
  mappings/                 ITU-T Y.3172 and AI-readiness self-assessment
frontend/src/pages/         CaseTimeline, Simulator, StandardsMapping, Evaluation, Audit
docs/architecture.md        the design, and the distinctions it is built around
REPORT.md                   results, method and limitations
paper/ResultRelay_ITU_paper.docx   the five-page submission paper (built by paper/build_paper.py)
docs/audit-disposition.md   red-team findings re-tested against the current build
```

## Interface

The console is designed as an instrument panel for a regulator, not a startup dashboard: one lead
question per screen, colour reserved for status, motion that shows a chain of custody.

- **Review:** [`docs/design/01-critique.md`](docs/design/01-critique.md) — five review seats, ten
  findings with measurements (including two contrast failures), and what was deliberately not done.
- **Jobs:** [`docs/design/02-user-stories.md`](docs/design/02-user-stories.md) — quality officer, duty
  biochemist, governance reviewer, evaluator; each story has an acceptance check.
- **Direction:** [`docs/design/03-moodboard.html`](docs/design/03-moodboard.html) — palette with
  measured contrast, type scale, motion curves, reference board.
- **Decisions:** [`docs/design/04-decisions.md`](docs/design/04-decisions.md) — what each library does
  and, more usefully, what it is forbidden to do.

Stack: **GSAP** for the reveal/count-up language, **three.js** for the one scene that carries meaning
(the pipeline, with the gate as a membrane and refused steps stopping at it), and **Magic UI patterns**
(blur-fade, shine border, animated beam) re-implemented against local tokens rather than installed —
the UI has to render in a sandbox with no network, so nothing is fetched from a CDN.

Initial JS is ~246 kB gzipped 75; three.js is a separate lazy chunk (131 kB gzip) that only downloads
when a scene mounts.

Type and colour are self-hosted and measured, not asserted: **Inter** and **JetBrains Mono** ship in
`frontend/public/fonts/` (SIL OFL 1.1, licences alongside) and are served from `/fonts`, and
`python3 scripts/check_contrast.py` verifies 35 foreground/background pairs against WCAG AA — including
the 3:1 floor for control boundaries and focus rings. It runs as part of `make check`. The audit that
produced it, including the three failures it found after the first pass, is
[`docs/design/05-typography-and-colour.md`](docs/design/05-typography-and-colour.md).

## Deployment boundary (read before hosting this)

This build has **no authentication**. Every endpoint returns case data to anyone who can reach it.

- `make dev` binds `127.0.0.1` by default. Widening it is an explicit act: `RESULTRELAY_HOST=0.0.0.0`.
- Cross-origin access is closed by default. If a separate front-end host is used, name it:
  `RESULTRELAY_CORS_ORIGINS=https://host`.
- `/api/health` states `authentication_enabled: false` so the boundary is declared, not assumed.
- **Do not host this with real patient data.** It is a single-tenant demonstration over synthetic cases.

## The advisory boundary

A model may propose; it may never decide. `backend/app/advisers/` holds the containment wrapper:
the boundary is closed by default, an out-of-country endpoint is refused under Federal Law 2/2019
Art. 13 unless a named Health Authority resolution is recorded, a proposal citing material outside
the applicable jurisdiction is rejected, and the deterministic gate computes its decision before it
sees the proposal at all. `backend/tests/test_adviser.py` asserts the decision is unchanged when an
accepted proposal is attached.

A model client *does* ship (`backend/app/advisers/llm.py`) — an OpenAI-compatible adapter that is
**not connected to anything by default**: its transport refuses, and the only endpoints it will
accept are loopback or `.ae`. Enable it against an in-country server:

```bash
RESULTRELAY_ADVISE=1 \
RESULTRELAY_ADVISE_URL=http://localhost:11434/v1 \
RESULTRELAY_ADVISE_MODEL=qwen2.5 \
make dev
```

An offshore endpoint such as `https://api.openai.com/v1` is refused at construction time under
Federal Law 2/2019 Art. 13 (processing health data outside the State), with Art. 24's
AED 500,000–700,000 penalty cited in the refusal — unless a named Health Authority resolution is
recorded in `RESULTRELAY_RESIDENCY_RESOLUTION`. In the shipped configuration no model runs, and the
Decision-trace page says so per step rather than implying otherwise.

### Why this repo publishes decision traces, not chain-of-thought

The hackathon criteria ask for reasoning that a judge can inspect, and this repository answers that
with a decision trace rather than a transcript of model reasoning — a position, not an omission.
Raw chain-of-thought is unverifiable (there is no artefact to check it against), unstable across
runs, and in this build there is no model running at all, so a published transcript would be
fabricated. What is published instead is the thing the criteria are actually after: for every step,
the event, the evidence retrieved with its claim class and printed page, each agent's proposal with
its basis, the gate's conditions and the invariant that fired, the transition and the resulting
state — all reproducible by re-running the same scenario. A judge who wants to see *why* the system
refused can read the refusal in `REPORT.md` §4, on the Decision-trace page, or in the failing
assertion itself.

## Honest limitations

- **Synthetic everything.** No real patient data, no EHR, no SMS gateway, no model provider.
- **Scenario authorship.** The eight scenarios were written by the same team that built the
  engine. Expected outcomes were authored separately and marked as such, but that is not
  independent validation. See `REPORT.md` §6.
- **One partial discriminator.** Scenario S6 separates only `retrieval_only`. It is reported as a
  partial result rather than dressed up as a general one.
- **No clinical claim.** Nothing here shows a patient outcome improved.
- **Gaps are published.** Fourteen open questions — including "no retrieved source sets an
  acknowledgment clock", the federal 25-year retention floor this build does not implement, and the
  absence of any way for a patient to report an inaccurate result — are in
  `knowledge_base/gap_register.csv` rather than in a comments file.

## Licence and third-party text

Source documents belong to their issuing bodies and are not included. Quotations are minimal and
attributed with section and page. See `knowledge_base/source_register.csv` for per-source licence
notes and `docs/architecture.md` §4 for the classification scheme.
