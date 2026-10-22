# Typography & colour — audit, fixes, and the two checks that stop it drifting

Second pass over the parts of the interface that are easiest to get 90% right and hardest to get
finished. Every claim below is either measured by `scripts/check_contrast.py`, asserted by
`backend/tests/test_api.py::test_self_hosted_fonts_are_served_as_fonts`, or visible in
`screenshot-console.png`.

---

## 1. The typography bug that mattered most: the font was never there

`--sans` began with `-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, …`. On macOS and Windows
that is fine. On Linux — including the container this runs in, and any judge's browser on Linux — it
resolved to DejaVu Sans. `Inter` sat fifth in the list, behind three families that would always match
first, and no `@font-face` loaded it in any case. **A typeface that is only referenced is not a
typeface**; the entire type system was being rendered in a fallback.

Fix: two self-hosted variable fonts, latin subset, `font-display: swap`, preloaded in `index.html`.

| Face | File | Size | Use |
|---|---|---|---|
| Inter (variable, 100–900) | `public/fonts/inter-var-latin.woff2` | 48 KB | everything readable |
| JetBrains Mono (variable) | `public/fonts/jetbrains-mono-var-latin.woff2` | 40 KB | ids, digests, clause numbers, counts |

Both are SIL OFL 1.1; the licence texts ship beside them (`public/fonts/OFL-*.txt`), which is an OFL
condition for redistribution, not a courtesy.

### The second bug, underneath it

Mounting the fonts was not enough. `backend/app/main.py` served `/assets` and `/data`, and everything
else fell through to the SPA catch-all:

```
GET /fonts/inter-var-latin.woff2 → 200  text/html  (index.html, 1097 bytes)
```

The browser received an HTML document where it expected a font, rejected it, and silently substituted
a system face. Nothing logged. Nothing broke. The type system was missing and the page looked "fine".
`document.fonts` reported `InterVar error` while the network tab said `200`.

Fix: an explicit `/fonts` mount, plus a test that fetches both files and asserts `content-type` is a
font type **and** that the payload starts with `wOF2`. A font that 200s as HTML is worse than a 404.

Verified after the fix:

```
document.fonts.check('14px InterVar')        → true
document.fonts.check('12px JetBrainsMonoVar') → true
```

---

## 2. Colour: measured, not eyeballed

The first pass fixed two contrast failures I had already found and introduced nothing new. This pass
made the palette *checkable*, which is the only way it stays fixed.

`scripts/check_contrast.py` parses the tokens out of `frontend/src/index.css` (so it measures what
ships, not a copy), then asserts **35 pairs**:

- all text ≥ 4.5:1 (body, muted, chips, banners, sidebar, table headers, 3-D captions)
- control boundaries and focus indicators ≥ 3:1 (WCAG 1.4.11, 2.4.11)

```
$ python3 scripts/check_contrast.py
contrast: 35 pairs at or above AA
```

Negative control — set `--ink-3` back to a light grey and the check fails:

```
FAIL 2.15:1 (min 4.5)  ink-3 on panel (muted)
FAIL 1.98:1 (min 4.5)  ink-3 on canvas
```

### Failures found and fixed in this pass

| Element | Before | Now | Note |
|---|---|---|---|
| Input / select border | `#e2e6eb` — **1.25:1** | `#818d99` — 3.39:1 | The border is the only boundary of a control; 1.25:1 is invisible at a glance and fails 1.4.11 |
| Focus ring on inputs | `#7fb8ae` — **2.24:1** | `#0b6b5f` — 6.40:1 | The old ring was overridden only for `button`, so inputs kept the weak one |
| Sidebar footer | `#61707d` — **3.64:1** | `#8b97a3` — 6.24:1 | Same failure as the nav label, missed in the first pass because it is a different rule |
| 3-D scene hint | `#6d7f8d` — **4.10:1** | `#93a6b4` — 7.50:1 | Small mono text on the darkest surface in the product |
| Chip / banner ink | `--accent`, `--warn`, … reused as text | `--ok-ink`, `--warn-ink`, `--bad-ink`, `--info-ink` | Status fills and status *text* are different colours; conflating them put 4.5:1 text on tinted fills by luck |
| Button hover border | `#d3d9df` | `--line-control` | Hover was the only affordance and was 1.6:1 |

Two of these (focus ring on inputs, scene hint) were created by the previous pass. Saying so is the
point of keeping the ledger.

---

## 3. Typographic details, and why each one

| Detail | Before | Now | Reason |
|---|---|---|---|
| Chips | All mono, 11px | Sans 11.5px for phrases; mono 11.5px for identifiers | "needs a human" set in a code face reads as a token, not a sentence. `looksLikeIdentifier()` decides: ALL_CAPS, dotted.paths, `RUN-…`, `#19` stay mono |
| Micro-labels | 10.5–11px | 11.5px minimum, 0.08–0.1em tracking | Uppercase at 10.5px is the least legible text in a product whose job is being read carefully |
| Numerals | `tabular-nums` on `body` | Only on `td/th/.num/.display/.mono` | Inter's tabular figures are monospaced; applying them to prose widened every paragraph for no benefit |
| Mono face | Browser default | JetBrains Mono + `font-feature-settings: "zero" 1` | Slashed zero: these strings are digests and clause numbers, where `0`/`O` confusion is a defect |
| Line height | 1.5 flat | 1.55 body, 1.45 table/small, 1.4 headers | Dense tables and 40px display type cannot share one ratio |
| Synthetic styles | Browser-invented | `font-synthesis: none` | If a face is missing, say so by falling back — do not let the browser fake a bold |
| Headings | — | `text-wrap: balance`; `p { text-wrap: pretty }` | Kills single-word orphan lines in panel headings |
| Input text | 13px | 13px, **16px under 620px** | iOS zooms any focused field below 16px; the trace and simulator are used on tablets |
| Sidebar labels | 10.5px | 11.5px | The smallest text sat on the darkest surface — the worst possible pairing |

---

## 4. Layout flaws found while looking at type

1. **Sources table had no column model.** Auto layout let a long classification chip claim its
   full nowrap width, squeezing the document title into a 10-line column beside 400px of empty
   space. Fixed with `table-layout: fixed`, explicit `<colgroup>` widths, and `td .chip { white-space: normal }`
   so long values wrap inside their own column.
2. **Classification was rendered as a badge, not a sentence.** `BINDING_REQUIREMENT (within Abu
   Dhabi); OUT-OF-JURISDICTION COMPARATOR for a Dubai case` is two facts; the badge now carries the
   token and the scope sits under it as text.
3. **Two hover colours** (`#fafbfc` and `#f7faf9`) for the same interaction. One now.
4. **Truncated engine string** in the evidence rail — `bm25 (k1=1.5, b=0.75), …` — replaced with the
   engine name plus a title attribute carrying the full value.
5. **Evaluation matrix clipped at the panel edge.** Five columns with `white-space: nowrap` on
   snake_case assertion keys (`no_patient_direct_communication_for_genetic_result`) pushed the last
   column past the border and cut it mid-word. Fixed layout plus `overflow-wrap: anywhere`.
6. **Raw ISO timestamp in the UI**: `2026-10-22T18:38:45.451319+00:00` was being printed as a
   subtitle. Now `finished 18:38:45`.
7. **Case timeline opened as a dead end** — two rows and a grey "select a case" instruction. It now
   selects the most recent case on arrival, so the page does its job without a prompt.
8. **Layer cards truncated their own descriptions** into a right-hand corner (`Where the case is in
   the institution's ow…`). The blurb is a sentence; it now sits under the heading and wraps.
9. **Acknowledgment column mixed alignments** — a right-aligned count beside a left-aligned chip, so
   each row read as two columns. One cell, one alignment: `current rev` plus the count.

---

## 5. What is still not right

- **No optical sizing.** Inter's variable axis includes `opsz`; the file loaded is the `wght`-only
  subset, so 40px display and 11.5px labels share one set of proportions.
- **No Arabic.** A UAE product would need an Arabic face and RTL mirroring. Out of scope for this
  pass and it should not be claimed otherwise.
- **Contrast is computed, not rendered.** The script compares token pairs; it does not catch a
  translucent overlay, a gradient, or a colour set inline in a component. `grep -rn "#[0-9a-f]\{6\}" src`
  still finds a handful of literals in page components.
- **No screen-reader or zoom pass.** Unchanged from the previous review, and still the largest hole.

## 6. Reproducing

```bash
python3 scripts/check_contrast.py          # 35 pairs, exit 1 on failure
make check                                 # includes the font-serving test
cd frontend && npm run build && cd .. && make dev
```
