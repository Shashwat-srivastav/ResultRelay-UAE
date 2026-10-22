# Design decisions — what shipped, and what each library is actually doing

Companion to `01-critique.md` (findings), `02-user-stories.md` (jobs), `03-moodboard.html` (direction).
This file is the ledger: every visual decision, the finding it answers, and how it was verified.

---

## 1. Stack, and the honest scope of each part

| Piece | Version | What it does here | What it deliberately does **not** do |
|---|---|---|---|
| **GSAP** (`gsap.com`) | 3.x | One reveal timeline per view (`gsap.matchMedia` + `power2.out`), count-up for the lead metric, per-step reveal in the trace | No ScrollTrigger parallax, no SplitText, no scroll-jacking. Motion never gates reading. |
| **three.js** | 0.186 | One scene: the six-stage pipeline with the gate as a membrane. Click a node to open that step. Console + trace (trace only when a step was refused) | No hero, no particles, no orbit controls, no post-processing. It is navigation, not atmosphere. |
| **Magic UI** patterns | — | Blur-fade, shine border, animated beam, dot pattern, number ticker — **ported to the local token system**, not installed | No `magicui.design` dependency, no Tailwind, no CDN: the app must render in a sandbox with no network. |
| Local design system | `src/index.css` §v2 | Tokens, type scale, motion durations, focus ring, reduced-motion parity | — |

`gasp.com` resolves to `gruppruna.com`, a car dealership. The brief grouped it with three.js and Magic
UI, which is the **GSAP** stack; that is what was integrated. If a different reference was intended, the
motion layer can be re-cut independently — the layout and tokens do not depend on it.

## 2. Finding → change

| Finding | Change | Where | Verified by |
|---|---|---|---|
| S1 no lead question | One lead figure (`documented / total`) in a 40px display face, three secondary metrics demoted to a row | `pages/Dashboard.tsx` | screenshot; `useCountUp` respects reduced motion |
| S2 cul-de-sac rows | Rows are `role="link"`, focusable, Enter/Space open `/trace?run=…&step=…`; "why →" affordance on hover/focus | `Dashboard.tsx`, `Trace.tsx` | Playwright: Tab→Enter lands on the trace for that run |
| S3 decorative colour | Green/amber/red only for gate, state and advisory status; configuration names are neutral chips; a legend sits where colour first appears | `Dashboard.tsx`, `index.css` | screenshot |
| S4 contrast | `--ink-3` 4.31:1 → 5.6:1; nav labels 3.64:1 → 5.9:1; smallest label raised to 11.5px with 0.1em tracking | `index.css` tokens | measured with a contrast script during the review |
| S5 focus | `:focus-visible` ring on every interactive element, skip link, `aria-expanded` on disclosures, `role="tablist"` step rail | `index.css`, `App.tsx`, `Trace.tsx` | Playwright keyboard pass |
| S6 no motion language | `--ease`, 120/200/320 ms; `useReveal` runs two `matchMedia` branches and `revert()`s cleanly | `design/motion.ts` | Playwright with `reduced_motion="reduce"` |
| S7 dead half-column | Scope-limits panel moved into the left column; 12-column grid with independent rails | `Dashboard.tsx` | screenshot |
| S8 flat type | 8-step scale, tabular numerals on every figure | `index.css` | — |
| S9 pipeline invisible | `Pipeline3D` — six nodes, gate membrane, refused steps stop short | `design/Pipeline3D.tsx` | screenshot; scene disposes on unmount |
| S10 generic mark | Relay glyph: signal passing through a gate ring | `App.tsx` `Logo` | screenshot |

## 3. Performance

The 3-D scene is `React.lazy`-loaded and lives in its own chunk.

| Chunk | Raw | Gzip |
|---|---|---|
| app | 246 kB | 75 kB |
| three (lazy) | 525 kB | 131 kB |
| gsap | 70 kB | 28 kB |

Initial payload is unchanged from before the redesign (246 vs 239 kB) despite adding three.js, GSAP and
the new components, because three.js only downloads when a scene mounts. `chunkSizeWarningLimit` is set
to 560 kB with a comment rather than silencing the warning globally.

## 4. Accessibility

- Reduced-motion parity tested in a real browser context, not just asserted in CSS.
- Skip link verified: first Tab stop, becomes visible at `top: 12px`.
- Case rows are operable by keyboard (`Enter`/`Space`), not mouse-only.
- Contrast measured; the two failures found in review are fixed, and the measurement is in the critique.
- **Not done:** no screen-reader pass beyond automated announcement checks, no 200% zoom review on the
  trace tables, no user testing with laboratory staff. These are open, not claimed.

## 5. What would change with more time

1. **A real user session** with a quality officer on the console and a duty biochemist on the escalation
   card. Everything above is expert review, which is not the same thing.
2. **Virtualised trace table** — a 20-step run is fine, a 200-step run is not yet.
3. **Saveable compare pairs**, so a reviewer can return to a specific divergence instead of re-running.

## 6. Reproducing the review

```bash
cd frontend && npm install          # three, gsap
make build                          # tsc -b && vite build → backend/app/static/app
make dev                            # http://127.0.0.1:8000
```

Screenshots used in the critique: `before_home.png`, `after_home.png`, `after_trace.png`.
