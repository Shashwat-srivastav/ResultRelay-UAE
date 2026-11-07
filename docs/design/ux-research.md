# ResultRelay console: user research for the redesign

**Date:** 2026-11-08 · **Build reviewed:** `web/src` at version 0.1.0 (8 pages) plus 9 screenshots
(`docs/figures/console.png`, `docs/figures/console_trace.png`, and `_work/video/probe/v3_simulator.png`,
`v3_evaluation.png`, `v3_standards.png`, `frame_05-channel.png`, `frame_08-genetic.png`, `frame_09-kb.png`,
`frame_10-eval.png`) · **Companion docs:** `01-critique.md` (visual and accessibility findings, Oct 2026),
`02-user-stories.md` (first story set). This document replaces the stories in `02-user-stories.md`. It keeps
the critique's colour and contrast findings and adds the domain, provenance and workflow findings that the
critique did not cover.

### Method and its limits

- **Evidence used:** published standards and guidance (Joint Commission, CAP, CLSI, RCPath, ONC, DHA), peer-reviewed
  studies on missed results and alert fatigue, the published incidents the scenarios are built from, vendor and
  design-system documentation, and a line-by-line read of the eight page components against the screenshots.
- **What this is not:** nobody was interviewed. The personas are **proto-personas** built from the literature and
  from the roles that DHA ST-28 and the scenarios define. §7 gives a five-session validation plan that can run
  before the onsite final on 8 Dec 2026. Until it runs, treat every persona claim as a hypothesis with a citation,
  not as a finding.
- **Severity convention** (§5): severity 1–4 (4 = could make someone misread the product's core claim or a
  patient-safety state) × frequency 1–3 (3 = on a screen almost every user sees). The score is the product.

---

## 0. The five findings that should drive the redesign

1. **The console never says where its scenarios come from.** Each scenario file has a `provenance` block
   (source title, URL, match strength, failure mode), but `list_scenarios()` drops it
   (`app/orchestration/engine.py:1436-1447`) and no page renders it (`grep provenance web/src` only finds the
   Evaluation column "Send provenance"). The README's strongest claim, "Built from real failures", is not on screen.
   This matters most for the judging criterion "agent capability in simulated error scenarios".
2. **The colours are backwards for this domain.** `stateTone()` (`web/src/ui.tsx:244-254`) paints
   `ESCALATION_REQUIRED` red, the same as `DELIVERY_STATE_UNKNOWN`, and paints `DELIVERY_CONFIRMED` amber. Escalating
   to a named person is the *correct* outcome in most scenarios, and closing a case on a delivery receipt is the
   *failure* the product exists to prevent. In `frame_05-channel.png` the safe run and the unsafe run carry the same
   amber chip.
3. **The human handoff, which is the whole point of the product, has no screen.** The console tile says "escalated,
   with an owner and a deadline", yet no page shows an owner, a deadline, a time elapsed, or whether the person
   answered. The Simulator shows only `SUPERVISOR, CLINICAL_LEAD`: role enums, not people, and no state.
4. **Internal vocabulary is shown as if it were interface copy.** State enums, invariant IDs, assessor field names,
   probabilities, JSON, file paths and a backticked code identifier (`` `case.recent_events` ``) all appear raw.
   Clinicians and regulators are not the audience for these strings, and a judge has to decode them under time pressure.
5. **The console mixes operations with experiments.** Policy-blind and ablation runs feed the same chain counts and
   cases table as the full system, so "Delivered 2" on the console is two runs of a deliberately unsafe baseline. The
   `Case` column cuts IDs to three segments (`Dashboard.tsx`, `case_id.split("-").slice(0, 3)`), so four different
   runs all read `SYN-CASE-003`.

---

## 1. Personas

Six personas. P1 to P3 are the people a deployed product serves. P4 and P5 decide whether it gets deployed. P6 is the
person all of this is for, and P6 never sees the console.

### Shared context: what makes this domain unusual

- **There is no ordering physician.** DHA ST-28 §11.1 lets a licensed laboratory accept walk-in patients for a
  permitted list of tests. §11.1.1 then puts the duty on the laboratory: "Critical laboratory results shall be
  reported clearly to the patient", and §11.1.3 adds: "The laboratory shall keep record of the communication with the
  patient." Genetic results are the exception. §13.4 says they "shall not be communicated to the patients directly"
  ([DHA ST-28, Issue 2, 2023](https://dha.gov.ae/uploads/052023/Standards%20for%20Clinical%20Laboratory%20Services2023552664.pdf);
  excerpts verified in `kb/records/S1_dha_st28.yaml`). The standard has no acknowledgment clock, no retry rule and no
  fallback-channel rule (gaps GR-03 and GR-04).
- **International practice is person-to-person, closed-loop and timed.** Joint Commission NPSG.02.03.01 requires
  critical results to be reported "on a timely basis", with written procedures for what counts as critical and who
  reports to whom, and with timeliness evaluated
  ([Joint Commission, lab NPSG chapter](https://jointcommission.org/-/media/tjc/documents/standards/national-patient-safety-goals/2024/npsg_chapter_lab_jan2024.ash)).
  CLSI GP47 describes "direct, person-to-person communication" and includes a sample escalation flow chart
  ([CLSI GP47](https://clsi.org/shop/standards/gp47/); [summary](https://labmedicineblog.com/2015/12/11/clsi-publishes-a-new-document-on-management-of-critical-and-significant-risk-results/)).
  CAP checklist practice records who received the result, read-back, and time to notification
  (commonly cited as GEN.41320/GEN.41330; [example lab form](https://www.downstate.edu/patient-care/lab-services/_documents/LAB-34_wm.pdf)).
  RCPath G158 makes the laboratory responsible for timely communication, and its 2025 draft notes that a system for
  this is an explicit ISO 15189:2022 requirement
  ([RCPath G158](https://www.rcpath.org/resourceLibrary/g158-bpr-the-communication-of-critical-and-unexpected-pathology-results.html)).
  ONC SAFER Guide 8 (Aug 2024) lists 23 practices on reporting, acknowledging, amending and tracking results
  ([ONC SAFER 8](https://www.healthit.gov/sites/default/files/topiclanding/2025-01/8.%20Test%20Results%20Reporting%20Final.pdf)).
- **Sending is rarely where it breaks. Acknowledgment is.** In one paediatric hospital, more than 90% of critical
  values were sent on time, but under 5% were *acknowledged* on time for the haematology/oncology service. Team
  smartphones raised that to a median of 76%
  ([BMJ Open Quality 2021, PMC8442100](https://pmc.ncbi.nlm.nih.gov/articles/PMC8442100/)). About 1 in 10
  electronic lab alerts went unread in VA clinics
  ([Singh 2010, via PSNet](https://psnet.ahrq.gov/issue/notification-abnormal-lab-test-results-electronic-medical-record-do-any-safety-concerns)),
  and 7.7% of imaging alerts lacked timely follow-up ([Singh 2009](https://pmc.ncbi.nlm.nih.gov/articles/PMC3445672)).
  Inpatient results that were not followed up after discharge ranged from 20% to 62%
  ([Callen 2011, BMJ Qual Saf](https://qualitysafety.bmj.com/content/20/2/194)).
- **SMS "delivered" is a carrier's claim, not a person's.** Some carriers acknowledge when a message enters their
  network rather than when it reaches the handset. SMS has no read state, and a missing receipt means "unknown", not
  "failed" ([Bird](https://bird.com/explained/sms/what-is-a-delivery-receipt);
  [Optus](https://sms.optus.com.au/docs/en/sms-delivery-info/mobile-delivery-receipts/)).
- **The audience is used to alarms that don't matter.** Primary-care physicians received about 77 EHR notifications
  a day, about 20% of them about test results
  ([Murphy 2016, JAMA IM](https://pmc.ncbi.nlm.nih.gov/articles/PMC4860883)). In Ancker 2017, each extra reminder
  per encounter cut the odds of acceptance by about 30%
  ([BMC MIDM](https://psnet.ahrq.gov/issue/effects-workload-work-complexity-and-repeated-alerts-alert-fatigue-clinical-decision-support)).
  In a 2024 survey, 35% of clinicians said critical-result calls distract them from patient care
  ([ADLM CLN 2024](https://myadlm.org/cln/Articles/2024/SeptemberOctober/Critical-result-notification-preferences)).
  Design consequence: red is scarce, and repeats are collapsed.
- **Explanations persuade whether or not they are right.** In Bansal et al. (CHI 2021), AI explanations raised the
  rate at which people accepted the AI's recommendation regardless of its correctness. Showing confidence did about as
  well as explaining ([paper](https://arxiv.org/abs/2006.14779)). Design consequence: show disagreement and code
  checks, not a fluent paragraph.

---

### P1. Dr Reem, laboratory supervisor and pathologist on duty, walk-in laboratory, Dubai

| | |
|---|---|
| **Role** | DHA-licensed clinical pathologist, supervisor on duty for a walk-in laboratory chain with several collection points. First tier in the escalation path (`SUPERVISOR`). |
| **Goals** | Every critical result reaches the patient (or, for genetics, the referring physician), and the laboratory can prove it. No surprises at a DHA inspection. Spend minutes, not an hour, on each escalation. |
| **Moment she opens the console** | A page or SMS from the system: "Critical result SYN-…: needs you by 15:45". She is between sign-outs or in a QC review, standing, on a lab workstation or her phone. |
| **First-5-second question** | "Which result needs me, why, and by when?" Next: "What exactly am I allowed to do: call, use the portal, or route to a physician?" |
| **Fears** | Closing a case on a carrier receipt and being wrong. Contacting the wrong person (a relative, or the patient for a genetic result) and breaching confidentiality. Being the last name in the audit trail with no record of what she did. Another alarm that turns out to be noise. |
| **Environment** | Interrupted every few minutes. Shared workstations. English is the working language, but patients and some staff prefer Arabic; about 91% of Dubai residents are non-nationals ([DSC series via GLMM](https://gulfmigration.grc.net/uae-dubai-estimates-of-population-by-nationality-emiratis-non-emiratis-at-selected-dates-1975-2016/)), so names, scripts and phone formats vary. |
| **AI literacy** | Moderate. She uses the LIS and middleware rules every day and distrusts free text she cannot trace. She will not act on "the model thinks". She will act on "the reply came from a different number than the patient's registered contact". |
| **What earns trust** | The exact clause behind the system's instruction (ST-28 §11.1.3, §13.4). The record behind each stage (gateway ID, receipt time, acknowledgment text and sender). An explicit statement of what is *not* known. One action, not a dashboard. |
| **Evidence** | CLSI GP47 person-to-person reporting and escalation; CAP read-back and documentation; the CRICO 2023 case, where the attending was paged, did not respond, and "the culture result was not escalated to the patient's nurse or another member of the care team" ([CRICO](https://rmfcd1-prod.rmf.harvard.edu/Risk-Prevention-and-Education/Case-Study-Catalog-Page/Case-Study/2023/Discharged-Patient-with-Pending-Test-Results)). |

### P2. Dr Faisal, clinical lead (second tier), laboratory network

| | |
|---|---|
| **Role** | Medical director or clinical lead. Receives an escalation only when the supervisor's deadline passes (`CLINICAL_LEAD`, scenario S10). |
| **Goals** | Understand in under a minute why the first tier failed, take over, and make sure the gap is fixed so it does not happen again. |
| **Moment he opens it** | Out of hours, on a phone, after a second-tier page. He has no context: he did not see the first escalation. |
| **First-5-second question** | "What happened before it reached me, how long has the patient been waiting, and who already tried what?" |
| **Fears** | Inheriting a case that is already hours late with no history. Being accountable for a decision the system made silently, such as an unapproved channel switch. |
| **Environment** | Phone, poor attention, possibly driving or in clinic. Needs a summary readable at arm's length. |
| **AI literacy** | Low to moderate. He wants the chain of custody, not model output. |
| **What earns trust** | A handover summary in time order: tier-1 paged at T, no response by T+15, raised to him at T+16, with every line linked to an audit entry. Confirmation that nothing was sent without authority. |
| **Evidence** | PerfectServe at HSS auto-escalated unacknowledged critical results after 6 minutes and reported a 42% improvement in acknowledgment time ([Healthcare IT News](https://www.healthcareitnews.com/news/hospital-special-surgery-accelerates-speed-care-vulnerable-patients); vendor-reported). PagerDuty-style escalation levels ([PagerDuty docs](https://support.pagerduty.com/docs/incidents)). |

### P3. Mariam, laboratory quality and compliance manager

| | |
|---|---|
| **Role** | Quality manager responsible for ISO 15189 or CAP accreditation, DHA inspection readiness and incident review. Owns the facility's institutional profile: approved fallback channels, acknowledgment clocks, escalation roles. |
| **Goals** | Show an inspector, for any case, that communication was attempted, delivered, acknowledged by the right person for the current revision, and documented. Find patterns: which channel fails, which tier does not answer. |
| **Moment she opens it** | Weekly review, a complaint, or the night before an inspection. Desktop, uninterrupted, export in mind. |
| **First-5-second question** | "How many cases are not closed, and is any of them closed for the wrong reason?" |
| **Fears** | A record that looks complete but is not, such as an acknowledgment bound to revision 1 after revision 2 was issued. An audit log that can be edited. A tool whose numbers mix tests with live work. |
| **Environment** | Desktop, two monitors, spreadsheets, the facility SOP open beside it. |
| **AI literacy** | Moderate. Reads confidence scores sceptically and wants calibration, not decimals. |
| **What earns trust** | Hash-chain verification she can rerun. Per-case export. Every number with its denominator. A clear line between "configured by our facility" (institutional control) and "required by DHA" (statute or standard). |
| **Evidence** | Joint Commission requirement to *evaluate* timeliness; ONC SAFER 8 practices on amended results; the AHRQ PSNet "Amended lab results" case, where the correction reached a unit and not the clinician who had acted on version 1 ([PSNet](https://psnet.ahrq.gov/web-mm/amended-lab-results-communication-slip)). |

### P4. Khalid, policy or compliance officer at a regulator (DHA Health Regulation, or TDRA)

| | |
|---|---|
| **Role** | Reviews digital health and telecom use cases. The DHA lens covers ST-28, Federal Law 2/2019 on health ICT and data residency, and the DHA AI policy. The TDRA lens covers SMS sender rules, spam policy and operator duties. He also sees the UAE Design System, which TDRA maintains ([designsystem.gov.ae](https://designsystem.gov.ae/about)). |
| **Goals** | Decide whether the system stays inside the law, and see where the law is silent (the gap register is the most useful artefact for him). Check that out-of-jurisdiction rules (Abu Dhabi, UK, US) are never applied as binding. |
| **Moment he opens it** | A sandbox review meeting, often projected on a screen with colleagues, or a pre-read link. |
| **First-5-second question** | "What is this system allowed to decide on its own, and which regulation does each decision rest on?" |
| **Fears** | An AI presented as making clinical or legal determinations. Foreign standards dressed up as UAE obligations. Patient data leaving the State (Federal Law 2/2019 Art. 13). Overclaiming ("compliant", "safe"). |
| **Environment** | Meeting room, shared screen, mixed Arabic- and English-speaking colleagues, little time per item. |
| **AI literacy** | Policy-literate, not ML-literate. Distrusts confidence decimals and accepts "the code checked X against the record". |
| **What earns trust** | Binding, guidance and comparator labels in plain words. Gaps stated as questions, with who could close them. A statement on every screen of what the system does not do. Arabic retrieval that visibly works. |
| **Evidence** | The scope-boundary design in ST-28 §11.1 and §13.4; GOV.UK and NHS conventions for status and warnings in public-sector services ([GOV.UK tag](https://design-system.service.gov.uk/components/tag/); [NHS warning callout](https://service-manual.nhs.uk/design-system/components/warning-callout)). |

### P5. Dr Lina, ITU or UAE-government evaluator with minutes per entry

| | |
|---|---|
| **Role** | One of several evaluators scoring about 15 shortlisted teams against five unweighted criteria: knowledge-base quality, agent behaviour in simulated error scenarios, gap identification, auditability, and Y.3172/AI Readiness alignment. Prototype accuracy is explicitly not scored ([event page](https://aiforgood.itu.int/event/ai-for-good-sandbox-hackathon-united-arab-emirates/)). |
| **Goals** | Score fairly and fast. Find evidence for each criterion without reading the code. Spot overclaiming. |
| **Moment they open it** | From the submission link, after the 5-page report and the video, with about 3 minutes for the live console. Possibly on a laptop in a hotel, or projected at GITEX. |
| **First-5-second question** | "What problem is this, and is it real?" Then, at 30 seconds: "Show me the agents doing something a plain LLM or rules engine would get wrong." |
| **Fears (theirs, as an evaluator)** | Being shown a toy scenario invented to flatter the system. Decorative AI. Numbers without baselines. Having to learn a private vocabulary (`INV-9`, `policy_blind`) to judge. |
| **Environment** | Fatigue after many demos. Will not open a dropdown unless told to. Reads the top third of each page. |
| **AI literacy** | High (ITU ML-in-networks standards background, Y.3172). Will look for the orchestrator, the evidence trail and the failure cases. |
| **What earns trust** | A real published incident next to the replay. The same scenario with and without the safeguard, side by side, with a one-line verdict. Honest limits next to the score (`n = 12`, "authored by the team"). Arabic retrieval. Audit verification they can trigger. |
| **Evidence** | Criteria from the event page (team notes, 2026-11-02). In the KSA edition, entries with verbatim-cited regulation mapping and an "AI proposes, deterministic code decides" design were among the winners (team notes). |

### P6 (indirect). Priya, walk-in patient, and her referring physician

| | |
|---|---|
| **Role** | Self-referred patient at a walk-in laboratory, an expatriate who prefers English with Arabic as a second script on official messages. For genetic tests, her referring physician is the recipient, not her. |
| **Goals** | Hear about a critical result promptly, from a source she trusts, in words she understands, with a clear next step: "seek medical advice" (ST-28 §11.1.2, guidance). |
| **Her moment** | An SMS from a sender ID she may not recognise, possibly read first by a family member who shares the phone. |
| **First-5-second question** | "Is this real, is it about me, and what do I do now?" |
| **Fears** | Spam or fraud (TDRA sender rules exist for a reason). A relative reading her result. Being told a genetic finding by text with no counselling. |
| **What the console must protect** | That a reply from *another person* is never counted as her acknowledgment. In the Medical Protection case, a positive result went by text to the husband's phone after a contact-number change ([Medical Protection](https://www.medicalprotection.org/uk/articles/digital-dilemmas-communicating-with-patients-by-text)). Genetic results must never use her channel ([adverse events in genetic testing, case series](https://pubmed.ncbi.nlm.nih.gov/31335384/)). |
| **Design implication** | The console should show the *recipient identity check* (registered contact vs sender of reply) as a first-class field, and the outbound message text as the patient would see it. |

---

## 2. Case studies: comparable products and practices

### CS-1. Closed-loop clinical communication: PerfectServe, TigerConnect, Vocera Engage (Stryker)

- **What they do:** The LIS flags a critical value. The platform routes it to the *role* on call, tracks message
  status, requires an explicit Accept or Reject, and escalates on a timer.
  - PerfectServe at HSS escalates unacknowledged results after 6 minutes. A decline is sent back to the lab. The
    thread shows "delivery timestamps, read receipts, message acknowledgments, and next steps"
    ([PerfectServe](https://www.perfectserve.com/integrations/clinical-alerts-critical-results/)).
  - TigerConnect shows delivered and read status indicators, plus an "Acceptance & Escalation" view against CLIA and
    Joint Commission timeframes ([TigerConnect](https://tigerconnect.com/?p=9047)).
  - Vocera Engage message states separate *Delivered*, *Read* and *Acknowledged*, and escalation rules set the number
    of tiers, the roles and the interval
    ([Engage release notes](https://pubs.vocera.com/rnotes/ReleaseNotes_engage_mobile_ios_5.2_sr0.html);
    [solution brief](https://www.stryker.com/content/dam/stryker/acute-care/vocera/resources/solution-briefs/vocera-engage-solution-brief.pdf)).
- **Borrow:**
  1. **Delivered, Read and Acknowledged as three visibly different states.** ResultRelay already has the stronger
     model (accepted, delivered, acknowledged by a named person for the current revision), but the console shows the
     stages as six equal boxes with no per-case progress.
  2. **An escalation timer shown as elapsed and remaining time** next to the named role.
  3. **An explicit Accept or Decline on an escalation**, with decline routed back. In the prototype this can be a
     simulated button that writes an audit event.
- **Do not borrow:** the read receipt as proof of acknowledgment, which is exactly the trap in S9 and S11. Also do not
  borrow their marketing outcome figures; these are vendor-reported numbers.

### CS-2. EHR result inboxes: Epic In Basket "Mark Reviewed", and its failure mode

- **What it does:** Result messages land in a clinician's inbox and are cleared with "Mark Reviewed"
  ([Partners guide](https://eristest2-6.partners.org/?p=12000)). Johns Hopkins warned that messages "with
  responsibility" could be marked done and removed "without the recipient noticing" (2020 notice)
  ([Hopkins Medicine Matters](https://medicine-matters.blogs.hopkinsmedicine.org/2020/01/epic-tip-of-the-week-january-31-2020/)).
  The PSNet Listeria case is the canonical harm: the attending got the result only as an inbox message that he did
  not see in time ([PSNet](https://psnet.ahrq.gov/web-mm/delayed-recognition-positive-blood-culture)).
- **Borrow:** the inbox metaphor for the supervisor (P1): a short list of *things that need you*, separate from the
  list of all cases.
- **Avoid:** any gesture that clears a case without a named, revision-bound acknowledgment. "Reviewed" and
  "documented" must never be one click apart. Every closure should show *who*, *which revision* and *on what
  evidence*.

### CS-3. NHS and RCPath practice: telephoned results policies

- **What it is:** UK trusts operate "telephoned pathology results" policies derived from RCPath G158. They set
  thresholds by analyte, define who may receive a call (a registered professional, with read-back), set out what to
  do when the requester cannot be reached (escalate to the on-call clinician, then the consultant), and require the
  call to be recorded in the LIS
  ([Sherwood Forest Hospitals policy v4.0, 2025](https://www.sfh-tr.nhs.uk/media/dxunc531/telephoned-pathology-results-policy-v40-issued-090625.pdf);
  [RCPath G158](https://www.rcpath.org/resourceLibrary/g158-bpr-the-communication-of-critical-and-unexpected-pathology-results.html)).
- **Borrow:**
  1. **A "who may receive this" rule shown on the case**: patient registered contact only, never a relative; for
     genetics, the referring physician only (ST-28 §13.4).
  2. **The fixed field set of a call record**: date and time, receiver's full name and role, read-back yes or no,
     revision. Render it as a GOV.UK-style *summary list*, not prose.
  3. **An escalation ladder drawn as a ladder**, with each rung's state (not tried, paged, no answer, accepted).

### CS-4. Incident management consoles: PagerDuty, incident.io, Linear

- **What they do:**
  - PagerDuty has three incident states: *triggered*, *acknowledged* and *resolved*. Acknowledging pauses escalation.
    Escalation policies have numbered levels. Each incident has a Timeline tab that can be filtered by event type
    ([PagerDuty incidents](https://support.pagerduty.com/docs/incidents)).
  - incident.io makes the *Incident Lead* role a first-class, named field on every incident
    ([incident.io roles](https://docs.incident.io/incidents/roles)).
  - Linear groups many custom statuses into a few *state categories* (backlog, unstarted, started, completed,
    cancelled), so any list can be grouped by category and the icons stay consistent
    ([Linear workflows](https://linear.app/docs/configuring-workflows)).
- **Borrow:**
  1. **Group the 18 machine states into about 6 categories for humans**: *Sending*, *Waiting for a person*, *With a
     person (escalated)*, *Needs reconciliation*, *Correction in progress*, *Closed (documented)*. Show the precise
     state on hover and in the trace. The console's chain and exit tiles already do this; the chips in tables do not.
  2. **An owner field and an escalation-level badge on every open case** ("Level 2 of 2 · Clinical lead · 07 min
     overdue").
  3. **A filterable timeline** on the Audit trail and Case timeline (filter by person, agent, gate or transport) with
     human-readable summaries and raw payload behind a disclosure.
  4. **Keyboard triage** in Linear's style (`j/k` to move, `Enter` to open) for P3's weekly review.

### CS-5. Air traffic control flight progress strips (paper and electronic)

- **What it is:** Each flight is a strip. Strips sit in *bays* that represent state (pending, taxi, runway,
  airborne) and move between bays as state or *ownership* changes. Strip management is described as a barrier against
  runway incursions ([SKYbrary](https://skybrary.aero/articles/flight-progress-strips)). Electronic systems keep the
  bay layout and add data and alerts ([Saab EFS](https://www.saab.com/products/electronic-flight-strips-EFS);
  [NASA NTRS](https://ntrs.nasa.gov/api/citations/20030068998/downloads/20030068998.pdf)).
- **Borrow:** the console's six-stage chain is already a strip board, but cases are only *counted* in it. Make each
  stage a bay that holds the case *strips* (ID, scope badge, time in stage, owner). A strip that has to cross the
  "acknowledged" line visibly cannot do so on a carrier receipt. Ownership transfer (supervisor to clinical lead) moves
  the strip and is logged, as a controller hand-off is.
- **Caution:** ATC strips work because controllers are trained on the code language. ResultRelay's users are not, so
  the strip carries plain words with the enum underneath.

### CS-6. Public-sector design systems: GOV.UK, NHS, UAE Design System (TDRA)

- **What they offer:**
  - **GOV.UK tag:** tags signal *status only*, where status matters to the user. Status wording and colour should be
    researched rather than invented ([tag](https://design-system.service.gov.uk/components/tag/);
    [task list iteration](https://designnotes.blog.gov.uk/2023/12/15/working-as-a-community-to-iterate-the-task-list-pattern/)).
  - **NHS warning callout:** for time-critical information or a common, significant mistake, so that it is found even
    by users who skip the page ([NHS](https://service-manual.nhs.uk/design-system/components/warning-callout)).
  - **UAE Design System:** maintained by TDRA, built for federal websites, and federal sites and apps are expected to
    comply with it in future ([about](https://designsystem.gov.ae/about);
    [WAM, DLS 2.0](https://www.wam.ae/en/article/b36k4xe-tdra-launches-uae-design-system-20-for-federal)).
- **Borrow:**
  1. **One tag vocabulary with research-backed words** ("Handed to a person", "Waiting for acknowledgment", "Closed:
     documented"), never a raw enum.
  2. **A warning callout reserved for the one mistake each scenario exists to catch**: "A reply from someone other
     than the patient is not an acknowledgment."
  3. **Bilingual labels for the core status vocabulary**, plus Arabic queries in Retrieval, which signals fit with the
     UAE federal ecosystem to TDRA judges. Arabic layouts need design work, not automatic mirroring.

---

## 3. Top tasks and three end-to-end journeys

### 3.1 Top tasks per persona (ranked by how often × how much is at stake)

| Persona | Top tasks (in order) | Page today | Gap today |
|---|---|---|---|
| **P1 Supervisor** | 1. See what needs me now and by when · 2. Understand why it was escalated (which stage broke, what evidence) · 3. Know which actions are authorised (channel, recipient) · 4. Record what I did · 5. Check that a correction reached the patient | Console → Simulator → Trace | No "needs me" list, no deadline, no action, no authorised-actions panel |
| **P2 Clinical lead** | 1. Read the handover: what tier 1 did and did not do · 2. Take ownership · 3. See time the patient has waited | Simulator escalations cell | Shows `SUPERVISOR, CLINICAL_LEAD` only; no time order and no state per tier |
| **P3 Quality manager** | 1. Count open and closed with the reason · 2. Find false closures · 3. Verify the audit chain · 4. Export a case for an inspector · 5. Review institutional settings (fallback approved? clock?) | Console, Case timeline, Audit | Baselines mixed in; Institutional profile is buried as the 6th tab in Standards |
| **P4 Regulator** | 1. See what the system may and may not decide · 2. See the clause behind a decision and its binding status · 3. Review the gaps · 4. Check that comparators are never binding · 5. Check data residency and channel rules | Standards & gaps, Trace | Enum labels; gaps not linked to the scenarios that surface them |
| **P5 Judge** | 1. Grasp problem and realism (5 s) · 2. Watch one scenario fail without the safeguard and pass with it (60 s) · 3. See the agents disagree and the gate decide (60 s) · 4. Check the KB, gaps and Arabic retrieval (30 s) · 5. Check the score with its baseline and caveat (20 s) | Console → Side-by-side → Trace → Standards → Evaluation | No guided path; provenance invisible; Compare default shows no difference; trace leads with the analyst's wrong answer and no label |
| **P6 Patient (indirect)** | Gets the right message, on the right channel, once, in words she understands; a relative's reply never closes her case | none (outbound text not shown) | The message as sent is not displayed anywhere a reviewer can check |

### 3.2 Journey A: "A judge has 3 minutes" (P5)

| t | Judge wants | Today | Target |
|---|---|---|---|
| 0:00–0:10 | "What is this, and is it real?" | Console header: "Where every critical result is on its way to a person…" plus six counters, three of them 0. No mention of the published incidents. | A **Start here** strip on the Console: one sentence on the problem, the chain, and "11 of 12 scenarios drawn from published patient-safety incidents and studies (AHRQ PSNet, CRICO/Harvard, Medical Protection, BMJ Open Quality); identities invented", with a **Watch S9 in 60 seconds** button. |
| 0:10–1:10 | "Show me it catch something" | Must pick Side-by-side, then a scenario and two configurations from three dropdowns. The default is council vs rules-only (`Compare.tsx:20-21`), which usually shows no difference. | **Side-by-side** preloaded with S9 (reply from the daughter), *Policy-blind* vs *ResultRelay + council*, and a verdict line at the top: "Policy-blind closed the case on a reply from someone else. ResultRelay escalated to the supervisor." The incident card is above both columns. |
| 1:10–2:10 | "Where's the multi-agent part, and is it auditable?" | Trace step 5 opens with the policy analyst's *wrong* reading, with a neutral `ANSWERED` chip, then raw `p=` values. | **Decision trace** step header: "Council caught a misreading": analyst (said acknowledged) vs reviewer (objected: sender is not the patient) → code check → gate: escalate. Raw fields sit behind "Show raw". A link reads "Audit entries 22–23 · chain valid". |
| 2:10–2:40 | "Is the knowledge base real, and does it handle Arabic?" | Standards → Retrieval tab. The Arabic query works, but the first thing shown is an amber "ChromaDB or Ollama unavailable" banner. | The Retrieval tab is preloaded with an Arabic query. The engine status is a neutral one-line note. Results show the binding label in words, the source, and "verified against official PDF p. 39". |
| 2:40–3:00 | "Numbers, with honesty?" | Evaluation table. All non-perfect scores share one amber, and the legend is below the fold. | The lead row is the full system at 12/12 with the strongest baseline beside it, next to the caveat "12 scenarios, written by the team; not a safety claim". Score chips are graded. |

### 3.3 Journey B: supervisor handles "escalation nobody answered" (P1 → P2), scenario S10

1. **15:00.** The SMS gateway is down and no fallback is approved. The gate refuses the channel switch (INV-9).
   *Needed:* the case appears in **Needs a person** on the Console with "Supervisor · due 15:15 · 00:00 elapsed".
   *Today:* only a counter ("With a named person 11"), with no owner or due time.
2. **15:02.** Dr Reem opens it. *Needed:* an escalation card reading "Why you: SMS gateway down; portal and phone are
   available but no approved fallback procedure (gap GR-04). Authorised actions: contact via approved procedure, or
   record the outcome. Not authorised: switch channel without a procedure reference." *Today:* the Simulator's "Open
   questions" paragraph.
3. **15:15.** Nobody answers, and the deadline passes. *Needed:* the strip moves to **Clinical lead · Level 2**, the
   timer turns, and the audit entry is linked. *Today:* the escalations cell changes to `SUPERVISOR, CLINICAL_LEAD`
   with no timestamps.
4. **15:16.** Dr Faisal opens it on his phone. *Needed:* a handover timeline (finalised 14:30 → SMS timeout 14:31 →
   supervisor paged 15:00 → no response → raised 15:15) and "patient waiting 46 min". *Today:* nothing designed for
   this.
5. **Close.** *Needed:* a named acknowledgment for the current revision, then "Documented", with the evidence fields
   (CS-3).

### 3.4 Journey C: regulator reviews a genetic result routing (P4), scenarios S4 and S7

1. Opens **Standards & gaps → Sources** and filters to DHA. Sees ST-28 §13.4 labelled **Binding in Dubai**.
2. Clicks "Used in: S4, S7" (*missing today*) and lands in the **Decision trace** where the scope gate refused
   patient SMS.
3. Sees the recipient chosen *from the retrieved clause* ("Referring physician, per ST-28 §13.4") and the channel
   "Secure physician messaging". Sees the patient SMS channel marked *not authorised for this scope*.
4. Opens **Gap register → GR-05** ("Does §11.1 reach genetic results?") and sees the scenarios that surface it, with
   "who could close this gap: DHA Health Regulation" (*missing today*).
5. Exports the case bundle (Simulator → Export bundle) and verifies the chain on **Audit trail**.

---

## 4. User stories

IDs: **SUP** supervisor (P1), **CL** clinical lead (P2), **QM** quality manager (P3), **REG** regulator (P4),
**JDG** judge (P5), **PT** patient (P6). MoSCoW priority is for the 10 Nov submission and the 8 Dec final.
*Must* = the core claim or the judging criteria fail without it. Acceptance criteria name the page and the exact
element.

### Must

**JDG-1.** As a judge, I want to see on the scenario itself which published incident it was reconstructed from, so
that I can trust it is not a contrived test.
- *Simulator*: below the Scenario select, an **Origin card** shows the source title, publisher, year, link, the
  stored match strength (e.g. "very strong") and the failure mode in one sentence.
- The same card, collapsed to one line, appears in the *Side-by-side* header and the *Decision trace* header.
- S6, which has no incident source, shows "Designed test: no incident source (tests the jurisdiction filter)". It
  never shows an empty card.
- `GET /api/scenarios` returns `provenance` for each scenario. A UI test fails if any scenario other than S6 renders
  without a source link.

**JDG-2.** As a judge with 3 minutes, I want a guided path, so that I see the strongest evidence in the right order
without learning the navigation.
- *Console*: a **Start here** strip above the chain with three buttons: "1 · See it catch a failure (Side-by-side,
  S9)", "2 · Why it decided (Trace)", "3 · Evidence and gaps (Standards)".
- Each button opens its page with the scenario and configuration preloaded through URL parameters (e.g.
  `/compare?scenario=S9…&left=policy_blind&right=resultrelay_council&autorun=1`).
- From a cold start, all three pages show content within 5 s with no dropdown interaction.

**JDG-3.** As a judge, I want the Side-by-side page to state the difference in one sentence, so that I don't have to
infer it from two state chips.
- *Side-by-side*: a **Verdict line** above the two panels, e.g. "Policy-blind closed the case at *Delivered*; the
  reply came from someone other than the patient. ResultRelay escalated to the supervisor (gate rule INV-8)."
- The unsafe side gets a red tag "Unsafe outcome" and the safe side a neutral tag "Handed to a person". The current
  grey hint "different final state" is removed.
- The default pair is *Policy-blind* vs *ResultRelay + agent council*, not council vs rules-only.

**ALL-1 (SUP, REG, JDG).** As any non-engineer reader, I want states, rules and classifications in plain words, so
that I can act or judge without a glossary.
- On *every* page, chips show a human label from a single map (e.g. `ESCALATION_REQUIRED` → "Handed to a person",
  `DELIVERY_CONFIRMED` → "Delivered to handset, not acknowledged", `BINDING_REQUIREMENT` → "Binding",
  `VERIFIED_OFFICIAL` → "Verified against official text"). The enum shows in a tooltip and in "Show raw".
- Invariant IDs never appear alone. `INV-9` renders as "INV-9 · no channel switch without an approved procedure".
- An automated check fails if any rendered text node matches `^[A-Z]+(_[A-Z]+)+$` outside a `<code>` or "raw"
  disclosure.

**SUP-1.** As a supervisor, I want a "Needs you" list with owner, deadline and time elapsed, so that I know what to do
first.
- *Console*: the "With a named person" tile opens (or sits above) a **Needs a person** table with columns Case ·
  Why (one line) · Owner (role and name) · Level (1 of 2) · Due · Elapsed.
- Rows are sorted by time remaining. An overdue row shows "Overdue by 07 min" in red. This is the *only* red on the
  Console.
- The table excludes runs from baseline and ablation configurations (see QM-1).

**SUP-2.** As a supervisor, I want an escalation card that says what I am and am not authorised to do, so that I don't
improvise a channel or recipient.
- *Simulator* (and *Case timeline* case header): an **Escalation card** with "Why you", "Authorised actions" (each with
  its source: clause or facility procedure ID), "Not authorised" (e.g. "Portal or phone: no approved fallback
  procedure (GR-04)"), and a primary button.
- In the prototype the primary button ("Record outcome") writes an `escalation.response` audit event and is labelled
  as simulated.
- For S3b, the card names the approved procedure `SYN-FAC-PROC-014` as the authority.

**REG-1.** As a regulator, I want escalation to a person to look like a safe outcome and a false closure to look like
a failure, so that colour does not invert the meaning.
- `stateTone()` maps the escalation states to neutral or info ("Handed to a person"). It maps the reconciliation
  states to amber. Red is reserved for (a) overdue escalations and (b) outcomes the evaluator marks unsafe.
- On *Side-by-side*, S11 under *Policy-blind* renders its final state with a red "Unsafe: closed without
  acknowledgment" tag. Under ResultRelay it renders neutral.
- The "run complete" chip on *Simulator* is neutral, not green.

**REG-2.** As a regulator, I want the decision trace to show where the agents disagreed and what code checked, so
that I can see the model did not decide.
- *Decision trace*: the step header summarises the council in one line, e.g. "Council: analyst read *acknowledged* ·
  reviewer objected (*reply not from the patient*) · code check: sender ≠ registered contact → objection upheld".
- The analyst's wrong reading is labelled "Reading overruled". The assurance row says what was upheld ("Reviewer's
  objection upheld"), not just `UPHELD`.
- Probabilities (`p=0.93`) and field names sit behind "Show raw model output".

**QM-1.** As a quality manager, I want live cases separated from evaluation and baseline runs, so that counts on the
Console mean what they say.
- *Console*: the chain, exit tiles and Cases table default to the full-system configuration(s). A toggle "Include
  baseline and ablation runs (n)" is off by default.
- When the toggle is on, baseline rows carry an outline tag "Baseline: policy-blind" and are excluded from the chain
  counts.
- The `Case` column shows the full run-distinct ID, or the case ID plus a short run suffix, so that no two rows read
  identically.

**JDG-4.** As a judge, I want the honesty statements next to the claims they qualify, so that I don't discover the
caveats later.
- *Top bar*: the "Synthetic data, offline" badge expands on click to the three facts: synthetic records, identities
  invented, scenarios adapted from published incidents (with a link to the list).
- *Evaluation*: the caveat banner stays, and the lead row reads "12/12 · n = 12 scenarios written by the team".
- No page uses "safe", "compliant" or "validated" without a qualifier (enforced by a copy lint).

### Should

**CL-1.** As a clinical lead receiving a second-tier escalation, I want a time-ordered handover, so that I can take
over without reconstructing the history.
- *Case timeline*: a **Handover** section at the top for any case with escalation level ≥ 2. It lists each escalation
  rung with paged time, response state and elapsed time, with each line linked to its audit sequence number.
- It shows "Patient waiting: 46 min since finalised" in a large numeral.
- It is readable at 375 px width with no horizontal scroll.

**SUP-3.** As a supervisor, I want to see who acknowledged, for which revision, and how that was checked, so that I
never accept a relative's reply.
- *Case timeline → Evidence & delivery*: the acknowledgment row shows Responder · Matched registered contact? (yes or
  no) · Revision acknowledged vs current revision · Method.
- In S9 the row shows "Responder: not the registered contact (reply text: 'This is his daughter…')" with a warning
  callout.
- In S2 and S5 an acknowledgment for R1 shows "for an earlier revision (R1); current is R2", and the stage does not
  advance.

**SUP-4.** As a supervisor, I want each delivery stage to show the transport evidence behind it, so that I can tell
accepted from delivered from acknowledged.
- *Simulator* "Delivery" cell becomes a three-step mini-chain: Accepted (gateway ref, time) → Delivered (DLR time or
  "no receipt: unknown") → Acknowledged (person, time).
- S8 shows "Accepted 15:01 · no delivery receipt after 30 min · state unknown" and never "Delivered".
- The copy "1 attempts" is fixed to correct plurals.

**QM-2.** As a quality manager, I want the Audit trail in plain language with the raw JSON one click away, so that I
can review a case in minutes.
- *Audit trail* "Summary" column shows a sentence, e.g. "Reviewer objected: unapproved channel (model, confidence
  0.44)". The JSON (including keys such as `noul`) sits in a row disclosure.
- Filter chips for Actor type (Lab, System, Agent, Gate, Person) and Event kind, as in the PagerDuty timeline.
- "chain valid" names what was verified: "57 of 57 entries recomputed from stored rows; no break".

**REG-3.** As a regulator, I want every gap linked to the scenarios and trace steps that surface it, and every clause
linked to where it was used, so that I can audit both directions.
- *Standards & gaps → Gap register*: each row has "Surfaced in: S3a step 2, S10 step 2" links into the *Decision
  trace*.
- *Sources*: each excerpt has "Cited in N runs" linking to *Case timeline → Evidence*.
- *Simulator* "policy gap surfaced at step 2: FALLBACK_UNAUTHORISED" links to GR-04.

**REG-4.** As a regulator, I want comparator and out-of-jurisdiction clauses to be unmistakable wherever they appear,
so that a foreign rule is never read as UAE law.
- Every citation chip carries one of three words: **Binding (Dubai)**, **Binding (UAE federal)**, **Comparator: not
  binding here**, with the jurisdiction code in the tooltip.
- In S6 the Abu Dhabi clause shows "Comparator: not binding here" on *Side-by-side*, *Trace* and *Case timeline*.
- The gap register's ID column does not wrap (`GR-01` on one line).

**JDG-5.** As a judge, I want the Evaluation table to tell good from bad at a glance, so that the score is legible
in 10 s.
- *Evaluation*: "Safe scenarios" chips are graded (12/12 strong neutral or ok, 9–11 light, ≤ 4 red outline). The
  "Replay" column uses neutral tags, not green.
- Column headers are full words with a one-line definition on hover ("Unauthorised channel: a send on a channel
  without an approved procedure").
- The full-system row is first, and the strongest competitor baseline (`static_rules`, 11/12) has a "best baseline"
  marker.

**JDG-6.** As a judge, I want the Arabic retrieval to be visible and explained, so that I can credit Arabic
knowledge-base coverage.
- *Standards → Retrieval* opens with an Arabic example query chip next to the English one.
- When results come from English sources, a note says "Arabic query matched English text via [method]; Arabic source
  text available: yes or no".
- The engine status ("BM25 only; vector store not running in this build") is a neutral inline note, not an amber
  banner.

**REG-5.** As a regulator, I want a persistent "what this system does not do" statement on operational pages, so that
the advisory boundary is never in doubt.
- The three-card panel now on the Console ("No clinical judgement / No advice to patients / No compliance claim") is
  available in the top bar as "Limits", one click from every page.
- *Decision trace* states once per run: "Agents advise; only the deterministic gate changes state; agents can only
  escalate to a person."

**PT-1.** As a patient (via the reviewer), I want the exact outbound message to be visible, so that reviewers can
check it gives no diagnosis and directs me to medical advice.
- *Simulator* and *Case timeline*: for each send, a **Message as sent** preview (channel, sender ID, text) with the
  sourced basis "ST-28 §11.1.2 (guidance): direct the patient to seek medical advice".
- For genetic scope, the preview shows the physician-addressed message and "Patient channel not used (ST-28 §13.4)".

**CL-2.** As a clinical lead, I want to accept or hand back an escalation explicitly, so that ownership is never
ambiguous.
- *Escalation card*: buttons "Accept ownership" and "Cannot take: return to supervisor with reason", both writing
  audit events (simulated in the prototype).
- Once accepted, the Console shows the owner's name, and the escalation timer stops (PagerDuty semantics).

### Could

**QM-3.** As a quality manager, I want a stage-dwell view, so that I can see where cases wait longest.
- *Console*: hovering a chain stage shows median and max time in stage across live cases.
- A stage with any case older than its configured clock shows an amber outline. It is labelled "institutional clock
  (not statutory)" because ST-28 sets none (GR-03).

**QM-4.** As a quality manager, I want to see the institutional profile that governed a run, so that I can tell facility
policy from regulation.
- *Simulator* header shows "Facility profile: fallback approved: no · ack clock: 30 min (institutional)" with a link
  to *Standards → Institutional profile*.

**SUP-5.** As a supervisor, I want keyboard triage on the Needs-a-person list, so that I can work through escalations
quickly.
- `j/k` move, `Enter` opens, `a` accepts (with confirm). The focus ring is visible, as in the existing `:focus-visible`
  rule.

**REG-6.** As a regulator, I want core status labels in Arabic, so that Arabic-speaking colleagues can follow a
projected demo.
- A language toggle (EN | ع) switches the about 20 status and classification labels and the page titles. Layout
  direction switches to RTL for those pages. Strings are reviewed by a native speaker.

**JDG-7.** As a judge, I want the Y.3172 mapping to point at live pages, so that alignment is demonstrable rather than
asserted.
- *Standards → ITU-T Y.3172 mapping*: each node (SRC, collector, MLFO, sink…) links to the page or step where it
  appears.

### Won't (this release)

- **Real paging, SMS or authentication.** The product is offline by design, and the README and banner say so.
- **A patient-facing view.** Outbound-only, and recorded as a gap.
- **Live multi-user queues.** No identity model.

**Count:** 26 user stories (10 Must, 11 Should, 5 Could) plus 3 explicit Won'ts.

---

## 5. UX problems in the current console, prioritised

Score = severity (1–4) × frequency (1–3). "Where" cites the screenshot and the code.

| # | Score | Problem | Where | Evidence and why it matters | Fix (story) |
|---|---|---|---|---|---|
| U1 | **12** (4×3) | **Incident origin is invisible.** No page shows that a scenario was reconstructed from a published incident, its source or its match strength. | All pages; `engine.py:1436-1447` omits `provenance`; no `provenance` render in `web/src` | The scenario files carry sources (PSNet, CRICO, Medical Protection, BMJ OQ, PubMed) and match labels. Without them, a judge sees invented `SYN-CASE` records and may discount criterion 2. | JDG-1, JDG-4 |
| U2 | **12** (4×3) | **The colour semantics are inverted.** Escalation (the safe outcome) is red. A false closure (`DELIVERY_CONFIRMED` under policy-blind) is amber. "run complete" and "chain valid" are green next to red states. | `ui.tsx:244-254`; `console.png` (red chips on 6 of 7 rows); `frame_05-channel.png` (both sides amber); `v3_simulator.png` (red state + green "run complete") | Alert-fatigue literature: red must be scarce to keep meaning (Ancker 2017). A regulator reading `console.png` would conclude the system is failing most cases. | REG-1 |
| U3 | **9** (3×3) | **Raw internal vocabulary used as UI copy.** State enums, `BINDING_REQUIREMENT`, `VERIFIED_AGAINST_SOURCE`, `SOURCE_AMBIGUITY`, `INV-9`, "obligation COMMUNICATED, clause S1-11.1.3, settled 1.00, gap NONE", `` `case.recent_events` ``, "AGENT:analyst", "ASSURANCE(code):AGENT:reviewer", path `evaluation/agent_runs/`. | `console_trace.png`; `v3_standards.png`; `frame_09-kb.png`; `frame_10-eval.png`; Simulator config description | Matches no real-world language for P1–P4 (NN/g heuristic 2, [match between system and the real world](https://www.nngroup.com/articles/ten-usability-heuristics/)). Judges must decode it inside 3 minutes. | ALL-1 |
| U4 | **9** (3×3) | **Baselines pollute operational counts; duplicate-looking IDs.** "Delivered 2" counts two policy-blind runs. Four rows read `SYN-CASE-003`. The header says "16 in this store" but the table shows 10 with no "show all". | `console.png`; `Dashboard.tsx` (`slice(0, 10)`, `split("-").slice(0, 3)`) | P3's first question ("is anything closed for the wrong reason?") can't be answered. Counts appear to contradict each other (11 escalated + 2 delivered + 3 documented = 16, of which several are baselines). | QM-1 |
| U5 | **9** (3×3) | **No "what happens next / who must act".** The state chip and a paragraph of open questions, but no owner, deadline, authorised action or next step. | `v3_simulator.png` "Case state" panel; `frame_08-genetic.png` escalations cell | This is the core human hand-off (CLSI GP47 escalation; CRICO case). The product's distinctive behaviour has no screen. | SUP-1, SUP-2, CL-1 |
| U6 | **8** (4×2) | **The "owner and a deadline" claim is not shown.** The tile copy promises an owner and a deadline. Escalations render as role enums (`SUPERVISOR, CLINICAL_LEAD`) without times or response state. | `console.png` exit tile; `Dashboard.tsx` `EXITS[0].why`; `frame_08-genetic.png` | Copy that promises data the UI does not show erodes trust with exactly the reviewers who check claims (P3, P4). | SUP-1, CL-1 |
| U7 | **8** (4×2) | **The trace leads with the wrong answer, unlabelled.** The policy analyst's claim that the daughter's reply "confirms communication… satisfying the duty" appears first with a neutral `ANSWERED` chip. "Assurance check on the analyst · UPHELD" is ambiguous. Raw `p=0.93` strings follow. | `console_trace.png` | A reader may think the system endorsed the error. Bansal 2021: explanations raise acceptance regardless of correctness. Disagreement and code checks must lead. | REG-2 |
| U8 | **6** (3×2) | **Side-by-side understates its finding.** The verdict is a small grey hint, "different final state". `#5 INV-9` is unexplained. The default pair (council vs rules-only) usually shows no difference. About 60% of the viewport is empty. | `frame_05-channel.png`; `Compare.tsx:20-21, 103-111` | This page is the strongest 30-second evidence for a judge (02-user-stories EV-2), and it currently needs interpretation. | JDG-3 |
| U9 | **6** (3×2) | **No guided entry, and the IA mixes modes.** "Operate" groups the Console with the Simulator, Side-by-side and Decision trace, which are demonstration and audit tools. There is no "Start here". | `App.tsx` `NAV` | A time-poor first visit lands on counters. The story order (problem → incident → replay → compare → evidence) is not reflected. | JDG-2 |
| U10 | **6** (3×2) | **Retrieval shows an infrastructure fault first.** An amber banner reads "hybrid retrieval requested but the ChromaDB store or Ollama is unavailable; BM25 only". "45 excluded" is stated twice. The Arabic query returns English text without explaining the match. | `v3_standards.png` | Criterion 1 (KB quality and retrieval). An amber banner reads as "broken" to a judge. Arabic capability is shown but not explained. | JDG-6 |
| U11 | **6** (3×2) | **Gaps, clauses and scenarios are not cross-linked.** The Simulator says "policy gap surfaced at step 2: FALLBACK_UNAUTHORISED" but doesn't link to GR-04. Gap rows don't link to scenarios. | `v3_simulator.png`; `frame_09-kb.png` | Criterion 3 (gap identification) and criterion 4 (source attribution) are strongest when traversable. | REG-3 |
| U12 | **6** (2×3) | **The open-questions wall.** An unbounded paragraph in a one-third-width cell mixes model objections, missing citations and gap codes. | `v3_simulator.png` (`frame_08` partly improved with bullets and "and 3 more in the trace") | Dense text in the place a supervisor looks for the next action. | SUP-2 |
| U13 | **6** (3×2) | **Positive verification shown in warning colour.** `VERIFIED_OFFICIAL` and `ABSENCE_SEARCHED` render amber. The ID wraps to "GR-/01". | `frame_09-kb.png` | Amber on "verified" tells a regulator the opposite of the truth. | REG-4, ALL-1 |
| U14 | **4** (2×2) | **Evaluation colour doesn't discriminate.** 11/12 and 3/12 are both amber. Green is spent on "stable" replay. Abbreviated headers ("Unauth. channel", "Comparator as binding", "Send provenance 0.00"). The definitions sit below the fold. | `v3_evaluation.png`; `Evaluation.tsx:104, 118, 162` | The caveat banner is exemplary and should stay. The table itself needs 10-second legibility. | JDG-5 |
| U15 | **4** (2×2) | **The Audit summary is raw JSON.** Agent messages are dumped as JSON (including the key `noul`). There are no filters. | `frame_10-eval.png` (Audit trail) | Criterion 4 is about auditability for humans. PagerDuty-style filters and plain summaries are the norm. | QM-2 |
| U16 | **4** (2×2) | **Times have no date or zone.** "15:45:00", and "finished 20:49:53" with no date. `fmtTime` uses the browser locale. | `console.png` audit feed; `v3_evaluation.png`; `ui.tsx:264-269` | Audit evidence needs an unambiguous timestamp (Dubai is UTC+4; a judge in Geneva sees a different local time). | QM-2 |
| U17 | **3** (3×1) | **The Trace page dead-ends from a cold start**: "No runs in memory… traces are served from the live run". | `Trace.tsx:89-93` | A judge who opens Decision trace first sees nothing. Seed one run on load or link straight to "Run S9 now". | JDG-2 |
| U18 | **2** (2×1) | **Deterministic rule assessors display a "confidence"** ("escalation_coordinator RECORD_DOCUMENTATION confidence 0.6"). | `console_trace.png` top | This blurs the "deterministic gate vs probabilistic agents" boundary that is the product's design claim. | REG-2 |
| U19 | **3** (1×3) | **Copy polish.** "1 attempts", "attempt(s)", "chunk(s)". The scenario select truncates mid-word ("…for a fa"). Labels are slug-first ("S3a-channel-outage-no-evidence — Primary…"). | `v3_simulator.png`; `frame_05-channel.png` | Small, but judges read polish as care. Use the title first, with the slug as secondary text. | ALL-1 |
| U20 | **2** (2×1) | **No Arabic UI, and the outbound message is not shown.** The patient-facing text is never displayed for review. | All pages | This matters to P4 (UAE federal ecosystem, UAE Design System) and protects P6. | PT-1, REG-6 |

**Keep as they are:** the disclaimer in the sidebar foot and the "Synthetic data, offline" badge. The Evaluation
caveat banner ("These numbers are not a safety or compliance claim…"). The "Confidence (author rating)" header on the
gap register, which is honest. The stage notes under the chain ("accepted is not delivered", "delivered is not
acknowledged"), which are the best copy in the product. The hash shown inline in the audit feed. The rows-as-links on
the Console. The "Recomputed from stored rows; the writer's claim is not trusted" line on Audit.

---

## 6. Language guidance: saying "reconstructed from a published incident; identities invented" honestly

### 6.1 Principles

1. **Make two separate claims, and keep them both visible.** (a) The *failure mode* is real and published. (b) The
   *people, numbers, timings and results* are invented. Never let (a) imply the record is real, and never let (b)
   imply the scenario is made up.
2. **Calibrate the verb to the match.** The scenario files already store a match strength. Use it, and don't round
   it up.
3. **Name the source and link it.** "A published case" without a citation is a claim. "AHRQ PSNet WebM&M (2017)" with
   a link can be checked.
4. **Say what was changed.** The setting moved to a Dubai walk-in laboratory, the channel became SMS, and the actors
   and values are invented. A reader should know the original was, for example, a US inpatient blood-culture case.
5. **Put it where the claim is made**, not only in the README: the scenario picker, the run header, the trace header,
   the comparison header, the exported bundle, the video lower-third and the report.

### 6.2 Three tiers of wording, mapped to the stored `provenance.match` values

| Stored match | Verb to use | Scenarios | Template |
|---|---|---|---|
| `very strong`, `almost exact` | **Reconstructed from** | S9, S2, S10 (S3a, see 6.4) | "Reconstructed from a published incident: *[source, year]*. Setting, people and values invented." |
| `strong`, `close` | **Adapted from** | S1, S11, S8, S3b | "Adapted from the failure described in *[source, year]* (*[original setting]*). Moved to a Dubai walk-in laboratory; people and values invented." |
| `related`, `related, not exact` | **Informed by** | S5, S4, S7 | "Informed by *[source]*. The specific sequence here was designed by the team to test *[rule]*." |
| *(no provenance)* | **Designed test** | S6 | "Designed test with no incident source. It checks that a highly relevant Abu Dhabi clause is never applied to a Dubai case." |

### 6.3 Exact strings

- **Global badge (top bar, all pages):** "Synthetic records · identities invented · offline". Expanded: "Every
  patient, person, number and timing here is invented. Most scenarios are adapted from published patient-safety
  incidents; each scenario shows its source. No hospital system, patient data or live messaging is connected."
- **Origin card (Simulator, Compare, Trace), S9 example:**
  > **Reconstructed from a published incident** · Medical Protection Casebook (Asia, July 2017) and *Digital
  > dilemmas: communicating with patients by text* · match: very strong
  > *What happened there:* a result reached, or was asked for by, a relative rather than the patient.
  > *What we changed:* Dubai walk-in laboratory, SMS reply from the patient's daughter, invented names and values.
  > [Read the source ↗]
- **S11 example:** "**Adapted from** AHRQ PSNet WebM&M (2017), *Delayed recognition of a positive blood culture*,
  and BMJ Open Quality (2021). There, a result reached a nurse and an inbox but not the responsible doctor in time.
  Here: an SMS delivery receipt with no acknowledgment. Invented people and values."
- **Exported bundle (`bundle.json` top level):** `"scenario_origin": {"tier": "adapted_from", "sources": [...],
  "identities": "invented", "statement": "..."}`, with the same sentence as the card.
- **Video lower-third:** "Scenario reconstructed from a published incident (Medical Protection, 2017). Names and
  values invented."
- **Arabic (draft for native-speaker review; do not ship unreviewed):** «سيناريو مُعاد بناؤه من حادثة منشورة تتعلق
  بسلامة المرضى. الأسماء والقيم افتراضية.» Avoid «مُختلَقة» ("fabricated"), which reads as deceptive.

### 6.4 Wording to avoid, and two claims to recheck before submission

- **Avoid:**
  - "real case", "true story" or "based on a real patient": the records are not real.
  - "every scenario is reconstructed from a published incident": S6 has no source, and three scenarios are only
    "related".
  - "proven safe", "compliant" or "validated against DHA": the Evaluation banner already disclaims these, so keep
    everything consistent with it.
  - "the AI decided": agents advise and the gate decides.
- **README hero (line 20)** says "Every scenario is reconstructed from a published patient-safety incident". Line 411
  correctly says S6 has none. Change the hero to "Eleven of twelve scenarios are drawn from published
  patient-safety incidents or studies (four closely reconstructed)", with the count computed from the files.
- **Match labels that look generous on a reviewer's reading:**
  - **S3a** (channel outage) is labelled `almost exact` to the CRICO 2023 case. That case is about an attending who
    did not answer a page, with no channel outage, so the closer pairing is S10.
  - **S8** (accepted by the gateway, never delivered) is labelled `strong` against sources that involve inbox and nurse
    hand-offs, not carrier acceptance.

  Recommend **S3a → "Adapted from"** and **S8 → "Informed by"**, with SMS delivery-receipt semantics cited as the
  technical basis ([Bird](https://bird.com/explained/sms/what-is-a-delivery-receipt);
  [Optus](https://sms.optus.com.au/docs/en/sms-delivery-info/mobile-delivery-receipts/)). A judge who clicks through
  and finds a weaker match than claimed will discount the rest.

---

## 7. Validation plan (before the 8 Dec onsite final)

| Test | Who (n) | Task | Pass criterion |
|---|---|---|---|
| 5-second test on the Console | 5 people outside the team, at least 2 with lab or clinical background | "What does this product do, and is anything wrong right now?" | ≥ 4 of 5 say "communicating critical results to a person", and none say "most cases are failing" (tests U2) |
| 3-minute judge simulation | 3 (an ITU-style technical reviewer, a policy person, a clinician) | Score the 5 criteria from the console only | Every criterion gets cited evidence from a page. Median time to the first incident source is under 20 s (tests U1, JDG-2) |
| Escalation card think-aloud | 2 pathologists or lab supervisors (UAE if possible) | S10 and S9: "What would you do now?" | Both name the authorised action and refuse the relative's reply without prompting (SUP-2, SUP-3) |
| Regulator walkthrough | 1 policy or compliance person | Genetic routing (Journey C) | Finds §13.4 and GR-05 within 2 minutes without help |
| Arabic label check | 1 native Arabic speaker with clinical vocabulary | Review the status vocabulary and §6.3 strings | No term reads as alarming or deceptive |

---

## Sources

**Standards and regulation**
- DHA ST-28 *Standards for Clinical Laboratory Services*, Issue 2 (2023): https://dha.gov.ae/uploads/052023/Standards%20for%20Clinical%20Laboratory%20Services2023552664.pdf (verified excerpts: `kb/records/S1_dha_st28.yaml`)
- Joint Commission NPSG.02.03.01 (Laboratory NPSG chapter): https://jointcommission.org/-/media/tjc/documents/standards/national-patient-safety-goals/2024/npsg_chapter_lab_jan2024.ash
- CLSI GP47: https://clsi.org/shop/standards/gp47/ · summary: https://labmedicineblog.com/2015/12/11/clsi-publishes-a-new-document-on-management-of-critical-and-significant-risk-results/
- CAP critical-result notification and read-back (example lab form citing GEN.41320/41330): https://www.downstate.edu/patient-care/lab-services/_documents/LAB-34_wm.pdf
- RCPath G158: https://www.rcpath.org/resourceLibrary/g158-bpr-the-communication-of-critical-and-unexpected-pathology-results.html
- ONC SAFER Guide 8, Test Results Reporting and Follow-up (Aug 2024): https://www.healthit.gov/sites/default/files/topiclanding/2025-01/8.%20Test%20Results%20Reporting%20Final.pdf
- NHS trust telephoned pathology results policy (SFH v4.0, 2025): https://www.sfh-tr.nhs.uk/media/dxunc531/telephoned-pathology-results-policy-v40-issued-090625.pdf
- ITU AI for Good Sandbox Hackathon (UAE): https://aiforgood.itu.int/event/ai-for-good-sandbox-hackathon-united-arab-emirates/

**Studies and incidents**
- BMJ Open Quality 2021, closed-loop critical results with team smartphones: https://pmc.ncbi.nlm.nih.gov/articles/PMC8442100/
- AHRQ PSNet WebM&M, delayed recognition of a positive blood culture: https://psnet.ahrq.gov/web-mm/delayed-recognition-positive-blood-culture
- AHRQ PSNet WebM&M, amended lab results: https://psnet.ahrq.gov/web-mm/amended-lab-results-communication-slip
- CRICO/Harvard RMF 2023, discharged patient with pending test results: https://rmfcd1-prod.rmf.harvard.edu/Risk-Prevention-and-Education/Case-Study-Catalog-Page/Case-Study/2023/Discharged-Patient-with-Pending-Test-Results
- Medical Protection, *Digital dilemmas*: https://www.medicalprotection.org/uk/articles/digital-dilemmas-communicating-with-patients-by-text
- Adverse events in genetic testing, case series (2019): https://pubmed.ncbi.nlm.nih.gov/31335384/
- Murphy et al. 2016, burden of inbox notifications: https://pmc.ncbi.nlm.nih.gov/articles/PMC4860883
- Singh et al. 2009, imaging alerts follow-up: https://pmc.ncbi.nlm.nih.gov/articles/PMC3445672 · Singh 2010, lab alerts: https://psnet.ahrq.gov/issue/notification-abnormal-lab-test-results-electronic-medical-record-do-any-safety-concerns
- Callen et al. 2011, missed test results in hospitalised patients: https://qualitysafety.bmj.com/content/20/2/194
- Valenstein et al. 2008, CAP Q-Probes, 121 institutions: https://www.captodayonline.com/Archives/feature_stories/0208_Qprobe.html
- Ancker et al. 2017, alert fatigue: https://psnet.ahrq.gov/issue/effects-workload-work-complexity-and-repeated-alerts-alert-fatigue-clinical-decision-support
- ADLM CLN 2024, critical-result notification preferences: https://myadlm.org/cln/Articles/2024/SeptemberOctober/Critical-result-notification-preferences
- Bansal et al. CHI 2021, AI explanations and team performance: https://arxiv.org/abs/2006.14779
- Dubai population by nationality (DSC series): https://gulfmigration.grc.net/uae-dubai-estimates-of-population-by-nationality-emiratis-non-emiratis-at-selected-dates-1975-2016/

**Products and design systems**
- PerfectServe critical results: https://www.perfectserve.com/integrations/clinical-alerts-critical-results/ · HSS case: https://www.healthcareitnews.com/news/hospital-special-surgery-accelerates-speed-care-vulnerable-patients
- TigerConnect critical labs: https://tigerconnect.com/?p=9047
- Vocera Engage: https://www.stryker.com/content/dam/stryker/acute-care/vocera/resources/solution-briefs/vocera-engage-solution-brief.pdf · message states: https://pubs.vocera.com/rnotes/ReleaseNotes_engage_mobile_ios_5.2_sr0.html
- Epic In Basket notes: https://medicine-matters.blogs.hopkinsmedicine.org/2020/01/epic-tip-of-the-week-january-31-2020/ · https://eristest2-6.partners.org/?p=12000
- PagerDuty incidents: https://support.pagerduty.com/docs/incidents · incident.io roles: https://docs.incident.io/incidents/roles · Linear workflows: https://linear.app/docs/configuring-workflows
- Flight progress strips: https://skybrary.aero/articles/flight-progress-strips · https://www.saab.com/products/electronic-flight-strips-EFS · https://ntrs.nasa.gov/api/citations/20030068998/downloads/20030068998.pdf
- GOV.UK tag: https://design-system.service.gov.uk/components/tag/ · task list iteration: https://designnotes.blog.gov.uk/2023/12/15/working-as-a-community-to-iterate-the-task-list-pattern/
- NHS warning callout: https://service-manual.nhs.uk/design-system/components/warning-callout
- UAE Design System (TDRA): https://designsystem.gov.ae/about · https://www.wam.ae/en/article/b36k4xe-tdra-launches-uae-design-system-20-for-federal
- SMS delivery receipts: https://bird.com/explained/sms/what-is-a-delivery-receipt · https://sms.optus.com.au/docs/en/sms-delivery-info/mobile-delivery-receipts/
- NN/g usability heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/
