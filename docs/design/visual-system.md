# ResultRelay visual system v4

This spec covers type, layout, colour, components and motion for the ResultRelay console. It builds on v3: light canvas, ruled panels, colour only for state. Every value here can be implemented as written. Where a value replaces a v3 value, the v3 value is shown as `was …`.

**Target viewport.** The demo is filmed at 1920×1080 with the browser at 120 % zoom, which gives a **1600×900 CSS-px viewport**. Every layout number below is checked at that size (called *film* below), at **1440×900** (a typical judge laptop) and at **1920×1080 at 100 %**. All measurements in this document are CSS px. To convert a screenshot measurement, divide by 1.2 (the `_work/video/probe/*` frames) or by 1.25 (`docs/figures/*.png`).

**Rules this spec keeps.** Colour is reserved for case state. Motion is allowed only when it carries information. There is no Tailwind. Everything is plain CSS plus the `motion` package (`import … from "motion/react"`), or pure CSS/SVG.

---

## 0. The trust idea, stated once

The app has three voices, and the reader must always know which one is speaking:

| Voice | What it is | Authority | Visual register (everywhere) |
|---|---|---|---|
| **AI said** | A council agent's claim, rationale or recommendation (policy analyst, telecom analyst, adversarial reviewer, orchestrator) | Advisory only: it can propose and escalate, never enforce | **Dashed** 1px border in `--ai-line`, violet ink label, dashed-ring glyph ◌, the words "advisory" or "model" in the label |
| **Code verified** | A deterministic check: quote found on its source page, revision bound, invariant held, hash recomputed | Verifies facts. It does not decide what happens next | **Solid hairline**, neutral ink, check-in-circle glyph ✓ (red cross ✗ when the check fails) |
| **Gate decided** | The deterministic gate's decision and the state transition it applied | Binding | **Solid 3px ink bar**, 600 weight, filled "barrier" glyph ▣; the outcome badge is the only coloured element |

The visual weight rises with authority: dashed, then hairline, then a heavy bar. Today the trace does the reverse. The orchestrator's advice sits in a filled amber box while the gate is plain text (see critique C21). The `<Provenance>` tag (§5.17) and these three registers are used on every page that shows a decision: Console, Simulator, Trace, Compare and Audit.

---

## 1. Critique of the v3 screens (25 issues, measured)

Sources: `docs/figures/console.png` and `console_trace.png` (scale 1.25), and `_work/video/probe/v3_*.png` and `frame_*.png` (scale 1.2). Font facts were measured with fontTools on the shipped `web/public/fonts/*.woff2`.

**Type and glyphs**

- **C1. Missing glyphs fall back to a different font.** The shipped Plex subsets have 232 glyphs (Sans) and 229 (Mono). `→ ← ↔ ≠ ≤ ≥ ✓ ✗ ●` are absent: fontTools reports U+2192 missing in all three files. Every `RESULT_DRAFT → RESULT_FINALIZED`, `#4 15:15:00 → ESCALATION_REQUIRED` and `A → B` transition therefore draws its arrow in Segoe UI or Consolas. Those fonts have a different weight and x-height, so the arrow sits about 1px high in the mono runs (`frame_05`, `frame_08`, `v3_trace`).
- **C2. The `"zero" 1` setting does nothing.** The Mono subset's GSUB table contains only `ccmp, dnom, frac, numr`. There is no `zero`, `tnum` or `ss0x` feature to turn on. (Plex Sans figures are already tabular by default: `0` and `1` both advance 600 units, so `tabular-nums` is a harmless no-op.)
- **C3. Too many near-identical sizes.** The CSS uses 12, 12.5, 13, 13.5, 14, 14.5 and 15px: seven sizes within 3px, and three of them fractional. 13 → 13.5 is a 3.8 % step, below the roughly 10 % difference people notice. At 120 % zoom, 12.5 / 13.5 / 14.5 render at 15 / 16.2 / 17.4 device px, so hinting varies from line to line. Panel titles (15px) are only 7 % larger than body text (14px) and do not separate from it.
- **C4. The hierarchy is inverted.** The page h1 is 22px, smaller than the 30px chain counts and the 24px exit counts. The page title loses to its own numbers.
- **C5. Arabic falls back to a system font.** The Standards query `نقل البيانات الصحية خارج الدولة` renders in the system Arabic face (`v3_standards`). The input has no `dir="auto"`, so the RTL text is left-aligned and the caret starts on the wrong side.

**State language, chips and colour**

- **C6. Raw enum strings everywhere.** At least 30 distinct SCREAMING_SNAKE tokens sit on primary surfaces. In 12px uppercase mono (7.2px per character), `CORRECTED_RESULT_ACKNOWLEDGED` is a 209px chip (`frame02`), wider than the State column's ideal 180px. `SOURCE_AMBIGUITY`, `VERIFIED_OFFICIAL`, `ANSWERED`, `UPHELD` and `APPLIED` all read as tokens, not facts.
- **C7. Chips are overused.** Evaluation shows 24 badges across 12 rows. The green "stable" chip is identical in all 12 rows and carries no information. The best row's "11/12" is in amber (the warning colour), and so is "3/12". Standards › Retrieval shows three stat chips in three tones, then two full-width amber banners that repeat the "45 excluded" fact.
- **C8. One colour carries many meanings.** Green means *documented*, *binding requirement*, *quote verified*, *gate permitted*, *transition applied*, *run complete*, *chain valid*, *stable* and *current revision*: nine meanings. Amber means *escalation*, *delivered*, *source ambiguity*, *verified official* and *safe-scenario count*. Red marks `ESCALATION_REQUIRED`, which is the system working as designed.
- **C9. The zero counts fail contrast.** Zero counts are `#d5dae0` on white, 1.41:1. That fails WCAG 1.4.3 even for large text (3:1). A "0" under *Delivery unknown* is good news, and it should be readable.
- **C10. The escalation exit is red.** "With a named person" has a 3px `--bad` red rule. Escalating to a named role is the designed *safe* exit. Red should mean *refused or broken*.

**Layout, proportion and alignment**

- **C11. The header wastes vertical space and repeats the sidebar.** The topbar is 98px (22 + 18 padding, 22px h1, 21px purpose line), 10.9 % of the 900px filmed viewport. The "Synthetic data, offline" flag is bottom-aligned (`align-items:flex-end`) to the purpose line, and with its 1px rule and 4px radius it looks exactly like a secondary button. The same fact is repeated in the sidebar footer (190px of text).
- **C12. The table text and the panel title start at different x.** `th, td` use 12px horizontal padding and `.panel-head` uses 16px, so "Case" starts 4px left of "Cases" (console.png: x 352 vs 357 at 1.25). The same 4px offset appears in every flush table.
- **C13. The chain's connectors and exits don't line up.** The connectors are 10px rotated squares with a 1px `#d5dae0` border (1.41:1), placed at `top:22px`. They line up with the stage index, not with the count or the visual centre, so they read as tab separators rather than flow. The exits grid (three columns with 16px gaps) does not line up with the six-column chain: the edge of exit 1 misses the stage-2 boundary by 10.7px. The two count anatomies also differ. Chain counts are 30px, left-aligned, under the name. Exit counts are 24px, right-aligned, on the name line.
- **C14. The final stage is always tinted.** The "Documented" stage has a green fill even when its count is 0, so colour stops meaning state.
- **C15. The sidebar's active marker is split.** The active bar is at `left:-14px`, flush against the viewport edge and 14px away from its own tinted fill, so it reads as two separate marks. The active item also switches weight from 400 to 600, which widens its label by about 4 % and shifts it. Group labels are 12.5/500 and items are 14/400, a 1.5px difference that gives almost no hierarchy. Brand text starts at x 60 while nav text starts at x 24, giving two left edges.
- **C16. Two-line table rows are too tall.** Two-line rows are 58.6px (10 + 19.6 + 18 + 10 + 1), so the Cases table shows 6.5 rows in the filmed viewport. `SYN-CASE-003` appears four times because the run suffix is cut off (`split("-").slice(0,3)`), so different runs look like duplicate rows.
- **C17. The acknowledgement chip wraps.** "current revision" wraps to two lines in a 126px column (`frame02`), making a 46px-tall chip. The cause is `td .chip {white-space:normal}`.
- **C18. The "Trace" column is invisible.** The last column (70px, 7.5 % of the table width) is empty until hover. Keyboard users see it only on focus.
- **C19. Intro banners are too wide and push the content down.** Banners span the 1300px content width, about 190–200 characters per line (Simulator, Standards, Trace, Audit, Evaluation), against a 60–80ch readable measure. Five of the eight pages open with one, which pushes the working surface down by 72–86px.
- **C20. Controls have inconsistent heights.** Selects are 35.6px, `.btn` is 37px (7 + 21 + 7 + 2) and `.btn.small` is 29.5px. In the Simulator, "Start run" and the selects are visibly 2px off. The configuration select truncates its own label (`…(policy analys`) because its width comes from the grid column, not the content.

**Page-level**

- **C21. The trace inverts the trust hierarchy.** The orchestrator's *advisory* "escalate to a person" gets the strongest container (amber fill plus a 3px bar). The Gate (binding) is plain 13.5px text. The Result is a 12px chip. AI rationale and policy quotations share one `.quote` style (3px `#d5dae0` bar), so a model's sentence looks like a cited clause. The reviewer's answers are printed twice: once as a mono line, then again as `objection=… (p=0.93)`.
- **C22. The Simulator buries the most important fact.** A 6px navy progress bar at 100 % says only "done". "run complete" is green while the outcome is an escalation. The Open questions cell holds 14 lines of 12.5px text in a one-third column. Next to it, *Escalations*, the fact that matters most (who owns the case now), is one line of raw codes (`SUPERVISOR, CLINICAL_LEAD`) with about 300px of empty space under it (`frame_08`).
- **C23. The Simulator's right rail is mostly empty.** The Channel status panel ends after three rows, leaving about 260px blank down to the fold. Channel status is shown as `UP` / `DOWN` chips.
- **C24. Side-by-side leaves half the frame empty and hides the difference.** Content ends at y 510 of 1080, so 53 % of the filmed frame is blank. The diverging final state, the whole point of the page, is a 12px chip. Steps are mono strings, and nothing aligns the left and right sides row by row.
- **C25. Audit and Gap register show raw data where a verdict belongs.** Audit dumps raw JSON (`{"obligation": {"choice": …`) into a 470px Summary column, so `agent.message` rows grow to five lines (about 96px). The page's verdict, "chain valid", is its smallest element (a 12px chip). In the Gap register, the 44px ID column wraps `GR-01` into `GR-` / `01`. Workflow stage and jurisdictions, which are prose, are set in mono. Evaluation sets its numeric headers in mono and wraps them to two lines (a 62px header row), and its zeros are at full ink, so the non-zero failure cells (2, 12) don't stand out.
- *(Also, not counted above.)* There are 148 inline `style={{}}` objects across the pages, plus hard-coded `#fbfcfd`, `#f8f9fa` and `opacity:.85`. They bypass the tokens, so `scripts/check_contrast.py` cannot see them.

---

## 2. Typography

### 2.1 Faces: keep IBM Plex, add IBM Plex Sans Arabic

| Role | Family | Weights shipped | Licence | Why |
|---|---|---|---|---|
| UI and prose | **IBM Plex Sans** | 400, 500, 600 | SIL OFL 1.1 | Unambiguous `I l 1` and `0 O`, open apertures, and a slightly technical voice that suits a lab report. Its figures are already tabular (all digits 600 units), so table numbers align without features. Kept because it is already shipped and verified, and switching would only change the look. |
| Identifiers | **IBM Plex Mono** | 400, 500 | OFL 1.1 | Same skeleton and x-height as Plex Sans (both 516/1000, cap 698/1000, measured), so mixed runs share one baseline and x-height. |
| Arabic | **IBM Plex Sans Arabic** | 400, 500, 600 | OFL 1.1 | Designed as Plex Sans's Arabic companion (IBM / Bold Monday). It is declared **under the same family name** with a `unicode-range`, so mixed Latin and Arabic strings pick the right glyphs with no markup. |

**Rejected.** *Inter / Inter Tight*: excellent, but it has no matching Arabic, and the repo history (`05-typography-and-colour.md`) shows Inter was already swapped out once. *Geist*: no Arabic and fewer clinical-grade glyph distinctions (`Il1`). *Source Sans 3*: good, but its Arabic pairing would be a different family (Noto), so Latin and Arabic would sit on different rhythms.

**Fix C1 and C2: subset properly.** Do not use the fontsource "latin" subset. Generate your own subset from the upstream TTFs (github.com/IBM/plex) with fontTools, keeping all layout features:

```bash
pyftsubset IBMPlexSans-Regular.ttf --flavor=woff2 --layout-features='*' \
  --unicodes="U+0000-00FF,U+0131,U+0152-0153,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20AC,U+2122,\
U+2190-2199,U+21A9-21AA,U+2212,U+2215,U+2260,U+2264-2265,U+2248,U+00D7,U+2026,U+2030,U+2032-2033" \
  --output-file=plex-sans-400.woff2
# same for 500, 600 and Plex Mono 400/500. Arabic:
pyftsubset IBMPlexSansArabic-Regular.ttf --flavor=woff2 --layout-features='*' \
  --unicodes="U+0600-06FF,U+0750-077F,U+0870-08FF,U+FB50-FDFF,U+FE70-FEFF,U+200C-200F,U+0660-0669" \
  --output-file=plex-sans-arabic-400.woff2
```

Check the result with `python -c "from fontTools.ttLib import TTFont; print(0x2192 in TTFont('plex-sans-400.woff2').getBestCmap())"`. It must print `True`. Draw ✓ ✗ and the state glyphs as inline SVG (§5.8), never as characters.

### 2.2 Scale: integer sizes on a 4px line grid

| Token | Size / line | Weight | Tracking | Use |
|---|---|---|---|---|
| `--t-display` | 40 / 44 | 600 | −0.022em | One headline figure per page at most (Evaluation "11 of 12", Compare final-state delta) |
| `--t-figure` | 32 / 36 | 600 (400 when zero) | −0.02em | Chain counts, KPI values |
| `--t-figure-sm` | 20 / 24 | 600 | −0.01em | Exit counts, inline KPI values |
| `--t-title-1` | 24 / 32 | 600 | −0.014em | Page h1 (was 22) |
| `--t-title-2` | 18 / 24 | 600 | −0.008em | Section heads, case header, final-state labels |
| `--t-title-3` | 15 / 20 | 600 | −0.004em | Panel titles, agent names, trace lane labels |
| `--t-body-lg` | 15 / 24 | 400 | 0 | Quotes, AI rationale, page prose; max 72ch |
| `--t-body` | 14 / 20 | 400 / 500 | 0 | UI default, table primary line, buttons, nav |
| `--t-small` | 13 / 18 | 400 / 500 | 0 | Secondary lines, hints, field labels, small buttons |
| `--t-caption` | 12 / 16 | 500 | +0.01em | Meta, timestamps, group labels, badge text, stage notes |
| `--t-mono` | 13 / 20 | 400 | 0 | Identifiers inside 14px text (case ids, clause refs) |
| `--t-mono-sm` | 12 / 16 | 400 | 0 | Hashes, codes under humanised labels, tooltips |

Rules:

- **Nothing below 12px.** At 120 % zoom 12px renders at 14.4 device px, the smallest size that survives video compression.
- **No 600 weight below 13px.** Plex 600 clogs at 12px on 1× screens, so use 500.
- **No uppercase anywhere in sans.** Uppercase exists only inside mono codes.
- **Mono is one step smaller than the sans it sits in** (13 inside 14, 12 inside 13). The x-heights are equal (516), but Mono is about 12 % wider (`a` advances 600 vs 534 units), so at the same size it looks larger.
- **Display figures pull left by `margin-inline-start: -0.04em`** so that the tabular "1" side bearing doesn't indent the figure from its label.
- **Line length:** prose and quotes max `72ch`; banners and notices max `960px`; table text clamps to 2 lines (`-webkit-line-clamp:2`), with the full text in a tooltip.
- **`text-wrap: balance`** on h1–h3 and badge-free titles; **`text-wrap: pretty`** on paragraphs.

### 2.3 Arabic

- Declare the Arabic files under `font-family:"Plex Sans"` with the `unicode-range` above (§8).
- On `:lang(ar)` and `[dir="rtl"]` blocks, use `font-size: 1.0714em` (14 → 15) and `line-height: 1.6`. Arabic in Plex Sans Arabic looks about one step smaller than Latin at the same size, and its marks need room above and below.
- Add `dir="auto"` to every `<input>`, `<textarea>`, quote block and table cell that shows source text.
- Use logical properties everywhere (`padding-inline-start`, `border-inline-start`, `inset-inline-start`). The left bars on quotes, banners and the gate lane must flip in RTL without extra CSS.

---

## 3. Layout

### 3.1 Shell and grid

| Token | Value | Notes |
|---|---|---|
| `--sidebar-w` | **224px** (was 236) | Labels plus 16px icons; 14 % of the film width |
| `--header-h` | **88px** including 1px rule (was ≈98) | §5.2 |
| `--page-pad-x` | 32px (≥1280) · 24px (1024–1279) · 16px (<1024) | |
| `--page-pad-top` | 24px | |
| `--content-max` | **1600px** | Left-aligned, never centred, so the left edge stays fixed relative to the sidebar |
| `--gutter` | **24px** between columns | |
| `--stack` | **16px** between stacked panels; **24px** between page bands (chain band → work area) | |
| `--rail-w` | **320px** (viewport <1500) · **360px** (1500–1799) · **400px** (≥1800) | Right rail on the Console, Simulator and Trace |

The page grid is `grid-template-columns: minmax(0,1fr) var(--rail-w); gap: var(--gutter)`. Pages without a rail use a 12-column grid (`repeat(12, minmax(0,1fr))`, same gutter).

| Viewport | Content width | Main | Rail | Chain stage width |
|---|---|---|---|---|
| **Film 1600×900** | 1312 | 928 | 360 | 154.7 |
| 1440×900 | 1152 | 808 | 320 | 134.7 (stage padding drops to 14) |
| 1920×1080 at 100 % | 1600 (capped) | 1176 | 400 | 196 |
| <1100 | single column; the rail stacks under the main column; the chain becomes 3×2 | | | |

### 3.2 Spacing scale (4px base)

`--s-0:0 · --s-1:2px · --s-2:4px · --s-3:6px · --s-4:8px · --s-5:12px · --s-6:16px · --s-7:20px · --s-8:24px · --s-9:32px · --s-10:40px · --s-11:48px · --s-12:64px`

Vertical rhythm: every line height is a multiple of 4. Inside a panel, related elements are 4px apart, separate items 8–12px apart and sections 16px apart. Panels are 16px apart and page bands 24px apart.

### 3.3 Panels

| Part | Value |
|---|---|
| Panel | `--surface`, 1px `--rule`, radius `--r-panel` 6px, no shadow |
| Panel head | **height 44px**, padding `0 16px`, title `--t-title-3`, hint `--t-small` `--ink-3` 8px after the title (baseline-aligned), 1px `--rule-2` below |
| Panel head actions | Only small (28px) secondary or ghost buttons and selects. A page's one primary action lives in the page header, never in a panel head (fixes "Run a scenario" competing on the Console) |
| Panel body | padding 16px; `flush` = 0 |
| Flush table | First and last cell padding-inline **16px**, so table text lines up with the panel title (fixes C12) |

### 3.4 Tables and density

| | Standard (default, filmed) | Compact (`[data-density="compact"]`) |
|---|---|---|
| Header row | 36px · 12/16 500 `--ink-2` on `--surface-2`, one line, 1px `--rule` below | 32px |
| Single-line row | **44px** (12 + 20 + 12) | 36px (8 + 20 + 8) |
| Two-line row | **56px** (10 + 20 + 16 + 10) | 48px (6 + 20 + 16 + 6) |
| Cell padding-inline | 12px (16px on the outer cells) | 10px (16px outer) |
| Row rule | 1px `--rule-2`; no zebra striping | same |
| Hover | `--surface-hover` | same |
| Panel body | 16 | 12 |
| `--t-figure` | 32/36 | 28/32 |

Table rules:

- Numbers: right-aligned, sans (Plex figures are tabular), never mono.
- Zeros: `--ink-4`, weight 400. Non-zero failure counts: `--crit`, weight 500.
- Identifiers: mono `--t-mono`.
- Every table declares a `<colgroup>` with explicit widths (§7).
- `vertical-align: top` for two-line rows and `middle` for single-line rows.
- The density toggle lives in the sidebar footer and is stored per viewer in `localStorage` inside try/catch.

---

## 4. Colour

### 4.1 Neutrals and action (contrast measured against `#ffffff` / canvas `#f4f5f7`)

| Token | Hex | On white | On canvas | Use |
|---|---|---|---|---|
| `--ink` | `#141c24` | 17.19 | 15.76 | Primary text, gate bar |
| `--ink-2` | `#3b4754` | 9.48 | 8.69 | Secondary text, labels, table headers |
| `--ink-3` | `#5b6572` | 5.92 | 5.42 | Muted text (≥ 4.5, all sizes) |
| `--ink-4` | `#7d8794` | 3.64 | 3.34 | **Large or non-text only:** zero figures (≥ 20px), chevrons, icons, control borders |
| `--line-control` | `= --ink-4` | 3.64 | 3.34 | Input, select and secondary-button borders (WCAG 1.4.11 ≥ 3:1). The old `#8a95a1` measured **2.79 on canvas**, which fails |
| `--rule-strong` | `#c4cbd3` | 1.64 | 1.50 | Chain track, timeline spine (decorative structure) |
| `--rule` | `#dde1e6` | 1.31 | 1.20 | Panel borders |
| `--rule-2` | `#eceef1` | 1.16 | 1.07 | Inner hairlines, row rules |
| `--canvas` | `#f4f5f7` | | | Page background |
| `--surface` | `#ffffff` | | | Panels |
| `--surface-2` | `#f8f9fa` | | | Table header, sidebar hover |
| `--surface-hover` | `#f1f3f5` | | | Row hover (`--ink-3` on it: 5.32) |
| `--action` | `#1f4a7a` | 9.06 | 8.30 | Primary buttons, links, selection, focus |
| `--action-hover` | `#173a61` | 11.57 | | |
| `--action-soft` | `#edf2f8` | | | Selected nav item and row (`--ink-2` on it: 8.42) |

White text on `--action` measures 9.06.

### 4.2 Case-state palette: one meaning per hue

Each tone has a **text** colour (≥ 4.5:1 on white and on its soft fill), a **soft** fill, a **rule**, and a **solid** for glyphs, beams and bars (≥ 3:1). It also has a **glyph shape**, so state never depends on colour alone (GOV.UK tag guidance; WCAG 1.4.1).

| Tone | Meaning, and nothing else | Text | Soft | Rule | Solid | Text on soft | Solid on white | Glyph |
|---|---|---|---|---|---|---|---|---|
| `ok` | **Documented**: closed, acknowledgement on the current revision recorded | `#1a6b43` (6.51) | `#edf6f0` | `#b5d8c3` | `#2a8a5a` (4.30) | 5.90 | 4.30 | filled circle ● |
| `progress` | **In progress**: moving along the chain, nothing wrong yet | `#3b4754` (9.48) | `#f1f3f5` | `#d3d8de` | `#5b6572` | 8.52 | 5.92 | half-filled circle ◐ |
| `att` | **Needs a person**: escalated to a named role, correction in progress, awaiting a human | `#8a4b00` (6.80) | `#fdf4e7` | `#ecd0a5` | `#a8650a` (4.63) | 6.24 | 4.63 | diamond ◆ |
| `crit` | **Refused or broken**: gate refused, delivery unknown or failed, chain invalid, check failed | `#a3201a` (7.56) | `#fcefee` | `#ecc3c0` | `#c4312a` (5.50) | 6.74 | 5.50 | triangle ▲ |
| `info` | **Comparator and reference**: a clause from another jurisdiction, informational notes | `#0f5e66` (7.46) | `#eaf5f6` | `#b7dade` | `#3f8f99` (3.75) | 6.71 | 3.75 | ring ○ |
| `ai` | **AI said**: advisory output of a model | `#5d3fa0` (7.82) | `#f5f2fb` | `#d8cdef` | `#9179cc` line (3.61) | 7.07 | 3.61 | dashed ring ◌ |

Reassignments that resolve C8:

- *Binding requirement* is a **classification**, not a state. It becomes a neutral badge with weight 500 ("Binding requirement"). Only *comparator* gets a tone (`info`, dashed), because a comparator must never be mistaken for an obligation.
- *Quote verified*, *chain valid*, *transition applied*, *stable* and *current revision* are **code-verified facts**. They render in the code register (neutral ink + ✓), not in green.
- *Gate permitted* is neutral (`progress`). Only *Gate refused* is coloured (`crit`).
- *Run complete* is neutral text.
- *Escalated to …* is `att`, not `crit`.

### 4.3 The three provenance registers (exact)

| | AI said | Code verified | Gate decided |
|---|---|---|---|
| Container | `border: 1px dashed var(--ai-line)`, radius 6, bg `--surface` | Inline rows, or a block with `border-inline-start: 1px solid var(--rule-strong)` | `border-inline-start: 3px solid var(--ink)`, bg `--surface`, padding 12 16 |
| Glyph (12px SVG) | Dashed ring: r 4.5, stroke 1.5, dasharray `2 1.6`, `--ai-line` | Circle r 5, stroke 1.25, `--ink-3` + check path, stroke 1.5, `--ink-2`; failed = cross in `--crit-solid` | Rounded square 10×10, radius 2, fill `--ink`, with a 6×2 white bar at y 4 (a "barrier") |
| Label | `--t-caption`, `--ai`: "Policy analyst · model, advisory" | `--t-caption`, `--ink-2`: "Checked by code" | `--t-small` 600, `--ink`: "Gate" |
| Body text | `--t-body-lg` 15/24 `--ink`, max 72ch, no left bar, no quotation marks (it is a claim, not a source) | `--t-small` 13/18 `--ink-2` | `--t-body` 14/20 `--ink`, 500 |
| Numbers | Confidence `p 0.93` in `--t-mono-sm` + a 40×4px meter (`--ai-line` on `--rule-2`) | | |
| Never | Fills, shadows, green or red | Colour unless the check failed | Dashed lines |

### 4.4 Focus, selection, overlays

- Focus: `outline: 2px solid var(--action); outline-offset: 2px` on all interactive elements. Inside tables and lists use `-2px`.
- Selection: `::selection { background: #cfe0f3; color: var(--ink) }`.
- Tooltip and toast surface: `--ink` with white text (17.19:1) and secondary text `#aab3bd` (8.10:1).

---

## 5. Components

### 5.1 App shell and sidebar

- **Sidebar.** Width 224. Bg `--surface`. Border-right 1px `--rule`. Padding `12px 12px 16px`. Sticky, full height. Flex column.
- **Brand row.** Height 56, padding `0 8px`, gap 10. Mark 24×24, radius 6, `--action`, with a 14px white glyph. Name `--t-title-3` (15/20 600). Sub-line `--t-caption` `--ink-3`: "Critical-result communication" (single line, 12px fits in 158px). Text starts at x 42 inside the sidebar.
- **Group label.** `--t-caption` 500 `--ink-3`. Padding `16px 8px 4px` (first group: 8px top).
- **Nav item.**
  - Box: height 32, padding `0 8px`, radius 4, gap 10.
  - Icon: 16px Lucide (ISC licence, inline SVG, stroke 1.5), `--ink-3`.
  - Label: `--t-body` **500** `--ink-2`.
  - Hover: `--surface-hover`, label `--ink`.
  - Active: `--action-soft` background, label and icon `--action`, weight stays 500 (no reflow), plus a **2×16px bar inside the item** (`inset-inline-start:0; top:8px; border-radius:0 2px 2px 0; background:var(--action)`). Fixes C15.
- **Live count on "Console".** A right-aligned badge with the number of cases needing a person: height 18, padding `0 6px`, radius 9, `--t-caption` 600 tabular, `--att` on `--att-soft`. Animates with the ticker (§6.1). It is hidden at 0.
- **Icons.** Console `layout-dashboard`, Case timeline `list-tree`, Simulator `play-square`, Side-by-side `columns-2`, Decision trace `git-commit-vertical`, Standards `scale`, Evaluation `flask-conical`, Audit `link`.
- **Footer.** Top rule 1px `--rule-2`, padding-top 12, `--t-caption` `--ink-3`. Line 1: "Demonstration build · v0.1.0" (version in mono 12). Line 2: the density toggle (§5.12, small segmented: Standard / Compact). Maximum height 72. The synthetic-data statement moves to the header pill, so it appears once.

### 5.2 Page header

- Height **88** = padding `16px 32px 15px` + h1 32 + gap 4 + purpose 20 + 1px border.
- Bg `--surface`. Grid `1fr auto`, gap 24, `align-items:start`.
- **h1** `--t-title-1`.
- **Purpose** `--t-body` `--ink-2`, one line, copy ≤ 100 characters, `max-width: 90ch`.
- **Right cluster** (flex, gap 12, `margin-top:4px` so 24px items centre on the 32px title line):
  - **Environment pill:** height 24, padding `0 10px 0 8px`, radius 12, bg `--canvas`, no border, `--t-caption` 500 `--ink-2`, 6px `--info-solid` dot, gap 6. Text: "Synthetic data · offline". It is not a button: no hover, `cursor:default`. Its `title` holds the full disclaimer.
  - **Page primary action**, if any: button height 32 with `margin-top:-4px`. For example "Run a scenario" on the Console, "Run the matrix" on Evaluation.

### 5.3 The chain: the signature element

On the Console (aggregate), the Simulator and Compare (one case, compact) and the Trace header (one case, compact).

**Aggregate anatomy (Console, film).** The **Chain panel** fills the main column (928 × 156). The **Needs-a-person panel** fills the rail (360 × 156), aligned to the same grid as the work area below it, so the chain band and the table share edges (fixes C13).

```
┌ Chain panel ───────────────────────────────────────────────────────────────┐ ┌ Needs a person ─────────── 3 ┐
│ ○──────────○──────────○──────────●──────────○──────────●                   │ │ ◆ With a named person      2 │
│ 1          2          3          4          5          6                   │ │   Lab supervisor 2           │
│ Finalised  Sending    At the     Delivered  Acknow-    Documented          │ │ ▲ Delivery unknown/failed  0 │
│ 0          0          gateway 0  2          ledged 0   3                   │ │   reconcile before retry     │
│ released   queued or  accepted,  delivered, named      the only state      │ │ ◆ Correction in progress   1 │
│ by the lab in flight  not deliv. not ackn.  person…    that closes         │ │   earlier ack. void          │
└────────────────────────────────────────────────────────────────────────────┘ └──────────────────────────────┘
```

**Stage cell** (six equal columns, no vertical separators; the track implies the sequence):

| y (px) | Element | Spec |
|---|---|---|
| 0–16 | padding | 16 (14 at <1500 viewport); padding-inline 16 / 14 |
| 16–32 | Rail row | Node 12×12 at x = padding, centred on the track (y 22–23 is the 2px track, `--rule-strong`, drawn once across the panel from node 1's centre to node 6's centre). Stage index "1"–"6" in `--t-caption` `--ink-3`, 8px right of the node |
| 44–64 | Name | `--t-body` 600 `--ink`, one line. Labels: **Finalised · Sending · At the gateway · Delivered · Acknowledged · Documented** |
| 68–104 | Count | `--t-figure` 32/36, `margin-inline-start:-0.04em`. Zero: `--ink-4`, weight 400 (3.64:1, large text, so it passes; fixes C9). Non-zero: `--ink`, 600. Documented and > 0: `--ok` |
| 108–140 | Note | `--t-caption` 400 `--ink-3`, 2 lines max, min-height 32. Copy ≤ 30 chars: "released by the lab" · "queued or in flight" · "accepted, not delivered" · "delivered, not acknowledged" · "named person, this revision" · "the only state that closes" |
| 140–156 | padding | 16 |

**Node states.**

| State | Fill | Border |
|---|---|---|
| Count 0 | `--surface` | 2px `--ink-4` |
| Count > 0 | `--ink-2` | 2px `--ink-2` |
| Documented and > 0 | `--ok-solid` | |
| Selected (filter) | + 3px `--action` ring at offset 2 | |

There is no permanent tint on the Documented cell (fixes C14).

**Interaction.** Each stage is a `<button aria-pressed>` that filters the Cases table to its states.

| Interaction | Effect |
|---|---|
| Hover | bg `--surface-hover` |
| Pressed | 2px `--action` bar at the bottom inside the cell; name in `--action` |
| Focus | standard ring at −2px |

**Needs-a-person panel.**

- Head: height 28, padding `6px 16px`. "Needs a person" in `--t-caption` 600 `--ink-2`, with the total on the right (`--t-caption` 600 tabular).
- Three rows of 42px (padding `4px 16px`, rule-2 between), grid `12px 1fr auto`, gap 10.
  - Glyph: tone shape (◆ att, ▲ crit, ◆ att).
  - Name: `--t-small` 500 `--ink`.
  - Second line: `--t-caption` `--ink-3`. For "With a named person" this line shows **owners from the data**: "Lab supervisor 2 · Clinical lead 1". For the other rows it is a ≤ 32-char reason.
  - Count: `--t-figure-sm` 20/24 tabular. Zero: `--ink-4` 400. Non-zero: tone text, 600.
- Each row links to the filtered table.

**Compact single-case chain** (Simulator, Compare, Trace header): height **64**.

- Nodes are 10px; names are `--t-caption` 500 under the nodes; no counts.
- Passed segments of the track become 2px `--ink-2`. The current node gets a 3px ring in its tone.
- If the case left the chain, a branch drops from the current node as a 2px elbow (radius 8) to a pill on the right labelled with the exit and owner: "◆ Escalated to lab supervisor". The pill is height 24, `--att-soft`, 1px `--att-rule`, `--t-caption` 600 `--att`.
- Unreached nodes have a 2px `--ink-4` border; unreached segments are `--rule-strong` dashed `4 4`.

### 5.4 KPI / metric

| Part | Spec |
|---|---|
| Box | Panel, padding 16, min-height 104, min-width 168 |
| Label | `--t-caption` 500 `--ink-2` |
| Value | `--t-figure` (24/32 600 in a 4-up strip below 1440) |
| Sub-line | `--t-caption` `--ink-3` |
| Delta | Inline after the value, 8px gap, `--t-caption` 600: "+1" and "−1" in `--ink-2` with a 10px arrow SVG. Never green or red; a change in count is not good or bad by itself |
| Clickable | Hover `--surface-hover`; selected 2px `--action` inset bar at inline-start |

### 5.5 Status badge: humanised

**Anatomy.**

| Part | Spec |
|---|---|
| Box | Height **20**, padding `1px 7px 1px 6px`, radius 4, 1px border `{tone}-rule`, bg `{tone}-soft` |
| Glyph | 8px tone glyph, gap 6 |
| Label | `--t-caption` **500** `{tone}` text, sentence case, `white-space:nowrap`, ellipsis at `max-width:100%` |
| Large variant | Height 24, `--t-small` 600, glyph 10, for page and case headers |
| Neutral variant | Classifications (e.g. "Binding requirement"): bg `--surface`, border `--rule`, text `--ink-2`, no glyph |

**The code.** The raw enum is never the primary label. It appears in two places:

1. A tooltip (§5.20) in mono: "Escalated to lab supervisor — `ESCALATION_REQUIRED`".
2. Detail views (Trace, Audit expanded row, Case timeline), where it sits after the badge as `--t-mono-sm` `--ink-3`, 6px gap.

Badges are **never interactive** (GOV.UK Tag guidance). The tooltip trigger is the focusable row or the cell around the badge.

**Budget.** At most one badge per table row (the state). Everything else is plain text with glyphs.

**Label map** (in `web/src/labels.ts`; role values interpolate):

| Code | Label | Tone |
|---|---|---|
| `RESULT_DRAFT` | Draft | progress |
| `RESULT_FINALIZED` | Finalised | progress |
| `TRANSMISSION_QUEUED` | Queued to send | progress |
| `TRANSMISSION_ATTEMPTED` | Sending | progress |
| `RETRY_PENDING` | Retry scheduled | progress |
| `TRANSPORT_ACCEPTED` | At the gateway | progress |
| `DELIVERY_CONFIRMED` | Delivered, not acknowledged | progress |
| `AWAITING_ACKNOWLEDGMENT` | Awaiting acknowledgement | progress |
| `CLINICAL_ACKNOWLEDGMENT_CONFIRMED` | Acknowledged | progress |
| `COMMUNICATION_DOCUMENTED` | Documented | ok |
| `CORRECTED_RESULT_ACKNOWLEDGED` | Correction acknowledged | ok |
| `ESCALATION_REQUIRED` | Escalated to {role} | att |
| `ESCALATION_IN_REVIEW` | With {role}, in review | att |
| `CORRECTION_PENDING` | Correction pending | att |
| `CORRECTED_RESULT_FINALIZED` | Correction finalised | att |
| `CORRECTED_RESULT_DELIVERY_PENDING` | Correction not yet delivered | att |
| `DELIVERY_STATE_UNKNOWN` | Delivery unknown | crit |
| `DELIVERY_FAILED` | Delivery failed | crit |
| Gate permitted / refused | Allowed / Refused by gate | progress / crit |
| Transition `APPLIED` / `BLOCKED` | Applied ✓ (code register) / Blocked | — / crit |
| Agent `ANSWERED` / `DISPUTED` | answered (plain caption) / Disputed | — / crit |
| Assurance `UPHELD` / `CORRECTED` / `OBJECTION_REJECTED` | Objection upheld / Corrected by code / Objection rejected | att / att / progress |
| `SUPERVISOR` / `CLINICAL_LEAD` | Lab supervisor / Clinical lead | — |
| `BINDING_REQUIREMENT` | Binding requirement | neutral 500 |
| `OFFICIAL_GUIDANCE` / `INSTITUTIONAL_PROCEDURE` | Official guidance / Institutional procedure | neutral |
| `GLOBAL_COMPARATOR` | Comparator, not binding here | info (dashed border) |
| `PRODUCT_DESIGN_CONTROL` / `RESEARCH_HYPOTHESIS` / `UNRESOLVED` | Design control / Hypothesis / Unresolved | neutral / neutral / att |
| `VERIFIED_AGAINST_SOURCE` | Quote found on source page ✓ | code register |
| `SOURCE_AMBIGUITY` / `SOURCE_CONFLICT` | Sources ambiguous / Sources conflict | att / crit |
| `INSUFFICIENT_EVIDENCE` / `CANDIDATE_POLICY_GAP` | Not enough evidence / Possible policy gap | att / att |
| `IMPLEMENTATION_GAP` / `INTEROPERABILITY_GAP` | Implementation gap / Interoperability gap | neutral |
| `VERIFIED_OFFICIAL` / `ABSENCE_SEARCHED` | Checked against official text ✓ / Searched, nothing found ✓ | code register |
| Event names (`step.completed`, `agent.message`, `state.transition.applied` …) | Step completed, Agent message, Transition applied … | — |
| Configs (`policy_blind`, `resultrelay_council` …) | Policy-blind baseline, ResultRelay + agent council … (from `configuration_label`) | — |

### 5.6 Buttons

| Size | Height | Padding | Type | Icon |
|---|---|---|---|---|
| md (default) | **36** | `0 14px` | `--t-body` 500 | 16, gap 6 |
| sm | **28** | `0 10px` | `--t-small` 500 | 14, gap 6 |
| header | **32** | `0 12px` | `--t-small` 500 | 16 |

| Variant | Rest | Hover | Pressed |
|---|---|---|---|
| Primary | bg `--action`, text white | `--action-hover` | `#122e4d` |
| Secondary | bg `--surface`, 1px `--line-control`, text `--ink` | bg `--surface-2`, border `--ink-3` | bg `--surface-hover` |
| Ghost | transparent, text `--action` | `--action-soft` | |
| Danger | bg `--crit`, text white (7.56) | `#8a1b16` | |

- Radius 4. Transition `background-color, border-color var(--dur-fast) var(--ease-out)`. Never scale.
- Disabled: bg `--surface-2`, border `--rule`, text `--ink-4`, `cursor:not-allowed`. Do not use `opacity`, which pushes text below contrast.
- Busy: the label stays and a 14px spinner replaces the icon. The width is locked with `min-width` measured at first render, so the button doesn't jump.

### 5.7 Input and select

| Part | Spec |
|---|---|
| Control | Height **36** (28 sm), padding `0 12px`, `--t-body`, 1px `--line-control`, radius 4, bg `--surface` |
| States | Hover border `--ink-3`; focus border `--action` + standard ring |
| Select | `appearance:none`, 16px chevron SVG at `inset-inline-end:10px`, padding-inline-end 32 |
| Select width | Sized to its longest option up to the container (`field-sizing: content` where supported; otherwise explicit widths in §7) |
| Option labels | ≤ 48 chars; the scenario title goes in the option, its slug in a line under the select |
| Field | Column, gap 6. Label `--t-small` 500 `--ink-2`; help and error `--t-caption` (error `--crit` with the ▲ glyph) |
| Mobile | `font-size:16px` under 620px (unchanged) |

### 5.8 Glyph set (inline SVG, `currentColor`, 8px for badges and 12px standalone)

| Glyph | 8px viewBox geometry | Tone |
|---|---|---|
| ok | `<circle cx=4 cy=4 r=4/>` | ok |
| progress | ring r 3.25, stroke 1.5, + left half filled (`<path d="M4 .75a3.25 3.25 0 0 0 0 6.5z"/>`) | progress |
| att | `<path d="M4 0 8 4 4 8 0 4z"/>` | att |
| crit | `<path d="M4 .5 7.8 7.5H.2z"/>` | crit |
| info | ring r 3.25, stroke 1.5 | info |
| ai | ring r 3.25, stroke 1.5, dasharray `1.7 1.4` | ai |

The glyph is vertically centred on the x-height: `align-self:center; margin-top:-1px` at 12/16.

### 5.9 Tabs

| Part | Spec |
|---|---|
| Strip | Height **40**, gap 4, 1px `--rule` below |
| Tab | padding `0 12px`, `--t-body` 500 |
| Inactive | `--ink-3`, hover `--ink` |
| Active | `--ink`, with a 2px `--action` indicator at the bottom that **slides** between tabs (§6.5) |
| Count | 6px after the label: height 18, padding `0 6px`, radius 9, bg `--canvas`, `--t-caption` 500 tabular `--ink-3` |
| Accessibility | `role=tablist/tab/tabpanel`, arrow-key roving focus |

### 5.10 Segmented control (filters)

- Outer: height **32**, padding 2, bg `--canvas`, 1px `--rule`, radius 6.
- Segments: height 26, padding `0 10px`, radius 4, `--t-small` 500 `--ink-2`, sentence case ("All · 18", "Possible policy gap").
- Active: bg `--surface`, 1px `--rule`, shadow `0 1px 0 rgba(20,28,36,.06)`, text `--ink`. The active plate slides (§6.5).
- **No navy fill.** Navy is reserved for the one primary action (was `.pill.active {background: var(--blue)}`).

### 5.11 Step rail (Trace and Simulator)

- Track: flex, gap 2. Height **32**.
- Segment: min-width 64 (flex 1 1 64px, max 120), radius 4 (rail ends radius 6).
- Content: "1" in `--t-caption` 600 tabular + 8px outcome glyph + label `--t-caption` (Allowed / Refused / Escalated). Below 72px, hide the label and keep the glyph.

| State | Fill / border | Text |
|---|---|---|
| Released, allowed | bg `--surface`, 1px `--rule` | `--ink-2` |
| Released, refused | bg `--crit-soft`, 1px `--crit-rule` | `--crit` |
| Released, escalated | bg `--att-soft`, 1px `--att-rule` | `--att` |
| Not yet released (Simulator) | bg transparent, 1px **dashed** `--rule-strong` | `--ink-4` |
| Current | + 2px `--action` bar at the bottom (slides, §6.5), label `--ink` 600 | |

This replaces the 6px progress bar: the rail *is* the progress, and it also shows which steps were refused.

### 5.12 Decision-trace record (one step)

- **Step header.** Height 48, padding `0 16px`. "Step 3" `--t-title-3` · time `--t-caption` tabular `--ink-3` · event humanised `--t-body` · on the right, the gate outcome badge (large) and a chevron button 28px (`aria-expanded`). The duplicated "permitted" + `SEND_PRIMARY` + "Hide" trio becomes **one** badge: "Allowed: queue send" (code in tooltip).
- **Body.** Grid `168px minmax(0, 760px)`, column gap 24. Rows are separated by 1px `--rule-2` with 12px padding-block. Labels are `--t-small` 600 `--ink` with a 12/16 `--ink-3` sub-line and a provenance glyph.

| # | Lane | Register | Content |
|---|---|---|---|
| 1 | Evidence · *retrieved by code* | Code | Up to 4 evidence blocks (§5.15) |
| 2 | Proposals · *rule assessors* | Code (deterministic heuristics) | Table-like rows: agent (humanised, 13/20) · proposal (badge-free mono 13) · "confidence 0.50, heuristic" `--t-caption` `--ink-3` |
| 3 | Agent council · *advisory* | AI | Agent cards (§5.14), 2-up at ≥ 1280 content width |
| 4 | Checks · *by code* | Code | Each condition one line: ✓ / ✗ glyph 12 + text 13/20; invariant codes as `--t-mono-sm` `--ink-3` at line end ("INV-8") |
| 5 | **Gate** | Gate | 3px ink bar block: "Gate routed the case to a named role" 14/20 500 + precondition 13/18 `--ink-2` + outcome badge (large) |
| 6 | Transition | Code | `[Acknowledged] → [Escalated to lab supervisor]`: two badges with a 12px SVG arrow (`--ink-4`), 8px gaps, then "Applied ✓" in the code register |
| 7 | Open questions | — | Numbered list 13/20 `--ink-2`, max 3 items, then "3 more in the full trace" link |

- The orchestrator's summary moves *inside* lane 3 as the last card, with the AI register and the title "Orchestrator recommends: escalate to a person". It must never use a filled container.

### 5.13 Agent message card (AI register)

- **Container:** 1px dashed `--ai-line`, radius 6, padding `12px 16px`, bg `--surface`.
- **Head row** (height 24):
  - ◌ glyph 12
  - Role `--t-title-3` ("Adversarial reviewer")
  - "model · advisory" `--t-caption` `--ai`
  - Right side: status as plain `--t-caption` `--ink-3` ("answered"). Only Disputed or Objection get a badge.
- **Answers:** a definition grid, `grid-template-columns: max-content 1fr`, gap `4px 12px`.
  - Key: humanised, `--t-caption` `--ink-3` ("Objection", "Own reading", "Supports analyst").
  - Value: humanised label + `p 0.93` meter (§4.3).
  - The raw `key=value` mono line is removed (fixes the duplication in C21).
- **Rationale:** `--t-body-lg` `--ink`, max 72ch, clamp 4 lines + "Show all". Prefixed by the caption "Model wrote" in `--ai`.
- **Check footer:** a 1px `--rule-2` top rule, then the **code register** line: "✓ Checked by code: contradiction with the record confirmed (upheld)", or "– Free text, cannot be checked by code" in `--ink-3`. Every AI claim ends with what code made of it.

### 5.14 Evidence / quote block (source excerpts)

| Part | Spec |
|---|---|
| Container | No box; `border-inline-start: 2px solid var(--ink-4)`, padding `2px 0 2px 14px` |
| Comparator variant | `2px dashed var(--info-line)` + info badge "Comparator, not binding here" |
| Head line | `--t-small`: ref mono 12 `S1 §11.1.1 · p.40` · classification badge (neutral) · jurisdiction `AE-DU` mono 12 `--ink-3` |
| Quote | `--t-body-lg` 15/24 `--ink`, max 72ch, `dir="auto"`, hanging open quote (`text-indent:-0.42em`) |
| Foot | `--t-caption` `--ink-3`: source title · "✓ Quote found on source page" (code register) |
| Score | Retrieval only: `score 11.10` `--t-caption` tabular, right-aligned, `--ink-3` |

### 5.15 Banner / notice

- Left 3px tone bar (`border-inline-start`), 1px `--rule` on the other sides, radius 4, padding `10px 14px`, `--t-small` `--ink-2`, **max-width 960px**.
- Soft fill only for `crit` and `att`.
- Intro banners are removed from page tops (§7). Their copy moves to the purpose line or to an "About this page" disclosure (`<details>`, summary `--t-small` 500 `--action`).

### 5.16 Provenance tag

- Inline-flex, gap 6. 12px glyph + `--t-caption` label.
- Variants: `ai` ("model · advisory"), `code` ("checked by code" / "check failed"), `gate` ("gate decision", 600 `--ink`).
- Used in trace lanes, audit actor cells, simulator events and toasts.

### 5.17 Empty, loading and error states

- **Empty** (in a panel): padding `40px 16px`, centred, max-width 48ch.
  - 20px Lucide icon `--ink-4`
  - Title `--t-body` 600 (margin-top 8)
  - Body `--t-small` `--ink-3` (margin-top 4)
  - One sm secondary button (margin-top 12)
  - Example: "No cases yet" / "Each simulator run creates one case." / [Open the simulator].
- **Loading:** skeleton rows match the real geometry (44 or 56px rows). Bars are 12px tall, radius 3, `--rule-2`, widths 60 % / 35 %, two bars per two-line row.
  - Shown only after 150ms (no flash).
  - Pulse: `opacity 1 → .55 → 1`, 1400ms ease-in-out, infinite. This is information ("still working"). Under reduced motion it is static.
  - Use `aria-busy="true"` on the region.
- **Error:** a `crit` banner. Title `--t-body` 600 `--crit` ("Could not load cases"), body `--t-small` with the error message in mono 12, then a "Try again" sm secondary button. Never a raw stack trace in the primary line.

### 5.18 Toast

- Bottom-end, inset 24.
- Width 360, padding `12px 16px`, radius 6, bg `--ink`.
- Text white `--t-body`; secondary `#aab3bd` `--t-small`.
- A 3px tone bar at inline-start, plus the provenance glyph.
- Stacks up to 3, gap 8, newest at the bottom.
- `role="status"` (`role="alert"` for crit).
- Auto-dismiss after 6s for progress and ok. **No auto-dismiss for att and crit**: they need a person, so they stay until closed or until the case opens.
- Enter: opacity 0 → 1, y 8 → 0, 200ms `--ease-out`. Exit: opacity → 0, 140ms.
- Copy pattern: "SYN-CASE-011 escalated to lab supervisor · Gate decision · [Open trace]".

### 5.19 Tooltip

- Bg `--ink`, text white `--t-caption` 400, padding `6px 8px`, radius 4, max-width 280. Codes in `--t-mono-sm` `#aab3bd`.
- Offset 6, no arrow.
- Open after 400ms hover or immediately on keyboard focus. Close after 0ms. Fade 100ms.
- `role="tooltip"` + `aria-describedby`.
- Never the only place a fact lives: the code also appears in detail views.

---

## 6. Motion

**Dependency:** `motion` (npm, the framer-motion successor; `import { motion, AnimatePresence, animate, useReducedMotion } from "motion/react"`). Wrap the app in `<MotionConfig reducedMotion="user">`, which disables transform and layout animation for users with OS reduced motion while still allowing opacity and colour. Pure-CSS pieces also honour `@media (prefers-reduced-motion: reduce)`.

**Motion tokens.**

| Token | Value |
|---|---|
| `--dur-instant` | 80ms |
| `--dur-fast` | 140ms |
| `--dur-base` | 220ms |
| `--dur-slow` | 360ms |
| `--dur-travel` | 360ms per chain hop, clamped to 360–1080ms |
| `--ease-out` | `cubic-bezier(0.2, 0, 0, 1)` |
| `--ease-in-out` (travel) | `cubic-bezier(0.65, 0, 0.35, 1)` |
| `--ease-expo` | `cubic-bezier(0.16, 1, 0.3, 1)` (Magic UI's beam easing) |

**Rules.**

1. Nothing animates on page mount. Pages render final values immediately, so screenshots, screen readers and time-poor judges see the answer at once. Motion plays only on a **change**: a step released, a case moved, a count changed, a chain verified.
2. At most one infinite animation ever runs, and it stops after 5s (WCAG 2.2.2).
3. Animate only `transform`, `opacity`, `stroke-dashoffset`, `offset-distance` and `background-color`.

### 6.1 Number ticker (Magic UI `number-ticker`)

- **Purpose:** show that a count *changed* and in which direction (chain counts, exit counts, sidebar badge, KPI strip, "Verified 23 of 57").
- **Magic UI original:** a `useSpring` (damping 60, stiffness 100) from `startValue` to `value`, triggered on `useInView`, writing `textContent` through `Intl.NumberFormat`.
- **Port:** trigger on **value change only**, not on view.
  - For |Δ| ≤ 3 (the common case), do a **digit roll**: the old number moves y 0 → −0.6em with opacity 1 → 0; the new one moves +0.6em → 0 with opacity 0 → 1. 260ms `--ease-out`.
  - For |Δ| > 3, count with `animate(from, to, { duration: 0.48, ease: [0.16,1,0.3,1] })`.
  - A delta tag ("+1" / "−1", §5.4) fades in over 140ms, holds 1600ms and fades out over 240ms.
- **Accessibility:** the visual span is `aria-hidden`. A sibling `.sr-only` holds the final value. A single polite live region per page announces the *event*, not the digits ("SYN-CASE-011 moved from Delivered to With a named person, lab supervisor").
- **Reduced motion:** the value swaps instantly. The cell's background flashes `--action-soft` → transparent over 600ms (colour only), and the delta tag still shows.

```tsx
// web/src/motion/NumberTicker.tsx
export function NumberTicker({ value }: { value: number }) {
  const prev = useRef(value); const reduce = useReducedMotion();
  const [pair, setPair] = useState<{ from: number; to: number; k: number }>({ from: value, to: value, k: 0 });
  useEffect(() => { if (prev.current !== value) { setPair(p => ({ from: prev.current, to: value, k: p.k + 1 })); prev.current = value; } }, [value]);
  const up = pair.to > pair.from;
  return (
    <span className="ticker" data-flash={reduce && pair.k ? pair.k : undefined}>
      <span className="sr-only">{value}</span>
      <span aria-hidden className="ticker-window">           {/* overflow:hidden; display:inline-grid */}
        <AnimatePresence initial={false} mode="popLayout">
          <motion.span key={pair.k} className="ticker-digit"
            initial={{ y: up ? "0.6em" : "-0.6em", opacity: 0 }} animate={{ y: 0, opacity: 1 }}
            exit={{ y: up ? "-0.6em" : "0.6em", opacity: 0 }} transition={{ duration: 0.26, ease: [0.2, 0, 0, 1] }}>
            {pair.to}
          </motion.span>
        </AnimatePresence>
      </span>
    </span>
  );
}
```

### 6.2 Chain beam (Magic UI `animated-beam`)

- **Purpose:** show a case moving along the chain (stage i → i+1) or **leaving the chain to a person** (stage → Needs-a-person row → named role). This is the motion signature of the product.
- **Magic UI original:** a quadratic path between two refs (`M sx,sy Q midX,sy−curvature ex,ey`) with an animated `linearGradient` x1/x2 sweep. Defaults: `duration 5`, `pathWidth 2`, `pathOpacity .2`, `ease [0.16,1,0.3,1]`, `repeat Infinity`.
- **Port changes:**
  1. It runs **once per event, never repeats**.
  2. The path is **orthogonal with 8px radius corners**, because the chain is a rail and an elbow reads as "branch".
  3. A head dot travels the path with CSS `offset-path`. This replaces the gradient sweep, which reads as decoration.
- **Geometry** (measured with refs + `ResizeObserver` on an absolutely positioned `<svg>` overlay covering the chain band, `pointer-events:none`):
  - In-chain: `M xi,23 H xj`.
  - Exit: `M xi,23 V (bandBottom−10) H (chainRight+12) V yRow H xGlyph`, with corners as `a8,8` arcs.
  - Escalation to a role (Simulator): from the exit pill to the "Owner now" card (§7.3), same elbow form.
- **Timeline** (one event):

| Time | Effect |
|---|---|
| t = 0 | The source node gets a ring pulse (3px ring in the tone, opacity .6 → 0, 360ms). The source count ticks −1 |
| 0 → T | The path fades to `opacity .5` (`--rule-strong`, 2px) over 120ms. A 6px head dot in the destination tone's solid colour moves `offset-distance 0% → 100%` over T = clamp(360ms × hops, 360, 1080), `--ease-in-out`. A 24px trailing dash (`stroke-dasharray 24 1000`, `pathLength=1000`, same tone at .45) follows the dot |
| T | The destination node or row gets a ring pulse (scale 1 → 1.8, opacity .5 → 0, 480ms `--ease-out`). The destination count ticks +1. The path fades out over 240ms |

- **Concurrency:** at most 3 beams at once, 120ms stagger. If more than 3 events are queued, skip the travel and only tick the counts (never build a backlog).
- **Reduced motion:** no path and no dot. The source and destination nodes change colour, and the destination gets a 2px tone outline that fades over 1200ms (opacity only). Counts swap.

```css
.beam-head { offset-path: path(var(--beam-d)); offset-rotate: 0deg; width: 6px; height: 6px; border-radius: 50%;
  background: var(--beam-c); animation: beam-travel var(--beam-t) var(--ease-in-out) forwards; }
@keyframes beam-travel { from { offset-distance: 0% } to { offset-distance: 100% } }
.beam-trail { fill: none; stroke: var(--beam-c); stroke-width: 2; stroke-linecap: round; opacity: .45;
  stroke-dasharray: 24 1000; stroke-dashoffset: 24; animation: beam-trail var(--beam-t) var(--ease-in-out) forwards; }
@keyframes beam-trail { to { stroke-dashoffset: -1000 } }   /* <path pathLength="1000"> */
```

`--beam-d` is set as an inline style string on the element (`style={{ "--beam-d": \`"${d}"\` }}`). If browser support for `offset-path: path(var())` is a concern, set `offsetPath` directly in the style object.

### 6.3 Live list (Magic UI `animated-list`)

- **Purpose:** new audit entries (Console rail) and newly released events (Simulator) appear at the top, so the eye catches *what just happened*.
- **Magic UI original:** items spring in from `scale 0` / `opacity 0`, with one item revealed per `delay` (1000ms default), inside `AnimatePresence`.
- **Port:** no scale (it blurs text and reads as decoration). Use `motion.li` with `layout="position"`, `initial {opacity:0, y:-6}`, `animate {opacity:1, y:0}`, 220ms `--ease-out`, `exit {opacity:0}` 140ms, wrapped in `AnimatePresence initial={false}`. A new item also gets `.is-new`: a background `--action-soft` → transparent fade over 1600ms plus a 2px inline-start bar in its tone for the same 1600ms. That bar tells you which rows are new.
- **Cadence:** Simulator "Run to end" releases one event every **900ms**, so each step is readable on video; the step rail fills in sync. The list is capped at 8 visible items in the rail, and older items exit.
- **Reduced motion:** no y or layout movement. The `.is-new` highlight stays (colour only).

### 6.4 Attention beam (Magic UI `border-beam`)

- **Purpose:** mark **the one** item that needs a person now (the oldest unowned escalation, or the case in the Simulator when the gate escalates). At most one per screen.
- **Magic UI original:** a `motion.div` beam on `offsetPath: rect(...)` with a masked border. Defaults: `size 50`, `duration 6`, `colorFrom #ffaa40`, `colorTo #9c40ff`, infinite linear.
- **Port:** pure SVG + CSS, with no gradient colours. An absolutely positioned `<svg>` covers the item (`inset:-1px`). A `<rect>` uses `rx` = the item radius and `pathLength="100"`, and its width and height are set from `ResizeObserver`. Stroke `--att-solid`, width 1.5, `stroke-dasharray: 14 86`, animated `stroke-dashoffset 0 → −100` over **2400ms linear, 2 iterations** (4.8s, under the 5s limit in WCAG 2.2.2).
- **Settle:** afterwards, the static 1px `--att-rule` border becomes `box-shadow: inset 0 0 0 1px var(--att-solid)` plus a 3px inline-start `--att-solid` bar. It re-runs only when a *new* item becomes the top item. It stops (fade 240ms) when the item is opened, and pauses on `visibilitychange`.
- **Reduced motion:** no loop; the static settled outline only.

```css
.attn-beam rect { fill: none; stroke: var(--att-solid); stroke-width: 1.5; stroke-dasharray: 14 86;
  animation: attn 2400ms linear 2 forwards; }
@keyframes attn { from { stroke-dashoffset: 0 } to { stroke-dashoffset: -100 } }
@media (prefers-reduced-motion: reduce) { .attn-beam { display: none } }
```

### 6.5 Sliding indicator (shadcn / Origin UI animated tabs, via Motion `layoutId`)

- **Purpose:** show *where you moved to* in tabs, the segmented filter and the step rail (current step).
- **Port:** one `motion.span` with `layoutId="tabs-indicator"` (a unique id per control instance) rendered inside the active item. Transition `{ type: "spring", stiffness: 520, damping: 42 }` (about 180ms, no overshoot).
- **Reduced motion:** `MotionConfig` makes it instant.

### 6.6 Verification sweep (Audit; custom, Magic UI list-stagger idiom)

- **Purpose:** show that verification is **recomputed row by row**, and *where* a break is.
- **Behaviour:** after "Verify the chain" (or on load *only after* the server returns a verdict), each row's Seq cell draws a 12px ✓. The check path has `stroke-dasharray 12`, dashoffset 12 → 0 over 160ms, staggered `min(24ms, 1200ms / n)`.
  - The header counter "Verified 23 of 57" ticks in step (§6.1).
  - At a break (row k): the sweep stops, row k gets a ✗ and a 3px `--crit-solid` bar, and later rows dim to `--ink-4` with "not verifiable after a break".
  - The total sweep is capped at 1.2s.
- **Reduced motion:** the final state is drawn immediately.

### 6.7 Rejected (would be decoration)

| Rejected | Reason |
|---|---|
| Blur fade on mount | Delays the answer; removed in v3 for good reason |
| Shine border, meteors, particles, retro grid, dot pattern, aurora or sparkles text, marquee, globe, confetti on "Documented" | Pure decoration; confetti would trivialise a clinical event |
| Typing animation on agent text | It implies live generation, but answers are replayed from `evaluation/agent_runs/`. That would be a false signal |
| three.js pipeline | It was navigation dressed as atmosphere in v2. The 2-D chain does the same job at 156px |

---

## 7. Page-by-page adjustments

### 7.1 Shell (all pages)

| Change | Values |
|---|---|
| Sidebar | 236 → **224**; padding `20px 14px 16px` → `12px 12px 16px`; group gap 22 → per-label `16px` top |
| Nav item | `7px 10px`, 14/21 400 → height **32**, `0 8px`, 14/20 **500**, 16px icon, gap 10 |
| Active nav marker | `left:-14px` bar → inset 2×16 bar at `inset-inline-start:0; top:8px`; no weight change |
| Sidebar footer | Paragraph + 3 status rows (190px) → 2 caption lines + density toggle (≤ 72px) |
| Topbar | `22px 32px 18px`, `align-items:flex-end` → `16px 32px 15px`, grid `1fr auto`, `align-items:start`; h1 22 → **24/32**; total 98 → **88** |
| Data flag | Bordered box, bottom-aligned → 24px pill, `margin-top:4`, `--canvas` fill, no border, info dot |
| Content | `max-width:1480` → **1600**; padding `24px 32px 64px` (unchanged) |
| Global | Replace all 12.5 / 13.5 / 14.5px sizes with the scale in §2.2; replace the 148 inline styles with utility classes (`.stack-4`, `.gap-8`, `.mt-4` …) and component classes; delete `#fbfcfd`, `#f8f9fa` and `opacity:.85` literals |

### 7.2 Console `/`

1. Chain band per §5.3: chain panel (main) + Needs-a-person panel (rail), height 156 both, 24px gap below. Remove `.chain-stage::before` chevrons and the `.final` tint.
2. Remove "Run a scenario" from the Cases panel head and put it in the page header (button 32px).
3. Cases table:

| Column | Width (film / 1440) | Content |
|---|---|---|
| Case | 168 / 152 | `SYN-CASE-011` mono 13/20; second line `run 70bef0` mono 12/16 `--ink-3` (fixes the duplicate-looking rows) |
| Scenario | auto (328 / 272) | Humanised title 14/20 ("Escalation nobody answers"), clamp 1; second line config label 12/16 `--ink-3` ("ResultRelay + agent council") |
| State | 248 / 216 | One humanised badge + second line 12/16 `--ink-3` ("since 15:45" or owner) |
| Acknowledgement | 152 / 136 | Text, no chip: "✓ Current revision" (code glyph) · "▲ Earlier revision" (`--crit`) · "—" `--ink-4` |
| › | 32 | Always-visible chevron 16px `--ink-4` → `--action` on row hover/focus (fixes C18) |

   - Two-line rows are **56px**. At film the table starts at y 372 and shows 9 rows (was 6.5).
   - Sort: needs-a-person states first, then by time desc. The top row gets the attention beam (§6.4) once.
4. Right rail under the Needs-a-person panel: **Audit activity** as a live list.
   - Item: line 1 time 12/16 tabular `--ink-3` + event humanised 13/18 500. Line 2 summary 13/18 `--ink-2`, clamp 2, enum codes humanised.
   - Hash only on hover/focus as a tooltip.
   - Padding 10 16, rule-2 between. Max 8 items. Head action "Verify chain" ghost sm.
5. **Evidence base** becomes a 3-row kv strip at the bottom of the rail (dt 13/18 `--ink-3` one line: "Excerpts verified", "Retrieval", "Live network"; dd 13/18 tabular, "96 of 96" in sans, not mono).
6. "What this console does not do" becomes a 3-column footnote strip below the table: no panel border, 1px `--rule` top, padding-top 12, title 13/18 600, body 12/16 `--ink-3`, height ≤ 72.

### 7.3 Simulator `/simulator`

1. Remove the intro banner. Its copy goes to the purpose line: "Release a scenario's events one at a time and watch what the gate decides."
2. Run toolbar (one row, panel body 16, `align-items:end`, gap 12):
   - Scenario select `flex: 1 1 440px`, min 360, options showing the **title**.
   - Configuration select `0 0 320px`, options = `configuration_label` ≤ 40 chars.
   - "Start run" primary 36.
   - Below: scenario summary `--t-body` `--ink-2` max 80ch, clamp 2; then the config description `--t-caption` `--ink-3`. The `WALK_IN` chip becomes the text "Walk-in" inside that caption.
3. Case panel head: "Case SYN-CASE-011" (mono id) + config label as hint. Actions: Step (sm secondary), Run to end (sm secondary), Export bundle (sm ghost).
4. Case panel body, top to bottom:
   - (a) **Large state badge** + state description 14/20 `--ink-2`.
   - (b) **Compact chain** 64px (§5.3) with an exit branch.
   - (c) **Step rail** (§5.11) replacing the 6px bar, with "5 of 6 events released" `--t-caption` `--ink-3` at its right end. "run complete" becomes neutral text "Run complete".
   - (d) Fact strip, 4 columns, each label 12/16 `--ink-3` + value 14/20:
     - Revision (mono)
     - Delivery ("0 of 1 attempts delivered")
     - Acknowledgement ("None")
     - Audit chain ("✓ Valid · 57 entries", code register)
5. **"Owner now" card** at the top of the right rail, when escalations exist. A panel with the att settled outline. Title "Needs a person" 12/16 600 `--att`. Escalation path as role chips connected by a 2px elbow: "Lab supervisor → Clinical lead" (`--t-title-3`), each with "since 15:45" and its status. The chain beam (§6.2) runs from the exit pill to this card when the escalation happens. Fixes C22.
6. Channel status (rail, under Owner now):
   - Rows 44px: channel humanised ("Patient SMS", primary) 14/20 + kind 12/16 `--ink-3`.
   - Status as glyph + text: "▲ Down, simulated gateway outage" `--crit` 13/18, or "Up" `--ink-3`.
   - The panel hugs its content. Below it, the rail continues with "This run's audit" as a live list, so no dead space (fixes C23).
7. Open questions get their own panel below the case panel, full main width: numbered list 14/20 max 80ch, each item prefixed "Step 4" `--t-caption` `--ink-3`.
8. Released events: live list (§6.3).
   - Row head 44: `01` mono 12 `--ink-3` width 24 · event humanised 14/20 · right: time 12/16 tabular `--ink-3` · gate outcome glyph + label · chevron.
   - Expanded body uses the trace lanes (§5.12) in compact form. The gate banner becomes the gate register (ink bar, not a green or red banner). "refs:" and "checked:" become code-register lines.
   - Agent cards inside use the AI register. Remove `background:#fbfcfd`.

### 7.4 Side-by-side `/compare`

1. Toolbar: three selects at 36px (scenario `1 1 360px`, configurations `0 0 280px` each) + "vs" `--t-small` `--ink-3` + "Run both" **primary**.
2. Under the toolbar, **two compact chains stacked** (each 64px, labelled on the left: config label 14/20 600 in a 200px column). "Run both" replays both with beams on the same clock, so the divergence is visible as the two dots part ways.
3. Headline row: two final-state badges (large) with a `--t-title-2` sentence between them: "Different final state". The diverging side has the attention outline.
4. Step comparison table, full width:

| Step 56 | Event auto | {Config A} 280 | {Config B} 280 |
|---|---|---|---|

   - Cells contain a humanised badge + "gate refused (INV-9)" caption where relevant.
   - Rows where A ≠ B get bg `--att-soft` and a "Differs" `--t-caption` 600 `--att` under the step number.
   - Rows are 52px.
   - Footer row "Citations used" and "Gate refusals" as 13/18 text, mono only for refs.
5. Target: content reaches ≥ 760 of 900px at film (was 510 of 1080 screen px, about 425 CSS).

### 7.5 Decision trace `/trace`

1. Remove the intro banner. Its copy goes to the purpose line plus an "About this page" disclosure.
2. Panel head: "Run" select width `min(560px, 100%)` showing `configuration_label · scenario title`. The meta row ("Configuration / Case / Corpus") becomes a kv strip with mono values and `--t-caption` labels.
3. Compact chain (64px) for the selected run above the step rail. Clicking a node jumps to the first step that reached it.
4. Step rail per §5.11 (was a bordered pill group with navy fill).
5. Step record per §5.12:
   - Label column 170 → **168**; content max-width **760**.
   - Lane order: Evidence → Proposals → Agent council → Checks → **Gate** → Transition → Open questions.
   - The gate outcome sits in the step header (one badge).
   - The orchestrator box loses its amber fill (C21).
6. Spacing: step cards 16px apart; card padding `0 16px 16px`; lane rows padding-block 12.

### 7.6 Standards and gaps `/standards`

1. Remove the intro banner. Purpose line: "The clauses the system cites, and where the rules say nothing. Comparators are never shown as binding." Link `manifest.json` in the disclosure.
2. Tabs per §5.9 (40px).
3. Retrieval:
   - Query (flex 1, `dir="auto"`, Arabic in Plex Sans Arabic) · Jurisdiction select 300 · Search primary 36.
   - The filter becomes the neutral segmented control (§5.10).
   - Stats become one line of text, 13/18 `--ink-2` tabular: "8 results · 51 considered · 45 excluded by the applicability filter".
   - The two amber banners merge into **one** 36px att notice: "Keyword search only (BM25): the hybrid index is unavailable."
4. Result cards: evidence-block style (§5.14) inside a 1px `--rule` card, radius 6, padding 16, 12px apart; ref line in mono 12; score right. Remove `VERIFIED_AGAINST_SOURCE` chips in favour of the code-register foot.
5. Gap register table:

| ID 72 | Question auto (min 320) | Class 196 | Stage 152 | Jurisdictions 184 | Verification 208 | Confidence 96 |
|---|---|---|---|---|---|---|

   - ID mono 13 `white-space:nowrap` (fixes the `GR-`/`01` wrap).
   - Question 14/20, clamp 3.
   - Class: humanised badge (the only badge in the row).
   - Stage: sans 13/18 sentence case ("Communication completion").
   - Jurisdictions: sans with codes inline mono 12 ("AE-DU vs AE-AZ").
   - Verification: code register text ("✓ Checked against official text").
   - Confidence: author rating as text `--ink-2`, with header "Confidence (author)".
   - Rows padding-block 12.
6. Gap-register intro: a 13/18 `--ink-3` line under the filter (max 96ch), not a banner.

### 7.7 Evaluation `/evaluation`

1. Keep the caveat banner (it matters to judges) but set `max-width: 960px`, `--t-small`, att tone, no soft fill (it is a scope statement, not a warning). Its bold lead stays.
2. A KPI strip under it, 4 × metric (§5.4, figure 32/36, tickers on re-run):
   - "ResultRelay safe scenarios 11 of 12"
   - "Best baseline 4 of 12"
   - "False closures (all configs) 0"
   - "Runs 144 · finished 20:49"
3. Matrix table:

| Configuration auto (min 280) | Safe 120 | Assertions 104 | False closure 88 | Stale ack 80 | Unauth. channel 96 | Scope violations 96 | Comparator as binding 112 | Send provenance 96 | Replay 88 |
|---|---|---|---|---|---|---|---|---|---|

   - All headers sans 12/16 500 `--ink-2`, **one line**, right-aligned for numbers, full text in tooltips (fixes the mono, two-line 62px header). Header row 36.
   - Configuration: humanised label 14/20 + id mono 12/16 `--ink-3`.
   - Safe: "11/12" 14/20 tabular + a 48×6 bar (track `--rule-2`, fill `--ink-2`, ResultRelay row fill `--ok-solid`), no chip.
   - Assertions: "53/53" + "100 %" 12/16 `--ink-3` on the same line.
   - Failure counts: 0 → `--ink-4` 400; > 0 → `--crit` 500. Send provenance "1.00" `--ink-2`; "0.00" `--crit` 500.
   - Replay: "Stable" `--t-caption` `--ink-3`; only "Unstable" is a crit badge.
   - The ResultRelay row gets a 2px `--action` inline-start bar and the caption "this system".
   - Rows are 52px.

### 7.8 Audit trail `/audit`

1. Remove the intro banner. Its copy goes to the disclosure.
2. Verdict block at the top of the panel body, height 56:
   - 16px code glyph + "Chain verified: 57 of 57 entries recomputed from stored rows" `--t-title-3`.
   - Right: `RUN-70bef00a40` mono 12 `--ink-3`.
   - On failure: crit register, "Chain broken at entry 23", with the break row scrolled into view.
   - The verification sweep (§6.6) drives it.
3. Toolbar (panel head): case select 360 + "Export bundle" sm secondary.
4. Table:

| Seq 56 → | At 80 | Event 184 | Actor 184 | Summary auto | Prev 112 | Hash 112 |
|---|---|---|---|---|---|---|

   - Seq tabular, right-aligned, plus the sweep ✓.
   - At: sans tabular.
   - Event: humanised 13/18 (code in tooltip).
   - Actor: provenance tag + humanised name ("◌ Policy analyst", "▣ Gate", "Lab", "Orchestrator").
   - Summary: **one sentence**, clamp 2. JSON payloads render only in an expanded row as a kv grid (key `--t-caption` `--ink-3`, value 13/18). Fixes C25.
   - Prev mono 12 `--ink-4`; Hash mono 12 `--ink-2`.
   - Rows 44 single-line, 56 when clamped to 2.

### 7.9 Case timeline `/cases`

1. Cases table: reduce from 8 columns to 6:

| Case 168 | Scenario auto | State 248 | Revision 120 (mono) | Acknowledgement 152 | Escalations 104 (num) |
|---|---|---|---|---|---|

   Delivery moves to the State second line ("0 of 1 delivered").
2. Detail header: compact chain 64 + large badge + "Owner now" line, as in the Simulator.
3. Event, transition and evidence tables follow §3.4. "From → To" becomes two badges with an SVG arrow. Layer and kind are humanised, with codes in tooltips. Page and step numbers are sans tabular, right-aligned.
4. The PillGroup becomes the segmented control. Tabs per §5.9.

---

## 8. Tokens: copy-paste block

```css
/* ResultRelay visual system v4: tokens. Replaces :root in web/src/index.css. */

@font-face { font-family: "Plex Sans"; src: url("/fonts/plex-sans-400.woff2") format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "Plex Sans"; src: url("/fonts/plex-sans-500.woff2") format("woff2"); font-weight: 500; font-display: swap; }
@font-face { font-family: "Plex Sans"; src: url("/fonts/plex-sans-600.woff2") format("woff2"); font-weight: 600 700; font-display: swap; }
@font-face { font-family: "Plex Sans"; src: url("/fonts/plex-sans-arabic-400.woff2") format("woff2"); font-weight: 400; font-display: swap;
  unicode-range: U+0600-06FF, U+0750-077F, U+0870-08FF, U+FB50-FDFF, U+FE70-FEFF, U+200C-200F; }
@font-face { font-family: "Plex Sans"; src: url("/fonts/plex-sans-arabic-500.woff2") format("woff2"); font-weight: 500; font-display: swap;
  unicode-range: U+0600-06FF, U+0750-077F, U+0870-08FF, U+FB50-FDFF, U+FE70-FEFF, U+200C-200F; }
@font-face { font-family: "Plex Sans"; src: url("/fonts/plex-sans-arabic-600.woff2") format("woff2"); font-weight: 600 700; font-display: swap;
  unicode-range: U+0600-06FF, U+0750-077F, U+0870-08FF, U+FB50-FDFF, U+FE70-FEFF, U+200C-200F; }
@font-face { font-family: "Plex Mono"; src: url("/fonts/plex-mono-400.woff2") format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "Plex Mono"; src: url("/fonts/plex-mono-500.woff2") format("woff2"); font-weight: 500 700; font-display: swap; }

:root {
  /* faces */
  --sans: "Plex Sans", "Segoe UI", system-ui, -apple-system, Roboto, "Noto Sans Arabic", Arial, sans-serif;
  --mono: "Plex Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;

  /* type scale: size / line-height / weight / tracking */
  --t-display-size: 40px;  --t-display-lh: 44px;  --t-display-wt: 600; --t-display-tr: -0.022em;
  --t-figure-size: 32px;   --t-figure-lh: 36px;   --t-figure-wt: 600;  --t-figure-tr: -0.02em;
  --t-figure-sm-size: 20px;--t-figure-sm-lh: 24px;--t-figure-sm-wt: 600;--t-figure-sm-tr: -0.01em;
  --t-title-1-size: 24px;  --t-title-1-lh: 32px;  --t-title-1-tr: -0.014em;
  --t-title-2-size: 18px;  --t-title-2-lh: 24px;  --t-title-2-tr: -0.008em;
  --t-title-3-size: 15px;  --t-title-3-lh: 20px;  --t-title-3-tr: -0.004em;
  --t-body-lg-size: 15px;  --t-body-lg-lh: 24px;
  --t-body-size: 14px;     --t-body-lh: 20px;
  --t-small-size: 13px;    --t-small-lh: 18px;
  --t-caption-size: 12px;  --t-caption-lh: 16px;  --t-caption-tr: 0.01em;
  --t-mono-size: 13px;     --t-mono-lh: 20px;
  --t-mono-sm-size: 12px;  --t-mono-sm-lh: 16px;
  --measure-prose: 72ch;   --measure-ui: 90ch;    --measure-notice: 960px;

  /* neutrals (contrast vs #fff / canvas) */
  --ink: #141c24;          /* 17.19 / 15.76 */
  --ink-2: #3b4754;        /*  9.48 /  8.69 */
  --ink-3: #5b6572;        /*  5.92 /  5.42 */
  --ink-4: #7d8794;        /*  3.64 /  3.34  large text + non-text only */
  --line-control: #7d8794; /*  3.64 /  3.34  WCAG 1.4.11 */
  --rule-strong: #c4cbd3;
  --rule: #dde1e6;
  --rule-2: #eceef1;
  --canvas: #f4f5f7;
  --surface: #ffffff;
  --surface-2: #f8f9fa;
  --surface-hover: #f1f3f5;

  /* action */
  --action: #1f4a7a;       /*  9.06 on white; white on it 9.06 */
  --action-hover: #173a61;
  --action-press: #122e4d;
  --action-soft: #edf2f8;
  --focus: #1f4a7a;
  --selection: #cfe0f3;

  /* case-state tones: text / soft / rule / solid */
  --ok: #1a6b43;   --ok-soft: #edf6f0;   --ok-rule: #b5d8c3;   --ok-solid: #2a8a5a;    /* documented */
  --prog: #3b4754; --prog-soft: #f1f3f5; --prog-rule: #d3d8de; --prog-solid: #5b6572;  /* in progress */
  --att: #8a4b00;  --att-soft: #fdf4e7;  --att-rule: #ecd0a5;  --att-solid: #a8650a;   /* needs a person */
  --crit: #a3201a; --crit-soft: #fcefee; --crit-rule: #ecc3c0; --crit-solid: #c4312a;  /* refused / broken */
  --crit-press: #8a1b16;
  --info: #0f5e66; --info-soft: #eaf5f6; --info-rule: #b7dade; --info-solid: #3f8f99; --info-line: #3f8f99; /* comparator */
  --ai: #5d3fa0;   --ai-soft: #f5f2fb;   --ai-rule: #d8cdef;   --ai-line: #9179cc;     /* AI said (advisory) */

  /* overlays */
  --overlay-bg: #141c24;  --overlay-fg: #ffffff;  --overlay-fg-2: #aab3bd;

  /* spacing (4px base) */
  --s-1: 2px; --s-2: 4px; --s-3: 6px; --s-4: 8px; --s-5: 12px; --s-6: 16px;
  --s-7: 20px; --s-8: 24px; --s-9: 32px; --s-10: 40px; --s-11: 48px; --s-12: 64px;

  /* layout */
  --sidebar-w: 224px;
  --header-h: 88px;
  --page-pad-x: 32px;
  --page-pad-top: 24px;
  --content-max: 1600px;
  --gutter: 24px;
  --stack: 16px;
  --band: 24px;
  --rail-w: 320px;

  /* components */
  --r-panel: 6px; --r-control: 4px; --r-badge: 4px; --r-pill: 999px;
  --panel-head-h: 44px; --panel-pad: 16px;
  --ctl-h: 36px; --ctl-h-sm: 28px; --ctl-h-header: 32px; --seg-h: 32px; --tab-h: 40px;
  --badge-h: 20px; --badge-h-lg: 24px;
  --row-h: 44px; --row-h-2: 56px; --th-h: 36px; --cell-px: 12px; --cell-px-edge: 16px;
  --chain-h: 156px; --chain-compact-h: 64px; --node: 12px; --track: 2px;
  --trace-label-w: 168px; --trace-content-max: 760px;

  /* motion */
  --dur-instant: 80ms; --dur-fast: 140ms; --dur-base: 220ms; --dur-slow: 360ms;
  --dur-hop: 360ms; --dur-hop-max: 1080ms; --dur-new: 1600ms;
  --ease-out: cubic-bezier(0.2, 0, 0, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --ease-expo: cubic-bezier(0.16, 1, 0.3, 1);
}

@media (min-width: 1500px) { :root { --rail-w: 360px; } }
@media (min-width: 1800px) { :root { --rail-w: 400px; } }
@media (max-width: 1279px) { :root { --page-pad-x: 24px; } }
@media (max-width: 1023px) { :root { --page-pad-x: 16px; } }

[data-density="compact"] {
  --row-h: 36px; --row-h-2: 48px; --th-h: 32px; --cell-px: 10px;
  --panel-pad: 12px; --t-figure-size: 28px; --t-figure-lh: 32px;
}

body { font: 400 var(--t-body-size)/var(--t-body-lh) var(--sans); color: var(--ink); background: var(--canvas);
  -webkit-font-smoothing: antialiased; font-synthesis: none; }
::selection { background: var(--selection); color: var(--ink); }
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
:lang(ar), [dir="rtl"] { font-size: 1.0714em; line-height: 1.6; }
.mono, code { font-family: var(--mono); font-size: var(--t-mono-size); line-height: var(--t-mono-lh); }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 1ms !important; animation-iteration-count: 1 !important;
    transition-duration: 1ms !important; scroll-behavior: auto !important; }
}
```

---

## 9. Implementation order (smallest change for the largest visible gain on film)

1. Fonts re-subset (C1, C2, C5) and token block (§8). Delete the legacy aliases once `grep -rn "var(--accent\|var(--bad\b" src` is empty.
2. `labels.ts` + the `Badge`, `Provenance` and glyph components (C6–C10). This changes every page.
3. Shell and header (C11, C15), panel and table alignment (C12, C16–C18), control heights (C20).
4. Chain band + Needs-a-person panel (C13, C14), then the Trace lanes (C21).
5. Motion: ticker → beam → live list → attention beam → sliding indicator → verification sweep. Install with `npm i motion` (approx. 30 kB gzip if you import only `motion`, `AnimatePresence`, `animate` and `useReducedMotion`; measure with `vite build`).
6. Simulator, Compare, Audit and Evaluation page passes (§7).
7. Extend `scripts/check_contrast.py` with the 40 pairs in §4.1–4.2, and add a test that asserts U+2192 is present in every shipped woff2.

---

## Sources

- Magic UI components and source (props and defaults quoted above): magicui.design/docs/components/number-ticker, /animated-beam, /border-beam, /animated-list; github.com/magicuidesign/magicui `apps/www/registry/magicui/*.tsx` (AnimatedBeam defaults `duration 5, pathWidth 2, pathOpacity .2, ease [0.16,1,0.3,1]`; NumberTicker spring `damping 60, stiffness 100`; BorderBeam `size 50, duration 6`; AnimatedList `delay 1000`).
- Motion (framer-motion successor), reduced motion: motion.dev/docs/react-accessibility (`MotionConfig reducedMotion="user"`, `useReducedMotion`).
- GOV.UK Design System, Tag: design-system.service.gov.uk/components/tag/ (sentence case since Frontend v5.0.0; tags not interactive; colour not the only signal).
- WCAG 2.2: SC 1.4.1 Use of Colour, 1.4.3 Contrast (Minimum), 1.4.11 Non-text Contrast, 2.2.2 Pause, Stop, Hide, 2.3.3 Animation from Interactions (w3.org/TR/WCAG22/).
- IBM Plex (Sans, Mono, Sans Arabic), SIL OFL 1.1: github.com/IBM/plex.
- Lucide icons, ISC licence: lucide.dev.
- Glyph coverage, GSUB features and metrics of the shipped fonts: measured locally with fontTools 4.68 on `web/public/fonts/*.woff2` (232 / 229 glyphs; U+2192 absent; GSUB `ccmp dnom frac liga numr`; x-height 516, cap 698, UPM 1000; Sans digits 600 units).
- Contrast ratios: computed with the WCAG 2.x relative-luminance formula for every pair listed in §4.
