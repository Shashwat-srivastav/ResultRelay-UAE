# ResultRelay console: wireframes, flows and microcopy (v2 proposal)

Status: proposal. Grounded in the console as it ships: `web/src/App.tsx`, `web/src/pages/*.tsx`,
`web/src/api/client.ts` and `app/api/routes.py`. Every sample value below comes from the shipped
scenarios, the evaluation report (`evaluation/report.md`, 144 runs) or the knowledge base. Identities
are the scenarios' invented ones.

Companion files: `01-critique.md` (findings), `02-user-stories.md` (jobs), `04-decisions.md` (what
shipped), `05-typography-and-colour.md` (tokens). This file says what to build next and where.

---

## 0. Principles and notation

**Seven rules every screen follows**

1. **The person comes first.** Before a page shows how anything works, it answers one question: does
   anyone need to act?
2. **States are words; codes are one step away.** `ESCALATION_REQUIRED` shows as **With a named person**,
   and the code appears in a tooltip, in the expanded trace, and in exports. Policy officers and judges
   still need the codes to match the docs, so they are never removed.
3. **The mark shows how much a statement counts.** AI suggestions, code checks, gate decisions and
   human decisions each have their own shape (section 6). The mark gets heavier as authority grows.
4. **Every scenario says where it came from.** It names the published incident, the source, the year,
   a link, and "identities invented" (section 5).
5. **One case has one address.** Timeline, trace, delivery and audit are tabs of `/cases/:id`. They are
   not four pages with four pickers.
6. **Empty states are honest.** Each one says what is missing, why, and the one action that fixes it.
7. **It is built for the video.** The demo is filmed at 1920×1080 with 120% zoom, which is a 1600×~825
   CSS-px viewport. Each page's answer sits above that fold, marked `┄┄ fold (video) ┄┄` in the wireframes.

**Wireframe notation**

| Mark | Meaning |
|---|---|
| `[Button]` `[▶ Primary]` | Button. `▶` marks the page's single primary action |
| `‹link›` `↗` | In-app link / external link (new tab) |
| `(Chip)` | Status chip (rendered label, the code goes in the tooltip) |
| `▾` `▸` | Select/menu, collapsed disclosure |
| `▌` | Selected row/nav item |
| `◇` `✓` `▣` `●` | Trust marks: AI suggested, checked by code, gate decided, person decided (section 6) |
| `↳ From …` | Provenance strip (section 5) |
| `░░░` | Skeleton (loading) |
| `┄┄ fold ┄┄` | Bottom of the 1600×825 video viewport |

Scale: about 1 character per 10 px. The content area is 1440 − 232 px sidebar = 1208 px, drawn
about 116 characters wide. The full shell is drawn once (1.5) and omitted after that.

**Copy style:** active voice, present tense, sentence case. British "-ise" spellings (Finalised),
"acknowledgment" without the middle e (as in the codebase and DHA text). Times are on the simulated
clock in Dubai time (GST). Say "simulated clock" once per page, never on each timestamp.

---

## 1. Information architecture

### 1.1 Current and proposed

| Today (8 nav items) | Proposed (6 nav items) | Change |
|---|---|---|
| Console `/` | **Overview** `/` | Renamed. The "needs a person" queue now leads the page |
| Case timeline `/cases` | **Cases** `/cases` (list) and **Case** `/cases/:id` (tabs) | Split: the list is a list, and a case gets its own page |
| Decision trace `/trace` | Case → **Decision trace** tab `/cases/:id/trace` | Merged into the case page; old URL redirects |
| Audit trail `/audit` | **Audit chain** `/audit` (all cases) and Case → **Audit** tab | Kept as a page; the same table also appears per case |
| Simulator `/simulator` | **Scenarios** `/scenarios` → mode **Run one** | Merged |
| Side-by-side `/compare` | **Scenarios** `/scenarios?mode=compare` → mode **Compare two** | Merged |
| Standards & gaps `/standards` | **Rules & gaps** `/standards` | Renamed; tabs reordered (search first) |
| Evaluation `/evaluation` | **Evaluation** `/evaluation` | Kept; leads with the headline finding |

Sidebar groups change from Operate / Evidence to **Work** (Overview, Cases), **Test** (Scenarios) and
**Evidence** (Rules & gaps, Evaluation, Audit chain).

### 1.2 Sitemap

```
ResultRelay
├─ WORK
│  ├─ Overview ................................ /
│  └─ Cases ................................... /cases
│     └─ Case: "The daughter replied" ......... /cases/:caseId              (tab: Summary)
│        ├─ Decision trace .................... /cases/:caseId/trace?step=5
│        ├─ Timeline .......................... /cases/:caseId/timeline
│        ├─ Delivery & revisions .............. /cases/:caseId/delivery
│        └─ Audit ............................. /cases/:caseId/audit
├─ TEST
│  └─ Scenarios ............................... /scenarios?scenario=S9…&config=resultrelay_council
│     ├─ mode: Run one (default)
│     └─ mode: Compare two .................... /scenarios?mode=compare&left=…&right=…
└─ EVIDENCE
   ├─ Rules & gaps ............................ /standards?tab=search|sources|gaps|settings|mapping
   │  └─ Clause drawer (overlay, from anywhere) ?clause=S1-11.1.3
   ├─ Evaluation .............................. /evaluation
   └─ Audit chain ............................. /audit?case=:caseId
```

### 1.3 Why each merge

**Simulator and Side-by-side become one "Scenarios" page with two modes. Yes.** Both pages pick a
scenario and a configuration and then run it. Today a judge has to choose between them before knowing
why they differ, and the scenario picker is built twice, with different labels (`Compare.tsx` lists bare
IDs and `Simulator.tsx` lists ID + title). With one page, the scenario stays selected when the mode
changes. "Compare two" is how you answer "what would a weaker system have done?", so the comparison
belongs next to the run.

**Case timeline and Decision trace become one "Case" page with tabs. Yes.** Both describe one case.
Today the trace is chosen by *run* (`/trace?run=`) and the timeline by *case* (`/cases?case=`), each with
its own picker, so a user can view S9's trace beside S3a's timeline without noticing. Dashboard rows
already jump to the trace (`Dashboard.tsx` `openTrace`). The case should be the object and the views
should be tabs. The trace becomes the default tab whenever the case has left the chain, because that is
when someone asks "why?".

**Audit trail stays a page and also becomes a tab.** The per-case table belongs on the case. A
cross-case page is still worth keeping: it is the only screen that answers "does every chain verify?" in
one look, and the policy officer starts there.

**Standards & gaps stays one page with its tabs reordered.** The policy officer's first action is to
search for a clause, so **Search clauses** comes first. Y.3172 and AI-readiness share one
**Standards mapping** tab with a toggle; they have the same table shape and the same reader. The
institutional profile and the state machine become **Lab settings**, so the 60-minute clock is shown as
the lab's own choice and not as a rule.

**Not merged: Evaluation.** It answers a different question (all scenarios against all configurations)
and judges look for it by name.

### 1.4 Routes and backward compatibility

| Old URL | New behaviour | How |
|---|---|---|
| `/` | Overview | unchanged |
| `/cases` | Cases list | unchanged path |
| `/cases?case=ID` | redirect → `/cases/ID` | client redirect in `App.tsx` |
| `/trace` | redirect → `/cases/<latest run's case>/trace` | resolve via `GET /runs` |
| `/trace?run=R&step=N` | redirect → `/cases/<case_id of R>/trace?step=N` | `GET /runs` already returns `case_id` per run |
| `/simulator` | redirect → `/scenarios` (keeps `?scenario=&config=`) | client redirect |
| `/compare` | redirect → `/scenarios?mode=compare` | client redirect |
| `/standards` | Rules & gaps, `?tab=` added | unchanged path |
| `/evaluation`, `/audit` | unchanged; `/audit?case=ID` preselects | unchanged path |
| unknown | Overview | `<Navigate to="/" />` (as today) |

Redirects use `replace`, so the back button never bounces. Links already in the README, the demo
transcript and the video keep working.

### 1.5 Global shell (1440)

```
┌──────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────┐
│ ⤺ ResultRelay            │ Overview                                           [▶ 3-minute tour]   (Synthetic data · offline) │
│   Critical lab results   │ Which critical results need a person now, and where every other one is.                     │
│                          ├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ WORK                     │                                                                                             │
│ ▌Overview            6   │   page content (1208 px)                                                                    │
│  Cases                   │                                                                                             │
│                          │                                                                                             │
│ TEST                     │                                                                                             │
│  Scenarios               │                                                                                             │
│                          │                                                                                             │
│ EVIDENCE                 │                                                                                             │
│  Rules & gaps            │                                                                                             │
│  Evaluation              │                                                                                             │
│  Audit chain        ✓    │                                                                                             │
│                          │                                                                                             │
│ ──────────────────────── │                                                                                             │
│ Demonstration build      │                                                                                             │
│ Synthetic patients;      │                                                                                             │
│ identities invented. No  │                                                                                             │
│ hospital system or live  │                                                                                             │
│ messaging is connected.  │                                                                                             │
│ Clock: simulated, GST    │                                                                                             │
│ Version 0.1.0            │                                                                                             │
└──────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────┘
```

* The **6** badge on Overview counts cases with an open escalation in ResultRelay runs. The **✓** on
  Audit chain means every chain verified at load; it changes to **✗ 1** if any chain breaks.
* **3-minute tour** starts flow (b) (section 3).
* **390 px:** the sidebar becomes a top bar with the logo, page title and a menu button. The menu opens
  a full-height sheet with the same groups. The data flag shrinks to an icon with a label for screen
  readers. The tour button moves into the menu.

---

## 2. Pages

### 2.1 Overview `/`

**Single job:** show the person on duty which cases are waiting for a human, and show that the rest
are accounted for.
**Five-second question:** *Does anyone need me right now, and for what?*

```
┌ NEEDS A PERSON NOW · 6 ──────────────────────────────── Showing: ResultRelay runs ▾  (7 comparison runs hidden) ‹All cases›┐
│ CASE                                   WHY IT NEEDS A PERSON                                 OWNER · DEADLINE              │
│ ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── │
│ The daughter replied                   The reply came from the patient's daughter. The       Supervisor on duty            │
│ SYN-CASE-010 · walk-in · Dubai         patient has not been reached.                         due 14:51 · 23 min left       │
│ ↳ From Medical Protection, 2017 ↗      ◇ AI reviewer objected → ✓ code kept it → ▣ gate      [Open case →]                 │
│ ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── │
│ Escalation nobody answered             The Supervisor did not respond within 30 min. Raised  Clinical lead (2nd tier)      │
│ SYN-CASE-011 · walk-in · Dubai         to the Clinical lead.                                 due 15:06 · overdue tier 1    │
│ ↳ From CRICO, 2023 ↗                   ▣ gate: no approved channel → ▣ gate: deadline passed [Open case →]                 │
│ ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── │
│ Accepted by the gateway, never         Gateway accepted the SMS 61 min ago. No delivery      Supervisor on duty            │
│ delivered · SYN-CASE-009               receipt, no acknowledgment.                           due 15:31                     │
│ ↳ From BMJ Open Quality, 2021 ↗        ▣ gate: acknowledgment window passed (lab setting)    [Open case →]                 │
│ ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── │
│ Genetic result, generic rule           A genetic result must go to the referring physician   Supervisor on duty            │
│ retrieved · SYN-CASE-005               (DHA ST-28 §13.4), not to the patient.                due 14:32                     │
│ ↳ From genetic-testing case series,    ▣ gate refused a patient send (scope)                 [Open case →]                 │
│   2019 ↗                                                                                                                   │
│                                                                                     ‹Show 2 more: S3a SMS down, S11 …›     │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ WHERE EVERY RESULT IS · 12 ResultRelay runs ───────────────────────────────────────────────────────────────────────────────┐
│  1 Finalised  ›  2 Sent  ›  3 Accepted by gateway  ›  4 Delivered  ›  5 Acknowledged  ›  6 Documented                      │
│      0              0              0                     0                  0                 6 ✓                          │
│                           accepted is not delivered   delivered is not acknowledged   a named person, current revision     │
│  OUT OF THE CHAIN   With a named person  6   ·   Delivery unknown or failed  0   ·   Correction in progress  0              │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ fold (video) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
┌ EVIDENCE BASE ────────────────────────────────────┐ ┌ AUDIT ACTIVITY ──────────────────────────────── ‹Check the chain›┐
│ 96 excerpts from 24 documents                     │ │ 14:21  Handed to a person · SYN-CASE-010                      │
│ 74 checked against the official download          │ │        Supervisor on duty, due 14:51 · entry 22 · 339589e1    │
│ 18 policy gaps recorded  ‹Gap register›           │ │ 14:20  Acknowledgment received · SYN-CASE-010                 │
│ Retrieval: BM25, deterministic · Live network: none│ │        entry 21 · 1a0a0d1a                                    │
│ A quote that isn't found on its source page is    │ │ ‹Show all activity›                                           │
│ left out of retrieval.                            │ └───────────────────────────────────────────────────────────────┘
└───────────────────────────────────────────────────┘
SCENARIOS  11 of 12 are reconstructed from published incidents (Medical Protection, CRICO, AHRQ PSNet, BMJ Open Quality,
AJCP, genetic-testing case series). 1 is a constructed test (S6). All identities are invented.  ‹See sources›
WHAT THIS CONSOLE DOES NOT DO ▸  (no clinical judgement · no advice to patients · no compliance claim)
```

**Data:** `GET /cases` plus `GET /scenarios` (title and provenance joined on `scenario_id`). Escalation
owner and due time need the case's escalations on each list row (P1 backend change; until then, open
the case to see them). The "why" sentence comes from the table in 4.6.

**Default filter:** only `resultrelay` and `resultrelay_council` runs. Today, policy-blind runs inflate
"Delivered" (two of them sit in "Delivered" in `console.png`) and duplicate rows such as SYN-CASE-003 ×5.
The comparison runs are one click away: **Show comparison runs (7)**.

**390 px:** the queue becomes a stack of cards. Each card shows the case title, the state chip, the
owner and countdown on one line, the "why" sentence, and a provenance line in small type. The whole card
is the tap target. The chain strip becomes a vertical list of six stages and three exits with counts
aligned right. Stages with zero cases collapse into one line ("Stages 1–5: 0 cases"). Evidence base and
audit activity become two disclosures at the bottom. The "does not do" note stays as one line.

**Hierarchy:** primary is the *Needs a person now* queue. Secondary is the chain counts. Tertiary is
Evidence base, Audit activity, the scenario provenance footer and the scope note.

| State | Copy |
|---|---|
| Loading | Queue: 3 skeleton rows `░░░`. Counts show `–`. Screen reader: "Loading cases…" |
| Empty, no cases at all | **No cases yet.** Each scenario run creates one case. `[▶ Run a scenario]` |
| Empty, nobody needs a person | **Nobody needs to act.** Every ResultRelay case is in the chain or documented. ‹See all cases› |
| Empty, filter hides everything | **No ResultRelay runs yet.** 7 comparison runs are hidden. `[Show comparison runs]` `[Run a scenario]` |
| Error | **Couldn't load cases.** The server said: `{status} {message}`. `[Try again]` (counts show `–`, never 0) |
| Health error (evidence panel) | **Couldn't check the evidence base.** Retrieval may still work. `[Try again]` |

---

### 2.2 Cases `/cases`

**Single job:** find any case and see where it stands.
**Five-second question:** *Where is each case, and who holds it?*

```
┌ FILTERS ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [Needs a person 6] [In the chain 0] [Documented 6] [All 12]     Runs: ResultRelay ▾     Scenario: Any ▾     🔍 Case ID…    │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ 12 CASES · newest first ───────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CASE                              WHERE IT IS              ACKNOWLEDGED          DELIVERY        OWNER · DEADLINE    RUN    │
│ ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── │
│ The daughter replied              (With a named person)    (By a reply — R1)⚠    1 of 1          Supervisor           Council│
│ SYN-CASE-010 · walk-in            since 14:21              reply text: daughter   delivered      due 14:51            ›      │
│ ↳ Medical Protection, 2017 ↗                                                                                               │
│ ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── │
│ Result corrected after it was     (Corrected result        (Current revision R2)  2 of 2         —                    Rules  │
│ acknowledged · SYN-CASE-002        acknowledged) ✓          R1 ack kept, not used  delivered                          ›      │
│ ↳ AHRQ PSNet, 2012 ↗                                                                                                       │
│ ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── │
│ Delivery outcome unknown          (Documented) ✓           (Current revision R1)  1 of 2         —                    Rules  │
│ SYN-CASE-001 · walk-in                                                            1 reconciled                        ›      │
│ ↳ AHRQ PSNet, 2017 · BMJ OQ, 2021 ↗                                                                                        │
│ …                                                                                                                          │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**390 px:** the filter pills scroll sideways in one row, and the selects move into a "Filters" sheet.
Each row becomes a card with the title, the state chip, owner and deadline, and the provenance line.
Acknowledgment and delivery move to a second line in small type. The run name sits at the bottom right
of the card.

**Hierarchy:** primary is the case title and *Where it is*. Secondary is acknowledgment, delivery and
owner. Tertiary is the run name, provenance and the case ID.

| State | Copy |
|---|---|
| Loading | 6 skeleton rows |
| Empty store | **No cases yet.** Each scenario run creates one case. `[▶ Run a scenario]` |
| Empty filter | **No cases match these filters.** `[Clear filters]` |
| Error | **Couldn't load cases.** The server said: `{status} {message}`. `[Try again]` |

---

### 2.3 Case `/cases/:caseId`

One header and five tabs. The header is the same on every tab.

```
┌ CASE HEADER ───────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ‹← Cases›                                                                                                                  │
│ The daughter replied                                                               [▶ Take this case]  [Download bundle ↓]  │
│ SYN-CASE-010 · Dubai walk-in laboratory · Revision R1 (current) · ResultRelay + agent council · run bb0899abb4              │
│ (With a named person)  Supervisor on duty · since 14:21 · due 14:51 · then Clinical lead          Simulated clock, GST      │
│ ↳ Reconstructed from: Medical Protection Asia Casebook, July 2017, Case 2: "a relative asks for a patient's blood-test       │
│   result" ↗ · Match: very strong · Names, times and values are invented.                                                    │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Summary   ▌Decision trace · 5 steps    Timeline · 9 events    Delivery & revisions    Audit · 23 ✓                         │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Default tab:** *Decision trace* if the case is out of the chain (escalated, unknown, correction), and
*Summary* otherwise. When the URL already names a tab or step, the URL wins.

**Take this case** appears only when the state is *With a named person* (`ESCALATION_REQUIRED`) and the
run is live in the registry. It sends `POST /runs/:runId/events {type:"escalation.resolved",
actor:"SUPERVISOR"}`, which moves the case to *In review*. Confirmation dialog:

> **Take this case?**
> You become the named person for SYN-CASE-010. Automatic sends stay blocked, and the case won't be
> raised to the Clinical lead at 14:51. This is recorded in the audit chain under *Supervisor on duty*.
> `[Cancel]` `[Take this case]`

After it succeeds: toast **"You have the case. Recorded as audit entry 24."** The chip changes to
**In review** and the button becomes disabled with the text **Taken by Supervisor on duty, 14:30**.

**390 px (whole page):** the header stacks: back link, title, state chip, owner and deadline, then a
provenance line clamped to two lines with "more". Both buttons go into a sticky bottom bar; *Take this
case* is full width. Tabs become a row that scrolls sideways, with the active tab scrolled into view.
Each tab's two-column layout becomes a single column.

**Header states**

| State | Copy |
|---|---|
| Loading | Title skeleton, chips skeleton; tabs are visible but disabled |
| Case not found (404) | **We can't find case `{id}`.** It may be from a store that was reset. ‹Back to cases› `[Run this scenario again]` (only if the ID names a scenario) |
| Error | **Couldn't load this case.** The server said: `{status} {message}`. `[Try again]` |
| Take this case failed | **Couldn't take the case.** Nothing was recorded. The server said: `{message}`. `[Try again]` |
| Run not in memory (button hidden) | Tooltip on the disabled button: *This run is no longer live. Re-run the scenario to act on it.* |

#### 2.3.1 Summary tab

**Job:** say in one paragraph why the case is where it is, and what can be done.
**Five-second question:** *Why is this case here, and what happens next?*

```
┌ WHY IT IS HERE ───────────────────────────────────────────────────────────────┐ ┌ WHAT YOU CAN DO ─────────────────────────┐
│ The result was delivered and the gateway recorded an acknowledgment, but the  │ │ ● Take this case                         │
│ reply says it is from the patient's daughter. The patient has not been        │ │   Stops the escalation to the Clinical   │
│ reached, so the case was handed to the Supervisor instead of being closed.    │ │   lead and records you as the owner.     │
│                                                                               │ │   [▶ Take this case]                     │
│ Finalised ✓ › Sent ✓ › Accepted ✓ › Delivered ✓ › Acknowledged ⚠ › Documented ✗│ │                                          │
│                                                     └ left the chain at step 5 │ │ Then, outside this system: reach the     │
│                                                                               │ │ patient on a verified number and record  │
│ ◇ AI reviewer: reply contradicts the record (0.93) → ✓ code: objection stands │ │ who you spoke to. (Recording the outcome │
│ → ▣ gate: hand to Supervisor → ● nobody yet                                   │ │ here is planned; see P2-3.)              │
│ ‹Open the decisive step (5) →›                                                │ │                                          │
└───────────────────────────────────────────────────────────────────────────────┘ │ If nobody takes it by 14:51 it goes to   │
┌ OPEN QUESTIONS · 2 ───────────────────────────────────────────────────────────┐ │ the Clinical lead automatically.         │
│ GR-09  No rule says how to verify who answered a message.     ‹Gap register›  │ └──────────────────────────────────────────┘
│ GR-03  No official deadline to acknowledge. 60 min is this lab's own setting.│
└───────────────────────────────────────────────────────────────────────────────┘
┌ AT A GLANCE ──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Current revision R1 · Delivery 1 of 1 delivered · Acknowledgments 1 (binds to R1, from a reply) · Escalations 1 ·         │
│ Audit chain valid, 23 entries                                                                                            │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Hierarchy:** primary is the *Why it is here* paragraph and the chain. Secondary is *What you can do*.
Tertiary is open questions and the at-a-glance strip.

| State | Copy |
|---|---|
| Documented case, *Why* panel | **Closed.** {Who} acknowledged revision {R} at {time} and the communication was recorded. Nothing is open. |
| No open questions | **No open questions.** Every condition the gate checked was settled. |
| *What you can do*, case not escalated | **Nothing needs you.** The case is moving through the chain on its own. |

#### 2.3.2 Decision trace tab `/cases/:id/trace?step=N`

**Job:** for each step, show what happened, which rules applied, what each agent said, what code
checked, what the gate decided and what a person decided, in that order.
**Five-second question:** *Who or what made this decision, and on which clause?*

**Default step** when there is no `?step=`: the *decisive step*. That is the first step where the gate
refused, or where the case left the chain. If neither happened, it is the last step. Today the trace
opens on step 1, which is almost never the interesting one.

```
┌ STEPS ────────────────────┐ ┌ STEP 5 OF 5 · 14:21 · decisive step ─────────────── ‹Compare: rules only ends "Documented" ✗›┐
│ 1  14:00  Finalised     ✓ │ │ The gate handed the case to the Supervisor. The AI reviewer said the reply contradicts the│
│    Lab released R1        │ │ record (confidence 0.93; the bar for free text is 0.70). Code can't check free text, so a │
│ 2  14:01  Sent          ✓ │ │ person decides.                                                                           │
│    SMS to patient         │ │                                                                                           │
│ 3  14:03  Delivered     ✓ │ │ 1  WHAT HAPPENED                                                                          │
│    Receipt matches ATT-001│ │    A reply arrived from the registered number. The gateway marked it "acknowledgment,     │
│ 4  14:20  Acknowledged  ⚠ │ │    verified number".                                                                      │
│    Reply received         │ │    ❝This is his daughter. My father is in hospital abroad and does not have his phone.   │
│▌5  14:21  With a person ● │ │     I will tell him when he calls.❞                                                       │
│    Handed to Supervisor   │ │                                                                                           │
│                           │ │ 2  RULES IT CHECKED                                    Binding = must be followed in Dubai │
│ ───────────────────────── │ │    (Binding · Dubai) DHA ST-28 §11.1.3, printed p.40   ✓ quote found on the source page    │
│ ◇ AI suggested            │ │    "The laboratory shall keep record of the communication with the patient." ‹Clause›     │
│ ✓ Checked by code         │ │    (Binding · Dubai) DHA ST-28 §11.1.1, p.40  "Critical laboratory results shall be      │
│ ▣ Decided by the gate     │ │    reported clearly to the patient."                                        ‹Clause›     │
│ ● Decided by a person     │ │    (Comparator · international) RCPath best practice §7, p.8: informs, cannot govern     │
└───────────────────────────┘ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ fold (video) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
                              │ 3  WHAT THE AGENTS SAID                        Advice only. Agents can only hand a case   │
                              │                                                to a person; they can't close or send.     │
                              │ ┌┄◇ AI · Policy analyst (DHA lens) · Mistral ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ Answered ┄┐ │
                              │ ┆ Reading  Communicated     Clause  DHA ST-28 §11.1.3     Settled  yes     Gap  none   ┆ │
                              │ ┆ "The acknowledgment from the patient's daughter ('This is his daughter…') confirms  ┆ │
                              │ ┆  communication of the current revision… satisfying the duty to record…"  ‹full›     ┆ │
                              │ ┆ ✓ Code check: Upheld. Every fact it cites is in the case record.                    ┆ │
                              │ └┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘ │
                              │ ┌┄◇ AI · Adversarial reviewer · different model family (Jev) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ Answered ┄┐ │
                              │ ┆ Objection  Reply contradicts the record        model confidence 0.93 (its own score)┆ │
                              │ ┆ Own reading  Waiting for acknowledgment     Analyst's claim supported  0.08         ┆ │
                              │ ┆ Problem with the analyst's claim  Ignores what the person said                       ┆ │
                              │ ┆ ✓ Code check: Objection stands. A recorded human statement exists. Code can't read   ┆ │
                              │ ┆   free text, so this kind of objection must clear 0.70 instead of 0.50.             ┆ │
                              │ └┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘ │
                              │ ┌─✓ Code · Orchestrator (deterministic) ──────────────────────────────────────────────┐ │
                              │ │ Decision  Hand to a person                                                           │ │
                              │ │ Recorded differences  Analyst and reviewer disagree (Communicated vs Waiting for     │ │
                              │ │ acknowledgment) · Objection stands                                                   │ │
                              │ └──────────────────────────────────────────────────────────────────────────────────────┘ │
                              │ ▸ 5 rule assessors: escalation proposed "Record the communication" (support 0.60), …     │
                              │                                                                                           │
                              │ 4  WHAT THE GATE DECIDED                                                                  │
                              │ ┃▣ Gate · Allowed: hand to a person                                                       │
                              │ ┃  Acknowledged → With a named person (Supervisor on duty)          (Moved)               │
                              │ ┃  ✓ INV-8   Acknowledgment binds to the current revision (R1)                            │
                              │ ┃  ✓ INV-1/2 Accepted is not delivered; delivered is not acknowledged                     │
                              │ ┃  ✓ Escalation role "Supervisor on duty" is configured                                   │
                              │ ┃  Authority: lab procedure P1 (no official deadline exists; gap GR-03)                   │
                              │                                                                                           │
                              │ 5  WHAT A PERSON DECIDED                                                                  │
                              │ ● Nobody yet. Supervisor on duty, due 14:51. If nobody takes it, it goes to the          │
                              │   Clinical lead.                                                     [Take this case]     │
                              │                                                                                           │
                              │ OPEN QUESTIONS   GR-09 No rule says how to verify who answered ‹›  ·  GR-03 No official   │
                              │                  deadline ‹›                                                              │
                              │ ‹← Step 4: Acknowledged›                                          Step 5 of 5 · corpus 3f9a…│
                              └───────────────────────────────────────────────────────────────────────────────────────────┘
```

**Rules for the step:**
* Section names and order are fixed on every step: *What happened, Rules it checked, What the agents
  said, What the gate decided, What a person decided, Open questions*. A section with nothing in it
  still appears, with one muted line ("No council on this step: rules-only configuration."). That
  keeps the shape the same, so a reader learns where to look once.
* The **summary sentence** comes from a template (4.7) and is the only prose on the step that is not a
  quote or an artefact.
* The raw codes appear in a `▸ Codes` disclosure at the end of each section (`obligation COMMUNICATED,
  clause S1-11.1.3 …`, the `TEXT_CONTRADICTS_RECORD` string), for readers who check against
  `council.py` or the audit bundle.
* Citations open the **clause drawer** (2.5.5), so the reader never leaves the trace.
* *Compare: rules only* deep-links to `/scenarios?mode=compare&scenario=S9…&left=resultrelay_council&right=resultrelay`.

**390 px:** the step rail becomes a horizontal row of chips ("1 ✓ 2 ✓ 3 ✓ 4 ⚠ 5 ●") pinned under
the tabs. The step detail is one column. Each section is a disclosure, and *What happened* and *What the
gate decided* open by default. The agent cards stack, and the quote clamps to 4 lines with "more".

**Hierarchy:** primary is the summary sentence and *What the gate decided*. Secondary is *What
happened*, *Rules it checked*, the agents and the code checks. Tertiary is the rule assessors, raw codes
and the corpus hash.

| State | Copy |
|---|---|
| Loading | Rail: 5 skeleton pips. Detail: 3 skeleton blocks |
| Run not in memory | **The step-by-step trace for this run isn't available. The server was restarted.** The audit chain still holds every decision (‹Audit tab›). `[Re-run this scenario]` (same scenario and configuration) |
| No steps yet | **No steps yet.** This run was started but no event has been released. ‹Continue in Scenarios› |
| No evidence on a step | No clause scored above the relevance floor for this step. |
| No council on a step | No council on this step: {configuration label} doesn't use agents. |
| No person yet | ● Nobody yet. {Role}, due {time}. |
| Error | **Couldn't load the trace.** The server said: `{status} {message}`. `[Try again]` |

#### 2.3.3 Timeline tab

**Job:** show, in time order, what each layer did, so that one layer's success can't stand in for
another's.
**Five-second question:** *What happened when, and at which layer?*

```
┌ TIMELINE · 9 events · simulated clock, GST ───────────────── Layers: [All] [Lab] [Network] [People] [Rules] [Workflow] [Audit]┐
│ TIME   LAB                 NETWORK                    PEOPLE                          RULES                 WORKFLOW         │
│ 14:00  R1 released                                                                    DHA ST-28 §11.1.1     Finalised        │
│ 14:01                      Send requested (ATT-001)                                                         Sent             │
│ 14:01                      Gateway accepted                                                                 Accepted by gw   │
│ 14:03                      Delivery receipt matched                                                         Delivered        │
│ 14:20                                                 Reply: "This is his daughter…"                        Acknowledged     │
│ 14:21                                                                                 GR-09 surfaced        With a person    │
│ 14:21                                                 ▣ Handed to Supervisor (ESC-001)                                       │
│        ▸ 2 audit-only events                                                                                                 │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
‹Switch to list view›  (columns: #, Time, Layer, What happened, By; the current "Event stream" table)
```

**390 px:** the swimlane becomes a single vertical timeline. Each event shows a coloured layer tag
(text, not colour alone), the time and the sentence. The layer filter becomes a select.

**Hierarchy:** primary is the Workflow column, which shows state changes. Secondary is the Network and
People lanes. Tertiary is Rules and Audit.

| State | Copy |
|---|---|
| Loading | 6 skeleton rows |
| No events | **No events recorded for this case yet.** |
| Layer empty | No {layer} events recorded. |
| Error | **Couldn't load the timeline.** `[Try again]` |

#### 2.3.4 Delivery & revisions tab

**Job:** show the evidence behind "delivered" and "acknowledged" for each revision.
**Five-second question:** *Did it reach a device, did a person acknowledge it, and was that the current
revision?*

```
┌ REVISIONS ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ R1  Synthetic analyte A (walk-in permitted panel) · v1 · (Current)                                                         │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ SEND ATTEMPTS ─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ATTEMPT   CHANNEL           REVISION   GATEWAY     RECEIPT          OUTCOME      RECONCILED   DUPLICATE                    │
│ ATT-001   SMS to patient    R1         Accepted    Matched 14:03    Delivered    —            —                            │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ ACKNOWLEDGMENTS ───────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ RECORDED AS                  CHANNEL          REVISION   COUNTS FOR CURRENT?   NOTE                                        │
│ Patient (verified number)    SMS to patient   R1         ✓ binds to R1         ⚠ Reply text says it's from the daughter.    │
│                                                                                ‹See step 5›                                 │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ CHANNELS (this run) ──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ SMS to patient (SMS, primary) (Working)  ·  Patient portal (Working)  ·  Phone call (Working)  ·  Fallback approved: no    │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ CITATIONS RELIED ON · 6 ───────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CLAUSE                    AUTHORITY HERE        CITED BY                 STEP                                              │
│ DHA ST-28 §11.1.1 p.40    (Binding · Dubai)     Policy applicability     2                                                 │
│ DHA ST-28 §11.1.3 p.40    (Binding · Dubai)     Policy analyst (AI)      5                                                 │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

S2 (correction) example row: `Patient · SMS · R1 · ✗ earlier revision: doesn't count for R2 (INV-8)`.

**390 px:** each table becomes a list of cards. The *Counts for current?* answer is the first thing on
each acknowledgment card.

**Hierarchy:** primary is the Acknowledgments table. Secondary is send attempts and revisions.
Tertiary is channels and citations.

| State | Copy |
|---|---|
| No attempts | **Nothing has been sent.** {e.g. The gate refused a patient send: genetic results go to the physician.} |
| No acknowledgments | **No one has acknowledged this result.** Delivery is not acknowledgment. |
| No citations | **No clause was relied on.** {Configuration} doesn't use the knowledge base. |

#### 2.3.5 Audit tab

The same component as the Audit chain page (2.7), filtered to this case. There's no case picker; the
case comes from the URL. Its states are listed in 2.7.

---

### 2.4 Scenarios `/scenarios` (Simulator and Side-by-side merged)

**Single job:** replay a reconstructed incident, either one event at a time or against a weaker system.
**Five-second question:** *What does this incident look like when ResultRelay handles it, and what would
a weaker system do?*

#### 2.4.1 Mode: Run one (before starting)

```
┌ MODE ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ (•) Run one, event by event     ( ) Compare two configurations                                                            │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ 1 · PICK A SCENARIO · 12 ─────────────────────────────────┐ ┌ 2 · ABOUT THIS SCENARIO ─────────────────────────────────────┐
│ ACKNOWLEDGMENT                                            │ │ S9 · The daughter replied                         5 events    │
│ ▌S9   The daughter replied                    5 events    │ │ A walk-in critical result is delivered by SMS. A reply comes  │
│       ↳ Medical Protection, 2017 · very strong            │ │ from the registered number, and the gateway marks it as an    │
│  S11  Delivered, never acknowledged           6 events    │ │ acknowledgment from a verified number. The words say it's the │
│       ↳ AHRQ PSNet, 2017 · BMJ OQ, 2021 · strong          │ │ patient's daughter, and that the patient is abroad.           │
│  S5   Late acknowledgment races a correction  7 events    │ │                                                               │
│       ↳ AHRQ PSNet, 2012 · related                        │ │ Safe ending: With a named person                              │
│ DELIVERY                                                  │ │ Tests: whether agents that read free text catch what rules    │
│  S1   Delivery outcome unknown                6 events    │ │ miss. Only the agent council passes it (Evaluation ›).        │
│  S8   Accepted by the gateway, never delivered 5 events   │ │                                                               │
│  S3a  SMS down, no approved fallback          5 events    │ │ ↳ Reconstructed from: Medical Protection Asia Casebook, July  │
│  S3b  SMS down, approved fallback             5 events    │ │   2017, Case 2 ↗ · Medical Protection: "Digital dilemmas,     │
│ CORRECTION                                                │ │   communicating with patients by text" ↗                      │
│  S2   Corrected after it was acknowledged     7 events    │ │   Match: very strong · Names, times and values invented.      │
│ ROUTING AND JURISDICTION                                  │ ├ 3 · PICK A CONFIGURATION ─────────────────────────────────────┤
│  S4   Genetic result, generic rule retrieved  4 events    │ │ (•) ResultRelay + agent council       the full system         │
│  S7   Genetic result routed to the physician  6 events    │ │ ( ) ResultRelay, rules only           no AI                   │
│  S6   Abu Dhabi rule ranks above Dubai's      4 events    │ │ ( ) Conventional rules engine         the row to beat         │
│       ↳ Constructed test, not from an incident            │ │ ( ) Policy-blind tracker              what most tools do      │
│ ESCALATION                                                │ │ ▸ 8 more: citation-only RAG and one-control-off ablations     │
│  S10  Escalation nobody answered              6 events    │ │                                                               │
│       ↳ CRICO, 2023 · almost exact                        │ │ [▶ Start]   ‹Compare against another configuration›           │
└───────────────────────────────────────────────────────────┘ └───────────────────────────────────────────────────────────────┘
```

#### 2.4.2 Mode: Run one (running)

```
┌ S9 The daughter replied · ResultRelay + agent council ─────── 4 of 5 events ████████████░░░ ─ [▶ Next event] [Play to the end] [Restart] ┐
│ ↳ From Medical Protection, 2017 ↗ · identities invented                                         ‹Open as a case →›   [Download bundle ↓] │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ CASE NOW ──────────────────────────────────────┐ ┌ EVENTS RELEASED · 4 ─────────────────────────────────────────────────────────────────┐
│ (Acknowledged)                                 │ │ 04  14:20  Acknowledgment received                     Delivered → Acknowledged  ▸ │
│ A named person acknowledged R1. Not yet        │ │     Reply from the registered number: "This is his daughter…"                      │
│ documented.                                    │ │     ▣ Gate allowed · INV-8 ✓ binds to R1                                           │
│                                                │ │ 03  14:03  Delivery receipt                              Accepted → Delivered    ▸ │
│ Fin ✓ › Sent ✓ › Acc ✓ › Del ✓ › Ack ● › Doc   │ │     ▣ Gate allowed · INV-2: delivered is not acknowledged                          │
│                                                │ │ 02  14:01  Decision point: send?                       Finalised → Sent          ▸ │
│ Revision      R1 (current)                     │ │     ◇ rules: send on the main channel · cites DHA ST-28 §11.1.1 · ▣ allowed        │
│ Delivery      1 of 1 delivered                 │ │ 01  14:00  Lab released the result                     — → Finalised             ▸ │
│ Acknowledged  1 · binds to R1                  │ │                                                                                    │
│ Escalations   none                             │ │ Next: 05 Decision point: record the communication?   [▶ Next event]                │
│ Audit chain   valid · 19 entries               │ └────────────────────────────────────────────────────────────────────────────────────┘
├ CHANNELS ──────────────────────────────────────┤
│ SMS to patient (primary)        (Working)      │
│ Patient portal                  (Working)      │
│ Phone call                      (Working)      │
└────────────────────────────────────────────────┘
```

* The newest event is at the top. Expanding a row (`▸`) opens the **same step component** as the
  decision trace (2.3.2), so there is one renderer and one vocabulary.
* "Open as a case →" goes to `/cases/:caseId/trace?step=<latest>`.
* *Next event* is the primary button while events remain. After the last one, the primary becomes
  **Open the decision trace →**.

#### 2.4.3 Mode: Compare two

```
┌ COMPARE TWO CONFIGURATIONS ON THE SAME SCENARIO ──────────────────────────────────────────────────────────────────────────┐
│ Scenario  S9 The daughter replied ▾          Left  ResultRelay + agent council ▾    vs    Right  ResultRelay, rules only ▾ │
│ Quick picks  [Council vs rules only]  [Full system vs policy-blind]  [Rules only vs conventional rules]      [▶ Run both] │
│ Same scenario, same seed, same network plan. Any difference comes from the configuration.                                 │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ OUTCOME ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                         LEFT · ResultRelay + agent council            RIGHT · ResultRelay, rules only                     │
│ Ends                    ✓ Safe: With a named person (Supervisor)      ✗ Unsafe: Documented, closed on the daughter's reply│
│ Rules cited             DHA ST-28 §11.1.1, §11.1.3                    DHA ST-28 §11.1.1, §11.1.3                          │
│ Gate refusals           0                                             0                                                   │
│ Out-of-jurisdiction     0                                             0                                                   │
│ Send attempts           1                                             1                                                   │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ STEP BY STEP · first difference at step 5 ─────────────────────────────────────────────────────────────────────────────────┐
│ STEP  EVENT                               LEFT                                         RIGHT                               │
│ 1     Lab released the result             Finalised                                    Finalised                           │
│ 2     Decision point: send?               Sent                                         Sent                                │
│ 3     Delivery receipt                    Delivered                                    Delivered                           │
│ 4     Acknowledgment received             Acknowledged                                 Acknowledged                        │
│▌5 ◀   Decision point: record it?          ▣ With a named person                        ▣ Documented ✗                      │
│                                           ◇ AI reviewer: reply contradicts the record  no council; structured fields only  │
│                                           ‹Open step 5›                                 ‹Open step 5›                       │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Policy-blind on S9 also ends **Documented ✗**. The more telling policy-blind contrasts are S8 (ends
**Delivered**: it read "accepted" as delivered) and S3a (ends **Delivered** on a channel that is down).
The quick picks carry those as their defaults: *Full system vs policy-blind* pre-selects S8.

**Safe/unsafe** needs `safe_final_states` from `scenarios/expected/*.json` in `GET /scenarios` (P1).
Until then the row shows the two final states without ✓/✗, plus a link to the Evaluation verdict.

**390 px (whole page):** in Run mode the scenario list is a full-width list. Picking a scenario opens a
details sheet with provenance, configuration radio buttons and Start. While running, *Case now* collapses
to a sticky chip bar ("Acknowledged · 4/5 · Next event"), and the events list fills the screen. In
Compare mode, Left and Right become tabs above one column, and the step table becomes cards showing
"Left: … / Right: …". The first difference is marked on its card and scrolled into view.

**Hierarchy:** in Run mode, primary is the event stream and *Next event*, secondary is *Case now*, and
tertiary is channels and the download. Before starting, primary is the scenario list and Start. In
Compare mode, primary is the Outcome row and the first-difference row, secondary is the step table, and
tertiary is totals.

| State | Copy |
|---|---|
| Scenarios loading | List: 8 skeleton rows; About panel: skeleton |
| Scenarios failed | **Couldn't load scenarios.** The server said: `{message}`. `[Try again]` |
| No scenario selected | (Never shown: the first scenario in the list is selected, which is S9 when entered from the tour) |
| Starting | Button shows a spinner: "Starting…" |
| Waiting for the first event | **Ready. Nothing has happened yet.** Release the first event to see the lab finalise the result. `[▶ Next event]` |
| Run finished | **Run complete: {state label}.** `[▶ Open the decision trace →]` `[Run it again]` `[Compare against…]` |
| Step failed | **That event couldn't be applied.** Nothing changed and nothing was recorded. The server said: `{message}`. `[Try again]` |
| Run lost (404 on step) | **This run is no longer live. The server was restarted.** `[Start it again]` |
| Compare: same config twice | Pick two different configurations. (Inline under the selects; Run both disabled) |
| Compare running | "Running the left side… / Running the right side…" with a 2-part progress bar |
| Compare: identical results | **Both configurations end the same way on this scenario.** That's a real result: this scenario doesn't separate them. Try ‹S9› or ‹S8›. |
| Compare failed | **The comparison stopped.** {Left/Right} failed: `{message}`. `[Run both again]` |

---

### 2.5 Rules & gaps `/standards`

**Single job:** show which clause backs a decision, whether it binds a Dubai case, and where the rules
say nothing.
**Five-second question:** *Is this rule binding here, or only a comparator, and was the quote checked?*

Tabs, in this order: **Search clauses** · **Sources (24)** · **Gap register (18)** · **Lab settings** ·
**Standards mapping**.

#### 2.5.1 Search clauses (default tab)

```
┌ SEARCH 96 EXCERPTS · English or Arabic ───────────────────────────────────────────────────────────────────────────────────┐
│ [ walk-in critical result reported clearly to the patient                                       ]  For a case in [Dubai ▾] │
│ Show  [(•) Rules that apply here]  [ Comparators only ]  [ Everything ]                                        [▶ Search] │
│ Try: ‹genetic results to the physician› ‹record of communication› ‹نتيجة حرجة المريض› ‹SMS delivery report›             │
│ "Rules that apply here" is the filter the policy agents use. The citation-only RAG baseline searches without it.          │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
  3 results · 51 considered · 45 left out by the filter        ⓘ Keyword search only (BM25); the vector store is offline.
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ (Binding · Dubai)  DHA Standards for Clinical Laboratory Services (ST-28) · §11.1.1 · printed p.40          score 7.412   │
│ "Critical laboratory results shall be reported clearly to the patient."                                                   │
│ ✓ Quote found on the source page · Checked against the official download ↗ · Cited in 9 cases ‹›           ‹Open clause› │
├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ (Binding · Dubai)  DHA ST-28 · §11.1.3 · printed p.40                                                       score 6.903   │
│ "The laboratory shall keep record of the communication with the patient."                                                 │
│ ✓ Quote found on the source page · Checked against the official download ↗                                ‹Open clause› │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

When "Everything" is selected, comparator results are visually set apart. They get an outlined chip,
**(Comparator · Abu Dhabi)**, and a line: *Binding in Abu Dhabi. For a Dubai case it informs and can't
govern.* Example: AD1 PP.11.2(d), "The notification is documented, including time and date called, and
the identification of the individual called…".

The query field and result text use `dir="auto"`, so Arabic renders right to left without breaking the
layout.

#### 2.5.2 Sources

```
│ SOURCE  DOCUMENT                                        ISSUED BY       APPLIES IN   AUTHORITY FOR A DUBAI CASE     CHECKED AGAINST              EXCERPTS │
│ S1      Standards for Clinical Laboratory Services      DHA             Dubai        (Binding)                      Official download ↗          14       │
│ U1      Federal Law No. 2 of 2019 (ICT in health)       UAE federal     UAE          (Binding)                      Transcription                6        │
│ U8      Regulatory Policy: Mobile Spam                  TDRA            UAE          (Binding on telecom licensees) Third-party copy             4        │
│ AD1     HAAD Clinical Laboratory Standards              DoH Abu Dhabi   Abu Dhabi    (Comparator) binding in AD     Official download ↗          8        │
│ G5      Communication of critical and unexpected …      RCPath          International (Comparator)                  Official download ↗          4        │
│ F1      ITU-T Y.3172 ML architectural framework         ITU-T           International (Binding for implementers)    Official download ↗          8        │
```

Header strip: **24 documents · 96 excerpts · every quote found on its source page · 74 checked against
the official download** · `[Download manifest.json]`.

#### 2.5.3 Gap register

Columns: **ID · The question the rules don't answer · Kind · Stage · What we do instead · Compared ·
Checked · Author's confidence**. Filter pills by kind. Each row's "What we do instead" names the product
control (for example GR-03 → "60-minute acknowledgment window, a lab setting (P1)"). It also links the
cases where the gap surfaced: *Surfaced in: S9, S10, S11 ›*.

#### 2.5.4 Lab settings

Two panels. **Timing and routing**: acknowledgment window 60 min, escalation response 30 min, retry
after 15 min, max retries 1, escalation role Supervisor on duty, second tier Clinical lead, fallback
approved: no. Each value carries the tag *(Our setting): no official rule sets this; see GR-03*.
**Case states (18)**: the state list with the labels and explanations from 4.5, codes in mono.

#### 2.5.5 Standards mapping

A toggle, `[ITU-T Y.3172] [AI readiness]`, over the existing mapping table. Status is shown as *Built*,
*Partly built* and *Not built*. The footer stays: *Statuses describe this prototype, not certified
conformance. "Not built" rows are deliberate non-claims.*

#### Clause drawer (overlay; opened from any citation anywhere)

```
                                                    ┌ CLAUSE ─────────────────────────────────────────── ✕ ┐
                                                    │ DHA ST-28 §11.1.3 · printed p.40 (pdf p.40)          │
                                                    │ (Binding · Dubai)  Must be followed for this case    │
                                                    │                                                      │
                                                    │ "The laboratory shall keep record of the             │
                                                    │  communication with the patient."                    │
                                                    │                                                      │
                                                    │ Document   Standards for Clinical Laboratory         │
                                                    │            Services · DHA ST-28 · Issue 2            │
                                                    │ Checked    ✓ quote found on the page · official      │
                                                    │            download ↗ · retrieved {date}             │
                                                    │ Used in    Gate rule "Record the communication"      │
                                                    │            (INV-10) · 7 cases ‹›                     │
                                                    │ Related gaps  GR-08, GR-11                           │
                                                    │ [Open in Rules & gaps]  [Copy citation]              │
                                                    └──────────────────────────────────────────────────────┘
```

**390 px (whole page):** tabs become a select at the top. Search keeps the full-width field. The
filters fold into "Show: Rules that apply here ▾". Results are cards. The Sources and Gap tables become
cards led by the authority chip. The clause drawer becomes a bottom sheet at 90% height.

**Hierarchy:** primary is the search results and the authority chip on each one. Secondary is the
verification line and source tables. Tertiary is scores, retrieval notes and the mapping tab.

| State | Copy |
|---|---|
| Search: before first search | **Search the 96 excerpts.** Try one of the examples, or ask in Arabic. |
| Search: loading | 3 skeleton result cards |
| Search: no results | **No excerpt that applies here matches "{query}".** `[Search everything]` shows comparators too. |
| Search: retrieval note | ⓘ {note from API, e.g. Keyword search only (BM25); the vector store is offline.} |
| Search: error | **Search failed.** The server said: `{message}`. `[Try again]` |
| Sources / Gaps / Settings / Mapping loading | Table skeleton |
| Sources / Gaps / Settings / Mapping error | **Couldn't load {the sources / the gap register / the lab settings / the mapping}.** `[Try again]` |
| Gap filter empty | **No gaps of this kind.** `[Show all 18]` |
| Clause not found (`?clause=` stale) | **That clause isn't in this corpus.** The index may have been rebuilt (corpus {hash}). |

---

### 2.6 Evaluation `/evaluation`

**Single job:** show which configurations end each scenario safely, and which single control made the
difference.
**Five-second question:** *Does the full system beat the alternatives, and on which scenario?*

```
┌ RESULT ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ The agent council ends all 12 scenarios safely. Rules only ends 11.                                                       │
│ The difference is S9, the daughter's reply: every configuration without the council records it as done.                  │
│ Synthetic scenarios, written by the team that built the system. Not a safety or compliance claim. ‹Why this matters ▸›    │
│ Last run 2 Nov 2026, 19:19 · 144 runs · replay stable in all 12 configurations                     [Re-run all 144]       │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ DOES EACH SCENARIO END SAFELY? ── ✓ safe ending and invariants held · ✗ not ── click a cell to replay it ─────────────────────┐
│                                        FULL SYSTEM   │ COMPOUND BASELINES          │ ONE CONTROL TURNED OFF                    │
│                                        Council Rules │ Conv.  RAG   Policy-blind   │ KB  Juris  Gate  Audit  Context Ack  Transp│
│ S1  Delivery outcome unknown             ✓      ✓    │  ✓     ✗     ✗              │ ✓   ✓      ✓     ✓      ✓      ✓    ✗     │
│ S2  Corrected after acknowledgment       ✓      ✓    │  ✓     ✗     ✗              │ ✓   ✓      ✗     ✓      ✓      ✗    ✓     │
│ S3a SMS down, no approved fallback       ✓      ✓    │  ✓     ✗     ✗              │ ✓   ✓      ✗     ✓      ✓      ✓    ✓     │
│ S3b SMS down, approved fallback          ✓      ✓    │  ✓     ✓     ✓              │ ✓   ✓      ✓     ✓      ✓      ✓    ✓     │
│ S4  Genetic, generic rule retrieved      ✓      ✓    │  ✓     ✓     ✗              │ ✗   ✓      ✓     ✓      ✓      ✓    ✓     │
│ S5  Late ack races a correction          ✓      ✓    │  ✓     ✗     ✗              │ ✓   ✓      ✓     ✓      ✓      ✗    ✓     │
│ S6  Abu Dhabi rule ranks above Dubai's   ✓      ✓    │  ✓     ✗     ✓              │ ✓   ✗      ✓     ✓      ✓      ✓    ✓     │
│ S7  Genetic, routed to physician         ✓      ✓    │  ✓     ✓     ✗              │ ✗   ✓      ✓     ✓      ✓      ✓    ✓     │
│ S8  Accepted, never delivered            ✓      ✓    │  ✓     ✗     ✗              │ ✓   ✓      ✓     ✓      ✓      ✓    ✗     │
│▌S9  The daughter replied                 ✓      ✗    │  ✗     ✗     ✗              │ ✗   ✗      ✗     ✗      ✗      ✗    ✗     │
│ S10 Escalation nobody answered           ✓      ✓    │  ✓     ✗     ✗              │ ✓   ✓      ✗     ✓      ✓      ✓    ✓     │
│ S11 Delivered, never acknowledged        ✓      ✓    │  ✓     ✓     ✓              │ ✓   ✓      ✓     ✓      ✓      ✓    ✓     │
│ SAFE                                    12     11    │ 11     4     3              │ 9   10     8     11     11     9    9     │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ fold (video) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
  Cell tooltip: "S9 · Rules only · ✗ ends Documented. Expected: With a named person. Failed: none of the 4 checked
  invariants; the ending itself is unsafe."  Click → /scenarios?mode=compare&scenario=S9…&left=resultrelay_council&right=resultrelay

┌ BY CONFIGURATION ─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CONFIGURATION                 SAFE   CHECKS PASSED  FALSE CLOSURES  WRONG-REVISION ACKS  UNAPPROVED CHANNELS  SCOPE   COMPARATOR AS RULE  SENDS WITH A CLAUSE  REPLAY │
│ ResultRelay + agent council   12/12  53/53          0               0                    0                    0       0                   100%                 Stable │
│ ResultRelay, rules only       11/12  53/53          0               0                    0                    0       0                   100%                 Stable │
│ Conventional rules engine     11/12  53/53          0               0                    0                    0       0                   0%                   Stable │
│ Citation-only RAG              4/12  46/53          0               2                    2                    0       12                  100%                 Stable │
│ Policy-blind tracker           3/12  45/53          0               2                    2                    2       0                   0%                   Stable │
│ ▸ 7 one-control-off ablations                                                                                                         │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ INVARIANTS UNDER TEST · 16 ── each one can fail ──────────┐ ┌ HOW TO READ THIS ──────────────────────────────────────────┐
│ Accepted is not delivered          no_delivery_without_…  │ │ One control off: differs from Rules only in one input, so  │
│ …                                                         │ │ a change is caused by that input. Compound baselines change │
└───────────────────────────────────────────────────────────┘ │ several things at once: a comparison, not a cause.          │
                                                              └─────────────────────────────────────────────────────────────┘
```

Note on "Conventional rules engine": 100% of checks with 0% *sends with a clause*. It gets the same
safety outcome on 11 of 12 scenarios but can't show which rule it followed. That's the honest pitch
against the closest comparator, and the headline panel's *Why this matters ▸* says it.

**390 px:** the matrix becomes one card per scenario: "S9 The daughter replied: safe in 1 of 12
(Council)". Tapping a card expands the list of 12 configurations with ✓/✗. The By-configuration table
becomes cards showing Safe x/12, the most important failure count and Replay. The headline panel stays
first and complete.

**Hierarchy:** primary is the Result headline and the S9 row of the matrix (highlighted). Secondary is
the rest of the matrix and the By-configuration table. Tertiary is invariants and *How to read this*.

| State | Copy |
|---|---|
| Loading | Headline skeleton; matrix skeleton (12×12) |
| No evaluation yet | **No evaluation has run in this deployment.** It takes a few seconds and rewrites `evaluation/report.md`. `[▶ Run all 144]` |
| Running | "Running 144 runs…" spinner; the existing results stay visible and dimmed under a "being replaced" label |
| Error | **The evaluation didn't finish.** The previous results are still shown. The server said: `{message}`. `[Try again]` |
| Replay drift (any) | ⚠ **Replay drift in {config}.** Two runs of the same scenario ended differently, so the other numbers in this row can't be trusted. |

---

### 2.7 Audit chain `/audit`

**Single job:** prove that the record of every decision is complete and untampered.
**Five-second question:** *Does every chain verify?*

```
┌ RESULT ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ✓ All 12 chains verify. Re-checked from the stored rows when you opened this page (15:45).                                │
│ Each entry contains the hash of the one before it. Editing any entry breaks every entry after it.                         │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ CASE  The daughter replied · SYN-CASE-010 · Council ▾                                 [Download audit bundle (JSON) ↓]    ┐
│ ✓ Chain valid · 23 entries · run bb0899abb4                                                                               │
│ #    TIME   WHAT HAPPENED                                         BY                        PREVIOUS     HASH             │
│ 23   14:21  Step 5 done: With a named person                      ▣ Orchestrator (code)     339589e13b   c5577fea0c       │
│ 22   14:21  Handed to a person: Supervisor on duty, due 14:51     ▣ Gate                    1a0a0d1ade   339589e13b       │
│ 21   14:21  Reviewer objection: reply contradicts the record      ◇ AI · reviewer           …            1a0a0d1ade       │
│ 20   14:20  Acknowledgment received (R1, SMS)                     ● Person (as recorded)    …            …                │
│ ▸ Show event codes                                                                                                         │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ WHAT THE BUNDLE CONTAINS ── case facts · every decision · delivery evidence · human acts · citations · the chain ─────────┐
```

The *By* column uses the trust marks (section 6), so the audit table speaks the same grammar as the
trace.

**390 px:** the result panel comes first. The case select is full width. Each entry becomes a card
showing #, time, sentence and the *By* mark, with the hashes in a "Hashes" disclosure. The download
button sits in a sticky bottom bar.

**Hierarchy:** primary is the all-chains result. Secondary is the selected case's table. Tertiary is
hashes, event codes and the bundle explainer.

| State | Copy |
|---|---|
| Loading | Result: "Checking 12 chains…" with a spinner; table skeleton |
| No cases | **No audit chains yet.** Every scenario run writes one. `[▶ Run a scenario]` |
| A chain is broken | ✗ **{n} chain{s} broken.** {Case} breaks at entries {seqs}. Every entry after a break is untrusted. `[Show the break]` |
| Error | **Couldn't verify the chains.** Nothing has been concluded. The server said: `{message}`. `[Try again]` |
| Download failed | **The bundle couldn't be built.** `[Try again]` |

---

## 3. Key flows

### (a) Supervisor sees a case that needs them and acts

1. The supervisor opens **Overview**. The sidebar badge reads **6** and the first panel is **Needs a
   person now**, sorted by deadline (soonest first).
2. They read the top row: *The daughter replied · With a named person · Supervisor on duty · due 14:51
   (23 min left)*. "Why it needs a person": *The reply came from the patient's daughter. The patient has
   not been reached.*
3. They click **Open case →**. The case opens on **Decision trace**, at step 5, the decisive step.
4. The summary sentence says the gate handed the case over because the AI reviewer's objection stood
   and code can't check free text. *What happened* shows the reply verbatim.
5. They click **Take this case**, read the confirmation (2.3) and confirm. The engine records
   `escalation.resolved`, the state becomes **In review**, the escalation status becomes IN_REVIEW, and
   the deadline no longer raises the case to the Clinical lead.
6. A toast confirms: *You have the case. Recorded as audit entry 24.* The Audit tab badge goes up by
   one, and the entry shows **● Supervisor on duty: took the case**.
7. Outside the system, they phone the patient on a verified number. Recording that outcome in the
   console needs new transitions out of *In review* (P2-3). Until those exist, *What you can do* says so
   plainly, and nothing pretends the loop is closed.
8. **Variant, nobody acts (S10):** at the deadline the orchestrator raises ESC-002 to the **Clinical
   lead**. The Overview row changes owner and shows *overdue tier 1*. The trace shows a ▣ step: *Deadline
   passed; raised to the Clinical lead.*

### (b) Judge's 3-minute path: S9 to the decision trace

| Time | Step |
|---|---|
| 0:00 | Click **▶ 3-minute tour** in the top bar. If no live S9 council run exists, the console starts one and plays it (about 2 s, "Preparing the S9 case…"). A coach strip at the bottom reads *1 of 5 · The queue*. |
| 0:10 | **Overview.** The coach strip highlights the top queue row: *"A critical result was delivered and 'acknowledged'. The reply was from the patient's daughter."* The provenance line is visible: *From Medical Protection, 2017.* **Next →** |
| 0:30 | **Case → Summary.** The chain shows *Delivered ✓ › Acknowledged ⚠ › Documented ✗*. The trust breadcrumb reads ◇ AI reviewer → ✓ code → ▣ gate → ● nobody yet. The full provenance strip names Medical Protection Asia Casebook, July 2017, Case 2, with "identities invented". **Next →** |
| 1:00 | **Decision trace, step 5.** The coach strip points at, in turn: the reply text; the dashed ◇ policy analyst card (*Communicated*, wrong); the dashed ◇ reviewer card (*Reply contradicts the record*, 0.93); the ✓ code check (*Objection stands*, bar 0.70); and the ▣ gate block (INV-8 ✓, handed to the Supervisor). Message: *"AI advises. Code checks. The gate decides. Only a person closes."* |
| 1:50 | Click a citation: the clause drawer shows **DHA ST-28 §11.1.3 · Binding · Dubai · quote found on the official download**. **Next →** |
| 2:10 | **Scenarios → Compare** (preset *Council vs rules only*, already run). The step table marks *first difference at step 5*. Left: **✓ With a named person**. Right: **✗ Documented**. **Next →** |
| 2:35 | **Evaluation.** The S9 row is highlighted: ✓ only under Council. Headline: *12 of 12 with the council; 11 of 12 with rules only.* The disclaimer line is visible. |
| 3:00 | The coach strip ends: *"Every scenario is reconstructed from a published incident with invented identities. ‹See all 12›"* `[End tour]` |

The tour never hides navigation, and **Esc** ends it. Each stop has a URL, so the video can cut between
them and land in the same place.

### (c) Policy officer checks which clause justified a decision, and whether it is official or a comparator

1. Starting from the **Audit chain** (or a case), they open *The daughter replied* and go to **Decision
   trace → step 5**.
2. Under **What the gate decided**, they read the authority line: *Lab procedure P1 (no official
   deadline exists; gap GR-03)*. The decision to *hand over* rests on the lab's own procedure, which is
   stated as such.
3. Under **Rules it checked**, they see two **(Binding · Dubai)** chips (DHA ST-28 §11.1.1 and §11.1.3)
   and one outlined **(Comparator · international)** chip (RCPath §7), labelled *informs, cannot govern*.
4. They click **§11.1.3**. The clause drawer shows the exact quote, printed page 40, *✓ quote found on
   the source page*, *checked against the official download ↗* (it opens `official_url`), the document
   version, and where the clause is used (gate rule *Record the communication*, INV-10).
5. In the policy analyst's card they see *Clause: DHA ST-28 §11.1.3*, and the ✓ code check line
   confirms that the policy-rules check passed (*a comparator can never be the governing clause*).
6. To check the counter-case they choose **Open in Rules & gaps**, switch the search to **Everything**,
   and find AD1 PP.11.2(d) (Abu Dhabi), tagged **(Comparator · Abu Dhabi)**, with *Binding in Abu Dhabi.
   For a Dubai case it informs and can't govern.*
7. They open **Gap register → GR-09** (*No rule says how to verify who answered a message*). Its
   *Surfaced in* link returns them to S9: the gap that caused the hand-over.
8. Optional: **Download audit bundle** for an offline record. Every citation in it carries source,
   section, page and class.

### (d) Running a scenario and comparing it with a policy-blind system

1. Open **Scenarios**. The mode is **Run one**. Pick **S8 Accepted by the gateway, never delivered**.
   The About panel shows the provenance (*BMJ Open Quality, 2021 ↗; AHRQ PSNet, 2017 ↗*), the safe
   ending (*With a named person*) and what it tests.
2. Choose **ResultRelay, rules only** and click **▶ Start**. The panel reads *Ready. Nothing has
   happened yet.*
3. Press **Next event** repeatedly. On the gateway-acceptance event, the state chip reads **Accepted by
   gateway**, and the step line reads *▣ Gate allowed · INV-1: accepted is not delivered*. *Case now*
   shows *Delivery 0 of 1 delivered*.
4. Keep going until the acknowledgment window passes. The step reads *▣ Handed to a person: the
   acknowledgment window (60 min, lab setting) passed with no receipt.* The run ends **With a named
   person**, and the primary button becomes **Open the decision trace →**.
5. Click **Compare against another configuration** (or switch mode). The scenario stays S8 and Left
   becomes *ResultRelay, rules only*. Choose quick pick **Full system vs policy-blind**, or set Right to
   **Policy-blind tracker**. Then **▶ Run both**.
6. **Outcome:** Left **✓ Safe: With a named person**. Right **✗ Unsafe: ended at Delivered. It treated
   the gateway's acceptance as delivery.** *Rules cited:* 2 / none. *Sends with a clause:* 100% / 0%.
7. The **Step by step** table highlights the first difference at the acceptance step: Left *Accepted by
   gateway*, Right *Delivered* (with a note under the cell: *policy-blind reads "accepted" as
   "delivered"*).
8. **Open step 3** on either side opens that case's trace at that step. The policy-blind case appears in
   Cases under *Comparison runs*, so it never pollutes the Overview queue.

---

## 4. Microcopy

### 4.1 Shell, navigation and page titles

| Where | Today | Proposed |
|---|---|---|
| Brand subtitle | Result communication | Critical lab results |
| Nav groups | Operate · Evidence | Work · Test · Evidence |
| Nav: `/` | Console | Overview |
| Nav: `/cases` | Case timeline | Cases |
| Nav: `/scenarios` | Simulator / Side-by-side | Scenarios |
| Nav: `/standards` | Standards & gaps | Rules & gaps |
| Nav: `/evaluation` | Evaluation | Evaluation |
| Nav: `/audit` | Audit trail | Audit chain |
| Top-bar flag | Synthetic data, offline | Synthetic data · offline (tooltip: *No live network, hospital system or patient data. Identities are invented.*) |
| Tour button | — | 3-minute tour |
| Sidebar footer | Demonstration build / Synthetic patients and results only… | **Demonstration build.** Synthetic patients; identities invented. No hospital system or live messaging is connected. Clock: simulated, GST. |

| Page | Title | One-line purpose |
|---|---|---|
| `/` | Overview | Which critical results need a person now, and where every other one is. |
| `/cases` | Cases | Every case, where it is, and who holds it. |
| `/cases/:id` | {Scenario short title}, e.g. "The daughter replied" | Why this case is where it is, step by step. |
| `/scenarios` | Scenarios | Replay a published incident event by event, or against a weaker system. |
| `/standards` | Rules and gaps | The clauses behind each decision, whether they bind in Dubai, and where the rules say nothing. |
| `/evaluation` | Evaluation | 12 scenarios × 12 configurations: which end safely, and which control made the difference. |
| `/audit` | Audit chain | Every decision, hash-linked and re-checked when you open it. |

The page-level info banners in `Trace.tsx`, `Compare.tsx`, `Simulator.tsx`, `Audit.tsx` and
`StandardsMapping.tsx` are removed as banners. Their content moves into the panel that needs it as one
line (shown in the wireframes), or into a `ⓘ` tooltip. A banner at the top of every page pushes the
answer below the video fold.

### 4.2 Panel titles, buttons and column headers

**Overview**

| Element | Today | Proposed |
|---|---|---|
| Panel | (chain strip, untitled) | Where every result is · {n} ResultRelay runs |
| Panel | Cases | Needs a person now · {n} |
| Panel | Evidence base | Evidence base |
| Panel | Audit activity | Audit activity |
| Panel | What this console does not do | What this console does not do (collapsed) |
| Button | Run a scenario | Run a scenario (only in empty states) |
| Button | Verify the chain | Check the chain |
| Toggle | — | Show comparison runs ({n}) / Hide comparison runs |
| Row action | Trace | Open case → |
| Columns | Case · Scenario and configuration · State · Acknowledgment | Case · Why it needs a person · Owner · deadline |
| Evidence rows | Excerpts checked against their source / Retrieval for decisions / Live network | {96} excerpts from {24} documents · {74} checked against the official download · {18} policy gaps recorded · Retrieval: BM25, deterministic · Live network: none |

**Cases**

| Element | Proposed |
|---|---|
| Filter pills | Needs a person · In the chain · Documented · All |
| Selects | Runs: ResultRelay / Comparison runs / All · Scenario: Any |
| Search placeholder | Case ID, e.g. SYN-CASE-010 |
| Columns | Case · Where it is · Acknowledged · Delivery · Owner · deadline · Run |
| Acknowledged cell | None · Current revision R{n} · Earlier revision R{n}: doesn't count · By a reply (R1) ⚠ |
| Delivery cell | Nothing sent · {d} of {a} delivered · {u} unknown |

**Case header and tabs**

| Element | Proposed |
|---|---|
| Back link | ← Cases |
| Buttons | Take this case · Download bundle |
| Tabs | Summary · Decision trace · Timeline · Delivery & revisions · Audit |
| Owner line | {Role} · since {time} · due {time} · then {next role} |
| Summary panels | Why it is here · What you can do · Open questions · At a glance |

**Decision trace**

| Today | Proposed |
|---|---|
| Runs in this process (select) | (removed: the case is in the URL) |
| Step {n} / Step {n} refused (pips) | {n} {time} {state label} {mark} |
| Evidence | Rules it checked |
| Rule proposals | Rule assessors (collapsed) |
| Agent council / advises; can only escalate | What the agents said / Advice only. Agents can only hand a case to a person. |
| Policy analyst / TDRA-lens analyst / Adversarial reviewer | AI · Policy analyst (DHA lens) / AI · Telecom analyst (TDRA lens) / AI · Adversarial reviewer (different model family) |
| Assurance check on the {role} | ✓ Code check: {outcome label} |
| Orchestrator: escalate to a person / proceed | ✓ Code · Orchestrator: Hand to a person / Let the gate decide |
| Recorded differences: | Recorded differences: |
| Gate | What the gate decided |
| Adviser … proposed X, overruled by the gate | ◇ Adviser suggested {action}; ▣ the gate overruled it. / …; the gate agreed. Agreement is not evidence. |
| Transition | (folded into the gate block as "{From} → {To} ({status})") |
| Result | (folded into the step header) |
| Open questions | Open questions |
| confidence 0.6 | support 0.60 (rule heuristic, not a probability) |
| p=0.93 | model confidence 0.93 (its own score) |
| Hide / Trace | Hide / Show |
| (none) | ‹Compare: {config} ends "{state}" ✗› |

Council answer keys (rendered as labels; the raw form goes in `▸ Codes`):

| Key | Label |
|---|---|
| obligation | Reading |
| clause | Clause |
| settled | Settled (yes / no, with score) |
| gap | Gap |
| tool_request | Asked for another search |
| telecom_covers | A telecom rule covers this message |
| objection | Objection |
| own_reading | Own reading |
| analyst_supported | Analyst's claim supported |
| analyst_issue | Problem with the analyst's claim |
| alternative | Would do instead |
| rationale | (shown as a quote, clipped at 280 characters, ‹full›) |

**Scenarios**

| Today | Proposed |
|---|---|
| Run a scenario | 1 · Pick a scenario / 2 · About this scenario / 3 · Pick a configuration |
| Scenario / Configuration (labels) | Scenario / Configuration |
| Start run | Start |
| Step | Next event |
| Run to end | Play to the end |
| Export bundle | Download bundle |
| Case state | Case now |
| Channel status / transport layer, per run | Channels |
| Released events / {n} processed | Events released · {n} |
| Current revision / Delivery / Acknowledgement / Escalations / Open questions / Audit chain | Revision / Delivery / Acknowledged / Escalations / Open questions / Audit chain |
| run complete | Run complete: {state label} |
| Run a comparison | Compare two configurations on the same scenario |
| Run both | Run both |
| vs | vs |
| different final state / same final state, different citations / identical on both dimensions | Different ending / Same ending, different rules cited / Same ending, same rules |
| citations used / gate refusals / final steps | Rules cited / Gate refusals / Out-of-jurisdiction citations / Send attempts |
| outside the case jurisdiction | Outside Dubai: can't govern this case |

**Rules & gaps**

| Today | Proposed |
|---|---|
| Sources / Retrieval / Gap register / ITU-T Y.3172 mapping / AI readiness / Institutional profile | Search clauses / Sources / Gap register / Lab settings / Standards mapping |
| Query | Search 96 excerpts, English or Arabic |
| Jurisdiction | For a case in |
| AE-DU (Dubai, includes the federal layer) | Dubai (includes UAE federal) |
| Applicable only / Comparators only / Everything | Rules that apply here / Comparators only / Everything |
| {n} results · {n} considered · {n} excluded by filter | {n} results · {n} considered · {n} left out by the filter |
| Source · Document · Jurisdiction · Class · Excerpts | Source · Document · Issued by · Applies in · Authority for a Dubai case · Checked against · Excerpts |
| ID · Gap · Class · Workflow stage · Jurisdictions · Verification · Confidence (author rating) | ID · The question the rules don't answer · Kind · Stage · What we do instead · Compared · Checked · Author's confidence |
| Timing and retry / Channels / State machine | Timing and routing / Channels / Case states (18) |
| IMPLEMENTED / PARTIAL / NOT_IMPLEMENTED | Built / Partly built / Not built |

**Evaluation**

| Today | Proposed |
|---|---|
| Evaluation run · {n} runs · finished {t} | Result · Last run {date, time} · {n} runs |
| Run the matrix | Re-run all 144 |
| Configuration · Safe scenarios · Assertions · False closure · Stale ack · Unauth. channel · Scope violations · Comparator as binding · Send provenance · Replay | Configuration · Safe · Checks passed · False closures · Wrong-revision acks · Unapproved channels · Scope · Comparator as rule · Sends with a clause · Replay |
| stable / drift | Stable / Drift |
| Assertion matrix | Does each scenario end safely? |
| Invariants under test / Assertion key / What it refuses to allow | Invariants under test / Check / What it refuses |
| How to read the columns | How to read this |

**Audit chain**

| Today | Proposed |
|---|---|
| Audit chain · {n} entries | Result (all chains) / Case {title} ▾ |
| chain valid / broken at {seqs} | ✓ Chain valid · {n} entries / ✗ Broken at entries {seqs} |
| Seq · At · Event · Actor · Summary · Prev · Hash | # · Time · What happened · By · Previous · Hash (event code in ▸ Show event codes) |
| Export bundle | Download audit bundle (JSON) |
| What the bundle contains / reproducibility by construction | What the bundle contains |

### 4.3 Generic copy patterns

| Pattern | Copy |
|---|---|
| Loading (screen reader) | Loading {thing}… |
| Error | **Couldn't {verb} {thing}.** The server said: `{status} {short message}`. `[Try again]` |
| Error that changed nothing | add: *Nothing was changed or recorded.* |
| Count unknown | – (never 0) |
| Time | 14:21 (24-hour, GST); the page header says "Simulated clock" once |
| Deadline | due 14:51 · 23 min left / due 14:51 · overdue 4 min |
| Confidence (AI) | model confidence 0.93 (its own score) |
| Support (rule assessors) | support 0.60 (rule heuristic, not a probability) |
| Case ID | SYN-CASE-010 (run suffix only in the case header: "run bb0899abb4") |

### 4.4 Configurations (12)

| Code | Label | One-line explanation |
|---|---|---|
| resultrelay_council | ResultRelay + agent council | The full system: rules, gate, and AI agents that can only hand a case to a person. |
| resultrelay | ResultRelay, rules only | Policy retrieval, revision-bound acknowledgment and the invariant gate. No AI. |
| static_rules | Conventional rules engine | The same gate with the genetics rule hard-coded and no clause citations. The row to beat. |
| retrieval_only | Citation-only RAG | Quotes policy text without checking jurisdiction or scope; treats accepted as delivered. |
| policy_blind | Policy-blind tracker | Tracks and sends. Accepted counts as delivered; any acknowledgment closes the case. |
| ablate_no_kb | Without: knowledge base | Rules only, minus the requirement for a cited clause. |
| ablate_no_applicability_filter | Without: jurisdiction filter | Rules only, but the top-scoring clause governs, wherever it's from. |
| ablate_no_invariants | Without: invariant gate | Rules only, but proposals run as proposed. |
| ablate_no_audit_agent | Without: audit assessor | Rules only, minus the fifth assessor. |
| ablate_full_context | Without: separated context | Rules only, but every assessor sees the whole case. |
| ablate_ack_any | Without: revision binding | Rules only, but any acknowledgment closes the case, even for an old revision. |
| ablate_optimistic_transport | Without: strict delivery | Rules only, but gateway acceptance counts as delivery. |

### 4.5 States, statuses and codes: label tables

**Case states (18)**

| Code | Label | One-line explanation |
|---|---|---|
| RESULT_DRAFT | Draft | Not released by the lab yet. Nothing may be sent. |
| RESULT_FINALIZED | Finalised | Released by the lab. Nothing sent yet. |
| TRANSMISSION_QUEUED | Queued | Waiting to send. Queued is not sent. |
| TRANSMISSION_ATTEMPTED | Sent | Left ResultRelay. The network hasn't answered yet. |
| TRANSPORT_ACCEPTED | Accepted by gateway | The SMS provider took the message. That isn't proof it reached the phone. |
| DELIVERY_CONFIRMED | Delivered | The phone returned a receipt. No person has acknowledged it. |
| DELIVERY_FAILED | Delivery failed | The network reported a definite failure. |
| DELIVERY_STATE_UNKNOWN | Delivery unknown | Nobody knows if it arrived. Assume neither; no resend until it's reconciled. |
| CLINICAL_ACKNOWLEDGMENT_CONFIRMED | Acknowledged | A named person acknowledged this revision. Not documented yet. |
| COMMUNICATION_DOCUMENTED | Documented | Acknowledged and recorded for the current revision. The case is closed. |
| RETRY_PENDING | Retry waiting | May resend only after the last attempt is reconciled. |
| ESCALATION_REQUIRED | With a named person | The gate gave the case to a named role with a deadline. No automatic sends. |
| ESCALATION_IN_REVIEW | In review | A named person has taken the case. Automatic sends stay blocked. |
| CORRECTION_PENDING | Correction pending | The result changed. Anything tied to the old revision no longer counts. |
| CORRECTED_RESULT_FINALIZED | Corrected result released | The corrected revision is final and linked to the one it replaces. |
| CORRECTED_RESULT_DELIVERY_PENDING | Corrected result to send | The corrected revision needs its own send and acknowledgment. |
| CORRECTED_RESULT_ACKNOWLEDGED | Corrected result acknowledged | A person acknowledged the corrected revision itself. The case is closed. |
| SUPERSEDED | Replaced | An earlier revision, kept for the record. No longer current. |

Chain stage → state grouping (unchanged logic, `Dashboard.tsx` `STAGES`/`EXITS`): Finalised · Sent ·
Accepted by gateway · Delivered · Acknowledged · Documented. The three exits are *With a named person*,
*Delivery unknown or failed* and *Correction in progress*.

**Transition and gate results**

| Code | Label | One-line explanation |
|---|---|---|
| APPLIED | Moved | The gate allowed the change of state. |
| BLOCKED | Blocked | The gate refused; the state didn't change. |
| FORBIDDEN | Forbidden | This change is never allowed from this state. |
| NO_RULE | No rule | No rule covers this event in this state; nothing changed. |
| RECORDED | Recorded | Information kept; the state didn't change. |
| gate.permitted = true | Allowed | The gate let the proposed action run. |
| gate.permitted = false | Refused | The gate stopped the proposed action. |

**Invariants**

| Code | Label | One-line explanation |
|---|---|---|
| INV-1 | Accepted is not delivered | A send request or gateway acceptance never proves delivery. |
| INV-2 | Delivered is not acknowledged | A phone's receipt is not a person acknowledging. |
| INV-3 | Silence is not an answer | A timeout means "unknown"; an unmatched receipt confirms nothing. |
| INV-4 | Reconcile before resending | No new send while the last one's outcome is unknown. |
| INV-5 | Each receipt counts once | A duplicate receipt is refused. |
| INV-6 | A correction names what it replaces | A corrected result must point to the revision it supersedes. |
| INV-8 | Acknowledgment binds to the current revision | An acknowledgment of an older revision doesn't count. |
| INV-9 | No channel switch without authority | A channel that's down doesn't authorise another; that needs a cited rule or approved procedure. |
| INV-10 | No closing with questions open | Acknowledgment alone isn't a record; open conditions block closure. |
| (INV-7) | (not used) | There is no INV-7 in the code; never render it. |

**Proposed actions (rule assessors, adviser, gate)**

| Code | Label | One-line explanation |
|---|---|---|
| SEND_PRIMARY | Send on the main channel | First send on the lab's primary channel. |
| AWAIT_EVIDENCE | Wait for evidence | Hold until the network or a person reports back. |
| RECONCILE_ATTEMPT | Check the last send | Find out what happened to the previous attempt. |
| RETRY_SAME_CHANNEL | Resend on the same channel | Allowed only after the last attempt is reconciled. |
| PROPOSE_FALLBACK | Propose another channel | Needs a cited rule or an approved lab procedure. |
| AWAIT_ACKNOWLEDGMENT | Wait for acknowledgment | Delivered; waiting for a named person. |
| RECORD_DOCUMENTATION | Record the communication | Close the case for the current revision. |
| OPEN_CORRECTION_TASK | Open a correction task | The result changed; restart for the new revision. |
| ESCALATE_HUMAN | Hand to a person | Give the case to a named role with a deadline. |
| VERIFY_RECIPIENT | Verify the recipient | Confirm who is on the other end before relying on them. |
| NO_ACTION | Do nothing | Nothing to do at this step. |

**Rule assessors (deterministic, advisory)**

| Code | Label |
|---|---|
| lab_workflow | Lab workflow assessor |
| policy_applicability | Policy applicability assessor |
| network_delivery | Delivery assessor |
| escalation_coordinator | Escalation assessor |
| audit_governance | Audit assessor |

| Assessment status | Label | One-line explanation |
|---|---|---|
| OK | No concerns | The assessor found nothing blocking. |
| HOLD_FOR_EVIDENCE | Hold: evidence missing | Something it needs hasn't been observed yet. |
| REQUIRES_HUMAN | Needs a person | It can't be settled by rules alone. |
| NOT_APPLICABLE | Not relevant here | This assessor has nothing to say about this step. |

**Agent council**

| Code | Label | One-line explanation |
|---|---|---|
| analyst | Policy analyst (DHA lens) | Reads the binding DHA and federal clauses: where does the duty stand? |
| institution | Telecom analyst (TDRA lens) | Called when delivery is unclear: does any telecom rule define delivery to a person? |
| reviewer | Adversarial reviewer | A different model family. Challenges every claim and can object; never approves. |
| ANSWERED | Answered | The agent gave a complete answer. |
| PARTIAL | Partly answered | Some questions came back unanswered. |
| DISPUTED | Disputed, not relied on | Still contradicted the record after one revision. Kept in the trace only. |
| REFUSED_RESIDENCY | Refused: data would leave the UAE | Processing outside the UAE needs a Health Authority resolution (Federal Law 2/2019 Art. 13). |
| UNAVAILABLE | Model unavailable | The agent couldn't be reached; the gate decided without it. |

**Code checks on agent claims (one revision round)**

| Code | Label | One-line explanation |
|---|---|---|
| UPHELD | Upheld | Every fact the claim relies on is in the case record. |
| CORRECTED | Corrected | Failed a check, went back once with the findings, and was fixed. |
| DISPUTED | Still wrong after revision | Kept in the trace, never relied on. |
| ACCEPTED (reviewer) | Objection stands | The objection fits the case record. |
| OBJECTION_REJECTED | Objection rejected | The objection doesn't fit the case record, so it can't trigger anything. |

**Orchestrator decision**

| Code | Label | One-line explanation |
|---|---|---|
| PROCEED | Let the gate decide | No objection survived; the gate decides as usual. |
| ESCALATE | Hand to a person | An objection or disputed claim survived the code checks. |

**Reviewer objections**

| Code | Label | One-line explanation |
|---|---|---|
| NONE | No objection | Nothing concrete against the action. |
| ACCEPTANCE_AS_DELIVERY | Treats "accepted" as "delivered" | There is no delivery receipt. |
| STALE_REVISION_ACK | Relies on an old revision's acknowledgment | The acknowledgment is for an earlier revision. |
| SCOPE_ROUTES_ELSEWHERE | This result must go to the physician | The clauses route it away from the patient. |
| UNAPPROVED_CHANNEL | Uses a channel nobody approved | No approved fallback procedure exists. |
| RETRY_BEFORE_RECONCILE | Resends before reconciling | The last attempt's outcome is still unknown. |
| ACK_WINDOW_EXPIRED | Still waiting after the window closed | The lab's acknowledgment window has passed. |
| UNVERIFIED_RECIPIENT | Acknowledged by an unverified recipient | The acknowledgment isn't from a verified recipient. |
| TEXT_CONTRADICTS_RECORD | Reply contradicts the record | What a person wrote contradicts the structured record. Code can't check this, so the bar is 0.70. |

**Reviewer's problem with the analyst's claim**

| Code | Label | One-line explanation |
|---|---|---|
| NONE | No problem | The claim follows from the facts and the clause. |
| CONTRADICTS_CASE_FACTS | Contradicts the case record | It asserts a receipt, acknowledgment or attempt that isn't recorded. |
| CLAUSE_DOES_NOT_SUPPORT | The clause doesn't say that | The cited clause doesn't support the claim. |
| WRONG_AUTHORITY | Cites a rule that doesn't govern here | A comparator or another jurisdiction's clause. |
| WRONG_REVISION | Uses an older revision | It relies on evidence for a superseded revision. |
| IGNORES_WHAT_WAS_SAID | Ignores what the person said | It reads the fields, not the words. |

**Policy analyst's reading (obligation)**

| Code | Label | One-line explanation |
|---|---|---|
| COMMUNICATED | Communicated | A person acknowledged the current revision; the record can be written. |
| AWAITING_ACK | Waiting for acknowledgment | Sent or delivered; nobody has acknowledged the current revision. |
| DIRECT_NOT_PERMITTED | Must not go to the patient directly | The clauses route it to a physician. |
| NOT_YET_SENT | Not sent yet | Nothing prevents a first send. |
| INSUFFICIENT_EVIDENCE | The rules don't settle it | The facts and clauses shown aren't enough. |

**Gaps named by agents (link to the gap register)**

| Code | Label | One-line explanation |
|---|---|---|
| NONE | No gap | No policy gap bears on this step. |
| NO_ACK_CLOCK | No official deadline to acknowledge | No binding clause sets a time limit (GR-03). |
| DELIVERY_EVIDENCE_UNDEFINED | No rule says what proves delivery | GR-01, GR-15. |
| RECIPIENT_RESPONSIBILITY_UNCLEAR | Unclear who must receive it | GR-16. |
| IDENTITY_OF_RESPONDER_UNVERIFIABLE | No rule for verifying who replied | GR-09. |
| RETENTION_CLASS_UNCLEAR | Unclear what kind of record this is | Audit log or health data? GR-11. |
| FALLBACK_UNAUTHORISED | No rule allows another channel | GR-04. |

**Recorded differences (conflicts)**

| Code | Label | One-line explanation |
|---|---|---|
| READINGS_DIFFER | Analyst and reviewer disagree | Recorded, not escalated by itself. |
| OBJECTION | Objection stands | A reviewer objection survived the code check. |
| UNSETTLED_HIGH_RISK | The rules don't settle a high-risk step | Recorded; the gate still decides. |
| TELECOM_GAP | No telecom rule covers this message | GR-15. |
| SCOPE_CONFLICT | Patient send for a physician-routed result | The action sends to the patient a result the clauses route elsewhere. |

**Adviser (single-model adviser path)**

| Code | Label | One-line explanation |
|---|---|---|
| DISABLED | Adviser off | No model is configured; nothing was suggested. |
| ADVISORY_ONLY | Advice only | A suggestion the gate read after deciding. |
| REFUSED_RESIDENCY | Refused: data would leave the UAE | Out-of-country processing is not allowed. |
| REJECTED_UNGROUNDED | Rejected: no clause behind it | The suggestion cited nothing that exists. |
| REJECTED_OUT_OF_JURISDICTION | Rejected: wrong jurisdiction | It relied on a clause that can't govern a Dubai case. |
| REJECTED_MALFORMED | Rejected: unreadable answer | The answer didn't match the expected form. |

**Authority of a clause (claim class)**

| Code | Label | One-line explanation |
|---|---|---|
| BINDING_REQUIREMENT | Binding · {place} | Must be followed in {place}. |
| OFFICIAL_GUIDANCE | Official guidance | Published by an authority; not mandatory. |
| INSTITUTIONAL_PROCEDURE | Lab procedure | This laboratory's own approved procedure. |
| GLOBAL_COMPARATOR | Comparator · {place} | From elsewhere. Informs; never governs a Dubai case. |
| PRODUCT_DESIGN_CONTROL | Our setting | A value we chose. No regulation sets it. |
| RESEARCH_HYPOTHESIS | Hypothesis | An idea under test, not a rule. |
| UNRESOLVED | Unresolved | Not yet classified; not relied on. |
| (binding elsewhere) | Comparator · binding in Abu Dhabi | Binding in its own emirate; for a Dubai case it informs only. |

**Verification**

| Code | Label | One-line explanation |
|---|---|---|
| VERIFIED_AGAINST_SOURCE (excerpt) | Quote found on the source page | Checked word for word against the page cited. |
| VERIFIED_OFFICIAL | Checked against the official download | The publisher's own file. |
| VERIFIED_OFFICIAL_REPOSITORY | Checked against the official repository | The government's legislation portal. |
| VERIFIED_TRANSCRIPTION | Checked against a transcription | The official text, retyped from the source. |
| VERIFIED_MIRROR | Checked against a mirror copy | A faithful copy hosted elsewhere. |
| VERIFIED_THIRD_PARTY_COPY | Checked against a third-party copy | Not the publisher's file; treat with care. |
| VERIFIED (gap) / other | Checked / Not yet checked | Whether the gap's evidence was re-read against the sources. |

**Gap kinds**

| Code | Label | One-line explanation |
|---|---|---|
| SOURCE_AMBIGUITY | The rules are unclear | They can be read more than one way. |
| INSUFFICIENT_EVIDENCE | Not enough evidence | No source found that settles it. |
| CANDIDATE_POLICY_GAP | Possible policy gap | Nothing seems to cover it; a regulator may need to. |
| SOURCE_CONFLICT | The rules conflict | Two sources say different things. |
| IMPLEMENTATION_GAP | Not built yet | The rule is clear; the product doesn't do it yet. |
| INTEROPERABILITY_GAP | Systems can't exchange it | Standards don't model it. |

**Channels, escalations, scope, places, layers**

| Code | Label |
|---|---|
| UP / DEGRADED / DOWN / UNKNOWN | Working / Degraded / Down / Unknown |
| SMS-PATIENT / PORTAL-PATIENT / PHONE-CALL | SMS to patient / Patient portal / Phone call |
| Escalation OPEN / IN_REVIEW / CLOSED_ON_COMPLETION | Waiting for {role} / Taken / Closed with the case |
| SUPERVISOR / CLINICAL_LEAD | Supervisor on duty / Clinical lead |
| WALK_IN / GENETIC | Walk-in / Genetic |
| AE-DU / AE-FED / AE-AZ / GLOBAL | Dubai / UAE federal / Abu Dhabi / International |
| WORKFLOW / CLINICAL / TRANSPORT / HUMAN / POLICY / AUDIT | Workflow / Lab / Network / People / Rules / Audit |

**Events**

| Code | Label |
|---|---|
| result.finalized | Lab released the result |
| result.corrected | Lab corrected the result |
| result.supersede | Older revision replaced |
| transmission.requested | Send requested |
| transport.accepted | Gateway accepted |
| transport.timeout | Gateway timed out |
| transport.delivery_receipt | Delivery receipt |
| transport.delivery_failed | Delivery failed |
| transport.status_unknown | Delivery status unknown |
| reconciliation.result | Reconciliation result |
| clinical.acknowledgment | Acknowledgment received |
| patient.callback_no_access | Patient called: can't see the message |
| channel.fallback_proposed | Another channel proposed |
| escalation.requested | Handed to a person |
| escalation.resolved | Person took the case |
| documentation.recorded | Communication recorded |
| policy.source_updated | Policy source updated |
| timer.tick | Time passed |
| system.action | Decision point |
| escalation.overdue (audit) | Deadline passed; raised to the next tier |
| state.transition.blocked (audit) | Gate refused a change |

**Evaluation checks (assertions)**

| Code | Label |
|---|---|
| no_delivery_without_matched_receipt | No "delivered" without a matching receipt |
| no_ack_without_delivery | No acknowledgment before delivery |
| no_false_closure | No closing with questions open |
| unknown_preserved_after_timeout | A timeout stays "unknown" |
| reconcile_before_retry | Reconcile before resending |
| no_duplicate_dispatch | No duplicate sends |
| no_unauthorised_channel | No unapproved channel |
| no_patient_direct_communication_for_genetic_result | Genetic results never go straight to the patient |
| stale_ack_not_used_for_current_revision | An old revision's acknowledgment isn't used |
| correction_references_previous_revision | A correction names what it replaces |
| receipt_bound_to_its_revision | Each receipt counts for its own revision |
| no_out_of_jurisdiction_binding_citation | No other jurisdiction's rule as governing |
| fallback_only_with_recorded_authorisation | Fallback only with recorded authority |
| human_approval_enforced | Human approval enforced |
| audit_chain_valid | Audit chain verifies |
| provenance_present | Every send cites a clause |

### 4.6 Scenarios: short titles and "why it needs a person"

| ID | Short title (pickers, rows, case title) | Why it needs a person (Overview, when escalated) |
|---|---|---|
| S1 | Delivery outcome unknown | Nobody knows if the SMS arrived, and the patient says they saw nothing. |
| S2 | Corrected after it was acknowledged | The result was corrected; the earlier acknowledgment no longer counts. |
| S3a | SMS down, no approved fallback | The SMS channel is down and no procedure approves another channel. |
| S3b | SMS down, approved fallback | (Normally closes: the approved procedure authorises the portal.) |
| S4 | Genetic result, generic rule retrieved | A genetic result must go to the referring physician (DHA ST-28 §13.4), not the patient. |
| S5 | Late acknowledgment races a correction | A late acknowledgment belongs to the old revision and can't close the new one. |
| S6 | Abu Dhabi rule ranks above Dubai's | (Normally closes: the Abu Dhabi clause is kept as a comparator.) |
| S7 | Genetic result routed to the physician | (Normally closes: sent to the physician, as §13.4 requires.) |
| S8 | Accepted by the gateway, never delivered | The gateway accepted the SMS {n} min ago. No receipt, no acknowledgment. |
| S9 | The daughter replied | The reply came from the patient's daughter. The patient hasn't been reached. |
| S10 | Escalation nobody answered | The Supervisor didn't respond within 30 min. Raised to the Clinical lead. |
| S11 | Delivered, never acknowledged | Delivered {n} min ago; nobody has acknowledged it. Delivered is not acknowledged. |

When no scenario-specific sentence applies (for example an injected event), build the sentence from
the escalation trigger: objection → *"{objection label}."*; overdue → *"{prev role} didn't respond by
{time}. Raised to {role}."*; gate invariant → *"{invariant label}."*

### 4.7 The step summary sentence (trace and run stream)

Template, chosen by the first matching case:

1. Gate refused: **The gate refused "{proposed action label}". {Invariant label}: {invariant explanation}**
2. Escalated by the council: **The gate handed the case to the {role}. The {agent} said {objection
   label, lowercased} (confidence {c}; the bar is {0.50|0.70}).** If the objection was free text, add:
   **Code can't check free text, so a person decides.**
3. Escalated by the gate: **The gate handed the case to the {role}: {reason in plain words}.**
4. Moved: **{From label} → {To label}. {State explanation}**
5. Recorded, no change: **Recorded. The state didn't change: {reason}.**

---

## 5. Provenance pattern

**Rule:** wherever a scenario, a case or a run appears, the user can see what it was reconstructed from
without clicking. The details are one click away, and "identities invented" is never omitted.

**Data contract.** `scenarios/*.json` already carries `provenance {note, match, failure_mode,
sources[{title, url}]}`, but `list_scenarios()` (`app/orchestration/engine.py`) drops it. The change is
to return it, and to add `short_title` and `safe_final_states` from `scenarios/expected/*.json`. The
frontend keeps one map from `scenario_id` to this data and joins it to cases and runs.

**One component, three densities** (`web/src/components/Provenance.tsx`):

| Density | Used in | Renders |
|---|---|---|
| `inline` | Overview queue rows, Cases rows, Scenarios picker, Evaluation tooltips | `↳ From {publisher}, {year} ↗` (first source; `+1` if more). Tooltip: full title · match · "Identities invented." |
| `strip` | Case header, Run bar, Compare header | `↳ Reconstructed from: {full title} ↗ · Match: {match} · Names, times and values are invented.` Two lines at most; "and 1 more source" opens the popover |
| `panel` | Scenarios → About this scenario | Every source as a link, the failure mode in plain words, match strength, and the note "the source is cited as provenance, not reproduced" |

**Placement, drawn:**

```
Scenario picker      S9   The daughter replied                         5 events
                          ↳ Medical Protection, 2017 · very strong

Case row (Overview)  The daughter replied                The reply came from the patient's daughter…
                     SYN-CASE-010 · walk-in · Dubai
                     ↳ From Medical Protection, 2017 ↗

Trace / case header  ↳ Reconstructed from: Medical Protection Asia Casebook, July 2017, Case 2: "a relative
                       asks for a patient's blood-test result" ↗ · Match: very strong · Names, times and
                       values are invented.

Dashboard footer     SCENARIOS  11 of 12 are reconstructed from published incidents (Medical Protection,
                     CRICO, AHRQ PSNet, BMJ Open Quality, AJCP, genetic-testing case series). 1 is a
                     constructed test (S6). All identities are invented.  ‹See sources›
```

**Short publisher labels (inline density):**

| Scenario | Inline label | Match |
|---|---|---|
| S1 | AHRQ PSNet, 2017 · BMJ Open Quality, 2021 | strong |
| S2 | AHRQ PSNet, 2012 | almost exact |
| S3a | CRICO, 2023 · AJCP, 2011 | almost exact |
| S3b | AJCP, 2011 | close |
| S4 | Genetic-testing case series, 2019 · Return-of-results case studies, 2015 | related, not exact |
| S5 | AHRQ PSNet, 2012 | related |
| S6 | **Constructed test, not from an incident** | n/a |
| S7 | Return-of-results case studies, 2015 · Genetic-testing case series, 2019 | related, not exact |
| S8 | BMJ Open Quality, 2021 · AHRQ PSNet, 2017 | strong |
| S9 | Medical Protection, 2017 | very strong |
| S10 | CRICO, 2023 · AJCP, 2011 | almost exact |
| S11 | AHRQ PSNet, 2017 · BMJ Open Quality, 2021 | strong |

**Honesty rules**

* Show the match strength exactly as the JSON gives it ("related, not exact"). Never round it up.
* S6 has no provenance block. Render it as **Constructed test, not from an incident: tests that a
  higher-ranked Abu Dhabi clause can't govern a Dubai case.** Never leave it blank, which would read as
  a missing link.
* The publisher name never appears in a way that suggests endorsement. The prefix is always "From" or
  "Reconstructed from", never a logo.
* External links open in a new tab with `rel="noopener"`. The ↗ glyph is the only external-link marker
  in the console.

---

## 6. Trust pattern

One visual grammar across the trace, the run stream, the audit table and the queue rows. **The mark
shows how much the statement counts. The tag says who said it.**

| Mark | Name | Shape | Border / fill | Colour token | Verbs it may use | May show a number? |
|---|---|---|---|---|---|---|
| `◇` | **AI suggested** | hollow diamond | 1 px **dashed** border, no fill, "AI" pill + model family | `--trust-ai` (slate-violet `#5b5f8a`) | suggests, objects, reads, flags | Yes: *model confidence 0.93 (its own score)* |
| `◇` | **Rules suggested** | hollow diamond | 1 px dotted border, no fill, "Rules" pill | `--trust-ai` | proposes | Yes: *support 0.60 (rule heuristic, not a probability)* |
| `✓` | **Checked by code** | check in a square | 1 px **solid** border, white fill | `--trust-code` (slate `#3d4854`) | checked, upheld, corrected, rejected, kept | No, only outcome words |
| `▣` | **Decided by the gate** | filled square | 3 px solid **left bar**, tinted fill | `--trust-gate` (navy `#1f4e79`) | allowed, refused, moved, handed to | No; shows the invariant ID |
| `●` | **Decided by a person** | filled circle | solid border, filled, role and time always present | `--trust-person` (plum `#6b3f8c`, the existing HUMAN layer colour) | acknowledged, took, recorded, approved | No; shows role, time and name when known |

**Rules**

1. **The heavier the mark, the more it counts:** dashed < solid outline < filled bar < filled with a
   name. Someone who never reads a legend still ranks them correctly.
2. **Meaning never rests on colour alone.** Each mark has a glyph and a text tag ("AI", "Code", "Gate",
   "Person"). The tag is the accessible name: `aria-label="AI suggestion from the adversarial
   reviewer"`.
3. **Green, amber and red are not trust colours.** They stay reserved for outcomes (safe, waiting,
   needs a person) as `04-decisions.md` S3 set out. A gate *refusal* is ▣ with a red outcome chip
   inside; the mark itself doesn't turn red.
4. **AI text is always quoted or labelled.** It never sits in the summary sentence as fact. The sentence
   says "the reviewer said…", never "the reply contradicts the record".
5. **Each actor has its own verbs.** AI never "decides", the gate never "suggests", and code never
   "thinks".
6. **A chain of marks reads left to right** with `→`: `◇ AI reviewer objected → ✓ code kept it →
   ▣ gate handed to Supervisor → ● Supervisor took it 14:30`. This breadcrumb appears in queue rows, the
   case Summary and the Compare step cells.
7. **An empty person slot is shown, not hidden.** `● Nobody yet` with the deadline: the absence is the
   point.
8. **Legend:** shown once in the trace's step rail, and in the tour's first trace stop. It is never a
   modal.

```
┌┄◇ AI · Adversarial reviewer · Jev ┄┄┄┄┄┄┄┄┄┄┄┄┐   ┌─✓ Code check ───────────────────────────┐
┆ Objection  Reply contradicts the record        ┆   │ Objection stands. A recorded human       │
┆ model confidence 0.93 (its own score)          ┆   │ statement exists.                        │
└┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘   └──────────────────────────────────────────┘
┃▣ Gate · Allowed: hand to a person               ┌●─ Person ────────────────────────────────┐
┃  INV-8 ✓  binds to R1                           │ Supervisor on duty took the case · 14:30 │
┃  Acknowledged → With a named person             └──────────────────────────────────────────┘
```

Dark mode: the same tokens, raised to at least 4.5:1 on `--surface` under the existing
`prefers-color-scheme` block in `index.css`. The dashed and dotted borders keep their pattern.

---

## 7. Prioritised implementation list

The submission deadline is 10 Nov. **P0** is what judges see in three minutes and what the video shows.
It is frontend work plus three small backend additions, with no route changes. **P1** is the
restructure. **P2** is polish and the one real backend capability gap.

### P0: before the video re-shoot

| # | Change | Files |
|---|---|---|
| P0-1 | **Label layer.** Add `labels.ts` with every map in 4.4–4.6 (`{label, explain}`). Add `<StateChip code>` / `<CodeLabel kind code>` that render the label, with code and explanation in the tooltip. Replace the raw-enum `Chip`s on every page. | new `web/src/labels.ts`; `web/src/ui.tsx`; `pages/Dashboard.tsx`, `CaseTimeline.tsx`, `Simulator.tsx`, `Compare.tsx`, `Trace.tsx`, `Evaluation.tsx`, `StandardsMapping.tsx` |
| P0-2 | **Provenance.** Return `provenance` from `list_scenarios()`. Build `Provenance` (inline/strip/panel). Show it in the Simulator picker and About text, the Compare picker, Dashboard rows, the Trace header, and the Dashboard footer line. S6 uses the "Constructed test" copy. | `app/orchestration/engine.py` (`list_scenarios`); new `web/src/components/Provenance.tsx`; `pages/Simulator.tsx`, `Compare.tsx`, `Dashboard.tsx`, `Trace.tsx` |
| P0-3 | **Trace rewrite in place.** Add a case header (short title, state, owner, provenance). Default to the decisive step. Add the summary sentence (4.7), fixed section names and order, trust marks (6), council answer labels, confidence wording, the `▸ Codes` disclosure, and the *Compare: rules only* link. Add `scenario_id` to the trace response. | `pages/Trace.tsx`; new `web/src/components/Trust.tsx`; `web/src/index.css` (trust tokens); `app/api/routes.py` (`run_trace`: add `scenario_id`, `escalations`) |
| P0-4 | **Overview queue first.** Put the *Needs a person now* panel above the chain. Default the filter to ResultRelay runs and add a *Show comparison runs* toggle. Add the "why" sentences (4.6). Rows open the case trace. | `pages/Dashboard.tsx` |
| P0-5 | **Shell copy.** Nav labels, groups, titles, purposes, footer and flag tooltip (4.1). Remove the page-top info banners and move their content inline. | `web/src/App.tsx`; the banners in `Trace.tsx`, `Compare.tsx`, `Simulator.tsx`, `Audit.tsx`, `StandardsMapping.tsx` |
| P0-6 | **Evaluation headline and ✓/✗ matrix.** Add the Result panel. Show the matrix with plain scenario names, grouped columns, the S9 row highlighted, and cells that link to Compare. | `pages/Evaluation.tsx` |
| P0-7 | **3-minute tour entry.** Add a top-bar button that finds the latest live S9 council run (`GET /runs`) or starts and plays one, then navigates to its trace. (The coach strip is P2-4; P0 only needs the jump.) | `web/src/App.tsx`; `web/src/api/client.ts` (no new endpoints) |

### P1: restructure (after submission, or before it if time allows)

| # | Change | Files |
|---|---|---|
| P1-1 | **Case page with tabs.** Add `/cases/:caseId/(trace|timeline|delivery|audit)`. Move the CaseTimeline tabs and the Trace into it. Extract `StepDetail`, `AuditTable` and `CaseHeader`. Add redirects for `/trace?run=`, `/cases?case=` and `/trace` (1.4). | new `pages/Case.tsx`, `components/StepDetail.tsx`, `components/AuditTable.tsx`, `components/CaseHeader.tsx`; `App.tsx`; slim `pages/CaseTimeline.tsx` → `pages/Cases.tsx` (list only); `pages/Trace.tsx` becomes a tab |
| P1-2 | **Scenarios page** (Run one + Compare two). Grouped picker with provenance. Run stream reuses `StepDetail`. Compare gets an Outcome row and a step-aligned diff with first-difference marking and quick picks. Add `/simulator` and `/compare` redirects. | new `pages/Scenarios.tsx` (from `Simulator.tsx` + `Compare.tsx`); `App.tsx` |
| P1-3 | **Safe endings in the API.** `GET /scenarios` returns `short_title` and `safe_final_states` (from `scenarios/expected/*.json`), so Compare and Run can say ✓/✗. | `app/orchestration/engine.py` or `app/api/routes.py` (`scenarios`) |
| P1-4 | **Escalations on list rows.** `GET /cases` rows include `escalations[{role, status, tier, due_at}]` and `run_id`, so the Overview shows owner and deadline without opening the case. | `app/api/routes.py` (`cases`) |
| P1-5 | **Take this case.** Add `api.injectEvent(runId, body)`. Add a header button, confirmation dialog, toast and disabled state (2.3). | `web/src/api/client.ts`; `components/CaseHeader.tsx` |
| P1-6 | **Rules & gaps.** Reorder and rename the tabs. Add the "Authority for a Dubai case" and "Checked against" columns (from `official_url`, `verification_status`). Add Arabic example chips and `dir="auto"`. Add the gap register's "What we do instead" and "Surfaced in". Add the **clause drawer**, opened from any citation (`?clause=`). | `pages/StandardsMapping.tsx`; new `components/ClauseDrawer.tsx`; `api/client.ts` (`chunk` already exists) |
| P1-7 | **Cases list filters.** Status pills, a runs filter, a scenario filter and ID search. | `pages/Cases.tsx` |
| P1-8 | **Audit chain page.** All-chains result first. *By* column with trust marks. Event codes in a disclosure. | `pages/Audit.tsx`, `components/AuditTable.tsx` |

### P2: polish and capability

| # | Change | Files |
|---|---|---|
| P2-1 | **390 px layouts** as described per page: sidebar to top bar and sheet, tables to cards, sticky action bars, the step rail as a chip row. | `web/src/index.css`; page components (class hooks only) |
| P2-2 | **Swimlane timeline**, with list view as the fallback. | `pages/Case.tsx` (timeline tab) |
| P2-3 | **Record the outcome from "In review".** New transitions: `ESCALATION_IN_REVIEW` + `clinical.acknowledgment` (verified identity, current revision) → `CLINICAL_ACKNOWLEDGMENT_CONFIRMED`, then `documentation.recorded` → `COMMUNICATION_DOCUMENTED`. Add tests, then a UI form ("Who did you reach? On which number? Which revision?"). Until this ships, the console must not imply that a person can close a case. | `app/state_machine/transitions.py`; `app/orchestration/engine.py`; `tests/test_state_machine.py`; `components/CaseHeader.tsx` |
| P2-4 | **Guided tour coach strip** (5 stops, Esc to leave, a URL per stop). | new `components/Tour.tsx`; `App.tsx` |
| P2-5 | **Keyboard:** `j`/`k` for previous/next step in the trace and run stream, `g o` for Overview, `?` for help. | `components/StepDetail.tsx`, `App.tsx` |
| P2-6 | **Dark-mode trust tokens** and a contrast check added to the existing script. | `web/src/index.css`; the contrast script referenced in `05-typography-and-colour.md` |
| P2-7 | **Print stylesheet** for a case (header, summary, decisive step, audit table). | `web/src/index.css` |
| P2-8 | **Arabic labels** for the state and trust vocabulary (only the label layer; `labels.ts` is keyed for this). | `web/src/labels.ts` |

**Verification for each item:** a screenshot at 1600×825 (the video viewport) showing the page's
answer above the fold; a keyboard pass (Tab reaches every action and Enter activates it); and, for any
route change, a test that each old URL in 1.4 lands on its new page.
