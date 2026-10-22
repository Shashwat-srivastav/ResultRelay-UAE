# User stories — who the console is for, and what they are trying to finish

Four roles, taken from the scenario set and the compliance mapping rather than invented. Each story has
an acceptance test that the build can actually be checked against.

---

## 1. Laboratory quality officer (Dubai, walk-in critical results)

> Accountable for whether the lab can *show* that a critical result was communicated. Reads the product
> once a week, under audit pressure.

| # | Story | Acceptance |
|---|---|---|
| QO-1 | I can see, in one screen, whether every live case is compliant right now | Console leads with the number that matters and its denominator ("2 of 2 documented"), not four counters |
| QO-2 | When a case is not compliant I can find out *why* without leaving the screen | Collapsed reason on the row; one click opens the gate decision that caused it |
| QO-3 | I can prove the record was not edited after the fact | Integrity panel shows chain state + `verify_entries` result, and a per-case reconciliation |
| QO-4 | I can see which clause a decision rests on, and whether that clause can bind this case | Every citation shows source id, section, class; any out-of-jurisdiction citation is visibly marked |

**Anti-goal:** QO must never be able to read a green badge as "clinically safe". State chips are about
*communication obligations*, and the UI says so where the chips first appear.

---

## 2. Duty biochemist (the person the system pages)

> Mid-shift, hands busy, interrupts everything. Uses it for 40 seconds at a time.

| # | Story | Acceptance |
|---|---|---|
| DB-1 | When the system needs a human, I see one action, not a dashboard | Escalation card: what happened, what I must do, deadline (if any), one primary button |
| DB-2 | I can act from the keyboard | Tab reaches the action; focus ring visible; Enter activates |
| DB-3 | I am never told a message was "delivered" when only a provider accepted it | Attempt / delivery / acknowledgment are three separate, labelled stages |
| DB-4 | Nothing animates in a way that could hide a change under my cursor | Motion ≤320 ms, no auto-advancing carousels, reduced-motion respected |

---

## 3. Governance / DPO reviewer (Abu Dhabi or federal lens)

> Reviews the tool before it is allowed near a real workflow. Distrusts demos by default.

| # | Story | Acceptance |
|---|---|---|
| GR-1 | I can tell what the system is *not* allowed to do | Advisory boundary is a named panel: mode, classification, "overruled by the gate", and why |
| GR-2 | I can see whether a model ran, and where it was allowed to run | Adviser status per step; residency rule (Art. 13) visible; "no endpoint configured" stated plainly |
| GR-3 | I can test the discrimination myself rather than trust a claim | Side-by-side runs the same scenario twice and shows where the citations diverge |
| GR-4 | I can see the evidence base and its limits | Sources, verified excerpt count, retrieval method, and the gaps register linked from the same rail |

---

## 4. Evaluator / judge (60 seconds, no context)

| # | Story | Acceptance |
|---|---|---|
| EV-1 | In 5 seconds I understand the product is a gate, not a messenger | Lead line names the mechanism; the pipeline is drawn, not described |
| EV-2 | In 30 seconds I see it do something a plain LLM cannot | Side-by-side, default-loaded with the jurisdiction-conflict scenario |
| EV-3 | In 60 seconds I can find the claims and their caveats in the same place | Score, baseline, n=7 and "synthetic, team-authored" sit together, not in a footnote |

---

## 5. Cross-cutting requirements

| Requirement | Why | Where it lands |
|---|---|---|
| Every screen states its own limits | This product's credibility *is* its honesty | `DemoNotice`, integrity rail, advisory panel |
| No dead ends | Curiosity is the conversion event | Rows → trace step; citation → standards entry |
| Semantic colour only | Colour must survive being meaningful | tokens: `--ok/--warn/--bad` used only for status |
| Motion explains causality | The system is a chain; the motion should be too | GSAP timelines, step reveal follows the chain |
| Works offline, no CDN | The preview sandbox has no network | three.js + GSAP bundled by Vite; no remote fonts |
| Keyboard parity | Regulatory users are keyboard users | focus ring, skip link, ARIA on all disclosures |

---

## 6. Explicitly out of scope for this pass

- Authentication / multi-user review queues (no backend identity model).
- Patient-facing views (the product is outbound-only; GR-14 records that as a gap).
- Real-time updates (the runtime is a demo registry; polling was rejected as dishonest theatre).
