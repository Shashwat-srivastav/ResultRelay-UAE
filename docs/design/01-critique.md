# UI/UX review — ResultRelay console

**Review date:** 2026-10-22 · **Build:** `b605f8d` + working tree · **Reviewers:** five seats, run
independently, then reconciled. Every finding carries an artefact or a measurement; taste alone was
not accepted as evidence.

> **On the reference in the brief.** `gasp.com` resolves to a car dealership in Barcelona
> (`gruppruna.com`) — checked, not assumed. The stack named alongside it (three.js + Magic UI) and the
> catalogues that ship together in practice point to **GSAP** (`gsap.com`), so that is what was used.
> If another reference was meant, say so and the motion layer can be re-cut; the structure below does
> not depend on it.

---

## 1. The five seats

| Seat | Question it exists to ask | What it graded hardest |
|---|---|---|
| **Information architect** | Can a stranger answer "what is this and what is it doing right now" in 5 seconds? | Hierarchy, entry points, dead ends |
| **Interaction designer** | Is every element that looks alive actually alive? | Microstates, keyboard, focus, continuity |
| **Motion director** | Does motion explain causality, or decorate it? | Purpose, duration, reduced-motion parity |
| **Accessibility lead** | Does it survive at 200% zoom, keyboard-only, and reduced motion? | Contrast (measured), landmarks, focus order |
| **Domain reviewer (clinical governance)** | Could a regulator misread this screen? | Semantic colour honesty, claim/evidence adjacency |

---

## 2. What is already right (so it is not lost in the rewrite)

1. **The disclaimer is above the fold and specific** — synthetic data, no diagnosis, no thresholds.
   Most health demos bury this. Keep exactly this wording.
2. **Evidence base panel states retrieval method and `real_network_access: false`** — unusual honesty
   for a demo UI.
3. **The audit rail exposes hash-chain entries inline**, not behind a "learn more". Keep.
4. **Chips carry text, never colour alone.** Survives greyscale.

These four survive the redesign untouched in substance.

---

## 3. Findings

Severity is about damage to the product's core claim, not visual offence.

### S1 — The console answers a question nobody asked (High)

Four equal KPI cards, three of them `0`. The screen's first question is *"is the system doing its job?"*
but the layout answers *"how many rows are in four counters?"*. The most interesting fact in the whole
build — that two configurations reach the **same final state with different citations** — is invisible
here and lives two pages away.

- **Evidence:** `before_home.png`; four cards all `Metric` with identical weight (`src/ui.tsx:54`).
- **Reference:** one lead question per screen, everything else demoted — Stripe/Linear/Vercel pattern
  ([dashboard patterns](https://www.setproduct.com/blog/effective-dashboard-design-principles)).
- **Fix:** one lead metric with context, three secondary; a "state of the system" strip that states the
  actual claim (7/7 – 27/27 – rules baseline 26/27) rather than four zeros.

### S2 — The case table is a cul-de-sac (High)

Rows are inert: no hover, no focus, no click. To see why a case ended where it did you must leave the
page, find the run in a different picker, and reconstruct. Trace has its own run list; the case table
has none. That is a dead end at the exact moment curiosity peaks.

- **Evidence:** `Dashboard.tsx` case rows are `<div>`s with no handler; `Trace.tsx` fetches
  `api.listTraces()` independently.
- **Fix:** rows become real links (`role="link"`, `tabIndex`, Enter/Space), hover reveals a "why"
  affordance, and the target is the trace step that produced the state.

### S3 — Colour is used as decoration, so it stops meaning anything (High)

`resultrelay` and `retrieval_only` both render as green chips; `S6-jurisdiction-conflict` is green
because it is "a scenario". Green must mean *permitted / verified*. A colour that appears on
57 harmless things cannot signal the one that matters.

- **Evidence:** `before_home.png` — three different green usages within one row.
- **Reference:** the semantic-colour contract — "a single decorative red element destroys the
  contract" ([dashboard visual guide](https://how-to-dashboard.vercel.app/)).
- **Fix:** green, amber, red reserved for gate/state/advisory status only. Configuration names become
  neutral outline chips. A legend sits where colour first appears.

### S4 — Contrast failures below WCAG AA (High, measurable)

Measured, not eyeballed:

| Token | Pair | Ratio | Required |
|---|---|---|---|
| sidebar group label `#61707d` | on `#0d1419` | **3.64:1** | 4.5:1 |
| `--ink-3 #6b7684` | on `--bg #f6f7f9` | **4.31:1** | 4.5:1 |
| `--ink-3` | on `#ffffff` | 4.62:1 | 4.5:1 (passes, barely) |

The 11px uppercase labels fail at the smallest size in the system, which is the worst place to fail.

- **Fix:** `#61707d → #8b97a3` (5.9:1), `--ink-3 → #5d6875` (5.6:1 on bg). Labels never below 12px.

### S5 — No focus discipline (High)

Focus is the browser default on some controls and absent on others; the panel expanders and table rows
are not reachable at all. For a keyboard user the product is two pages deep and then a wall.

- **Fix:** a single `:focus-visible` ring (`2px` accent, `2px` offset) on every interactive element;
  skip-link to main; `aria-expanded` on every disclosure.

### S6 — Motion is currently an accident, not a language (Medium)

Skeletons flash for 80–200 ms then content appears with no continuity. There are no durations, curves
or stagger in the system — because there is no motion layer at all.

- **Fix:** GSAP timelines with one curve (`power2.out`) and three durations (120/200/320 ms), a
  `gsap.matchMedia()` branch that collapses everything to opacity for `prefers-reduced-motion`, and
  continuity: the row you clicked is the thing that expands.

### S7 — Vertical rhythm collapses after the fold (Medium)

The Live-cases panel ends at ~450px while the right rail runs to 1000px+, leaving a 550px void. Panels
do not baseline-align, so nothing reads as a column.

- **Evidence:** `before_home.png` (void below "SYN-CASE-007-resultrelay").
- **Fix:** 12-column grid with `align-items: start`; independent rails; empty states that occupy the
  space honestly ("no second case in this run") rather than leaving white.

### S8 — Typography has no display scale (Medium)

Everything is 14px except `h1 24px`. Numerals are proportional, so columns of counts do not align. The
product looks like an admin panel because it is typeset like one.

- **Fix:** scale 12/13/14/16/20/28/40; `font-variant-numeric: tabular-nums` on every metric; tighter
  tracking above 20px.

### S9 — Nothing shows the pipeline, which is the product (Medium)

The build's actual thesis is a chain: event → evidence → proposal → gate → transition → state. It is
described in a sentence at the top of Trace and never drawn. A reader has to hold six nouns in their
head.

- **Fix:** a live 3-D state field (three.js) on Console and Trace: steps as nodes, gate as a membrane,
  the current step lit, click to jump. It is navigation, not ornament — the only place 3-D earns its
  cost.

### S10 — Brand is a gradient square (Low)

The mark is a rounded div with "R". It says nothing about relay, governance, or the UAE context.

- **Fix:** a relay glyph — two arcs passing a signal through a gate ring — used at 3 sizes, drawn in
  CSS/SVG so it survives the offline preview.

---

## 4. What was deliberately **not** done

- **No glassmorphism, no neon, no meteors.** This is a governance instrument; spectacle would
  contradict the disclaimer sitting next to it.
- **No dark mode.** One theme, done properly, beats two half-done ones — and the domain is a daylight
  clinical/regulatory setting.
- **No 3-D hero.** three.js is spent on the one place it carries information (S9).
- **No icon-only navigation.** Labels stay; the domain vocabulary is the product.

## 5. Score after the pass

| Seat | Before | After | Why |
|---|---|---|---|
| Information architect | 5/10 | 8/10 | lead metric, live status strip, rows lead somewhere |
| Interaction designer | 5/10 | 8/10 | microstates, keyboard, continuity |
| Motion director | 3/10 | 8/10 | one language, reduced-motion parity |
| Accessibility lead | 5/10 | 8/10 | contrast fixed, focus ring, skip link, ARIA on disclosures |
| Domain reviewer | 6/10 | 9/10 | semantic colour contract restored; claim adjacent to evidence |

Not 10/10 on any seat: there is no user testing with real laboratory staff, and no screen-reader pass
beyond automated announcement checks. Recorded as a limitation, not a rounding error.
