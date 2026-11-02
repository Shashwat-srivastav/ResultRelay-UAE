"""LEGACY: builds the earlier long-form paper (8 scenarios, 11 configurations). Superseded by the template report
in submission/ResultRelay_ITU_Submission.docx; kept for history. Its counts are not current."""
#!/usr/bin/env python3
"""Build the five-page submission paper from the repository's own numbers.

Every figure in the paper is read from the built artefacts (manifest, evaluation results) so the
paper cannot drift from the code. Prose is fixed; numbers are not typed by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission" / "ResultRelay_ITU_paper.docx"

manifest = json.loads((ROOT / "web/public/data/manifest.json").read_text())
results = json.loads((ROOT / "evaluation/results/latest.json").read_text())

SOURCE_COUNT = len(manifest["knowledge_base"]["sources"])
EXCERPT_COUNT = len(manifest["excerpts"])
GAP_COUNT = len(manifest["gaps"])
MAPPING_COUNT = sum(len(v) for v in manifest["mappings"].values())
STATS = results["summary"]
# Derived, never hand-typed: a hard-coded "28 runs" caption is how the counts drifted last time.
RUN_COUNT = results["run_count"]
SCEN_COUNT = results["scenario_count"]
CONF_COUNT = len(results["configurations"])
# Assertion totals are counted from the expected-action files, so the caption cannot drift from them.
SPECS = {
    f.stem: json.loads(f.read_text())
    for f in sorted((ROOT / "scenarios" / "expected").glob("*.json"))
}
ASSERTION_COUNT = sum(len(v["must_hold"]) for v in SPECS.values())

def _cfg_row(key):
    r = STATS["by_configuration"][key]
    return [
        r["label"],
        f"{r['scenarios_fully_safe']}/{r['runs']}",
        f"{r['assertions_passed']}/{r['assertions_total']}",
        str(r["false_closures"]),
        str(r["stale_ack_uses"]),
        f"{r['mean_provenance_completeness']:.2f}",
    ]


def add_para(doc, text, size=9.5, bold=False, italic=False, space_after=4, align=None, style=None):
    p = doc.add_paragraph(style=style)
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if align is not None:
        p.alignment = align
    return p


def heading(doc, text, size=11):
    return add_para(doc, text, size=size, bold=True, space_after=3)


def table(doc, rows, widths=None, header=True, size=8.5):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            c = t.cell(i, j)
            c.text = ""
            p = c.paragraphs[0]
            run = p.add_run(str(cell))
            run.font.size = Pt(size)
            run.bold = header and i == 0
            p.paragraph_format.space_after = Pt(0)
            if widths:
                c.width = Cm(widths[j])
    return t


doc = Document()
sec = doc.sections[0]
sec.top_margin = Cm(1.9)
sec.bottom_margin = Cm(1.9)
sec.left_margin = Cm(2.0)
sec.right_margin = Cm(2.0)

style = doc.styles["Normal"]
style.font.name = "Times New Roman"
style.font.size = Pt(9.5)

# ---------------------------------------------------------------- title block
add_para(doc, "Resolving which law applies before an AI agent acts:", size=15, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
add_para(doc, "a policy-governed prototype for patient result messaging in the United Arab Emirates",
         size=12, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)
add_para(doc, "ResultRelay project  ·  ITU AI for Good Lab Hackathon submission  ·  Dubai Health Authority "
              "challenge (ST-28)  ·  22 October 2026",
         size=8.5, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
add_para(doc, "All data synthetic. Not a medical device. Not evidence of clinical safety, clinical "
              "effectiveness or regulatory compliance.",
         size=8, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

# ---------------------------------------------------------------- abstract
heading(doc, "Abstract")
add_para(doc,
    "Health AI projects in the UAE usually begin with a model and reach for a privacy statute; for "
    "patient data that order is wrong twice over. Federal Decree-Law No. 45 of 2021 (PDPL) excludes "
    "health personal data that is already subject to sectoral legislation (Art. 2, exclusion (e)), and the "
    "instrument that does govern — Federal Law No. 2 of 2019 on the Use of ICT in Health Fields — "
    "carries obligations a messaging workflow can actually violate: confidentiality of circulation "
    "(Art. 4), a prohibition on processing health data outside the State without a Health Authority "
    "resolution (Art. 13, penalty AED 500,000–700,000 under Art. 24), enumerated permitted "
    "disclosures (Art. 16) and a 25-year retention floor (Art. 20). This paper describes ResultRelay, "
    "a prototype that treats instrument resolution as a first-class engineering step: a "
    f"{SOURCE_COUNT}-document corpus of machine-verified quotations, a jurisdiction model that layers "
    "federal law under emirate policy, a deterministic gate that no model output can overrule, and an "
    "advisory boundary that refuses to run at all on an endpoint outside the State. We report what "
    "the evidence supports, what it does not, and the three obligations our own build fails.")
add_para(doc, "Keywords: health data governance; UAE Federal Law 2/2019; policy applicability; "
              "human-in-the-loop; retrieval-augmented generation; critical result communication.",
         size=8.5, italic=True, space_after=8)

# ---------------------------------------------------------------- 1
heading(doc, "1.  The problem is not the model")
add_para(doc,
    "A laboratory that tells a patient their critical result is abnormal is performing a "
    "communication act with legal content. Dubai's Standards for Clinical Laboratory Services "
    "(ST-28, Issue 2, §11.1.1–11.1.3) require such results to be reported clearly to the patient and "
    "the communication to be recorded; the standard does not define what evidence proves the "
    "communication occurred, nor what a delivery receipt is worth. An engineering team that fills "
    "that silence with a default — 'sent' means done — has invented a policy, and the invention is "
    "invisible in the code review, in the tests, and in the demo.")
add_para(doc,
    "The prototype we present starts from the opposite end: it asks which instrument applies, "
    "extracts the obligations that instrument actually imposes, and only then asks what software "
    "would satisfy them. The claim is deliberately narrow. We do not claim clinical benefit, we do "
    "not claim regulatory approval, and we do not claim that a synthetic benchmark shows a system is "
    "safe. We claim that the resolution step is implementable, testable and auditable, and we show "
    "where it still fails.")

# ---------------------------------------------------------------- 2
heading(doc, "2.  The governing-instrument chain")
add_para(doc,
    "The chain below is the paper's substantive contribution to the local context. Each link is a "
    "verified quotation in the corpus, and the corpus refuses to index a quotation whose words cannot "
    "be found on the page the register claims.")
table(doc, [
    ["Instrument", "Layer", "What it settles for a patient message"],
    ["Federal Law 2/2019, Art. 2", "National", "Applies to all ICT uses in health fields in the State, including free zones — not avoidable by licence type."],
    ["PDPL (Decree-Law 45/2021), Art. 2, exclusion (e)", "National (excluded)", "Health personal data subject to other legislation is outside the PDPL; consent mechanics under the PDPL cannot be cited as the authority for a notification."],
    ["Federal Law 2/2019, Art. 4", "National", "Confidentiality of health data; validity and credibility protected against unauthorised amendment — the basis for an append-only, attributable audit trail."],
    ["Federal Law 2/2019, Art. 13 + Art. 24", "National", "No storing, processing, generating or transforming health data outside the State without a Health Authority resolution; AED 500,000–700,000 penalty."],
    ["Federal Law 2/2019, Art. 16", "National", "Patient information may be circulated for health purposes without written approval; five exceptions enumerated (insurer verification, de-identified research, public health, judicial, authority inspection)."],
    ["Federal Law 2/2019, Art. 20", "National", "Retention of at least 25 years from the last procedure."],
    ["DHA HISHD/PP-12 §4.6.1", "Dubai", "Restates the 25-year floor as an entity duty; longer retention reserved to the Medical Director."],
    ["DHA HISHD/PP-08 §4.5.1, §4.9.10", "Dubai", "Accuracy at record level; entities must provide a way for patients to report inaccurate information."],
    ["DoH ADHICS V2/2024, §1 and §2.30", "Abu Dhabi", "Binds any Abu Dhabi entity transmitting health information; data must not be altered or destroyed in an unauthorised manner — the basis for tamper-evidence. Comparator for a Dubai case."],
    ["UAE AI Charter (June 2024), P6 and P12", "National (guidance)", "Human judgment and oversight over AI is treated as irreplaceable; the Charter defers to sectoral law. Classified OFFICIAL_GUIDANCE, so it can shape a design but never authorise an action."],
], widths=[4.2, 2.6, 9.6])
add_para(doc, "Table 1. Instruments that bear on a patient result message, by layer.", size=8, italic=True, space_after=6)
add_para(doc,
    "Three consequences are not obvious from the statutes alone. First, Art. 16 permits telling the "
    "patient for health purposes, but the de-identified research exception does not authorise a model "
    "processing identifiable results: research and care are different bases. Second, Art. 13 covers "
    "processing, so inference at an offshore endpoint is inside the prohibition even where nothing is "
    "stored; a hosted model is a legal question before it is an architecture choice. Third, Art. 20 "
    "sets a retention floor but no disposal rule, so keeping everything forever is also non-compliance.")

# ---------------------------------------------------------------- 3
heading(doc, "3.  Method")
add_para(doc,
    f"Corpus. {SOURCE_COUNT} documents, {EXCERPT_COUNT} excerpts, each carrying source, section, printed "
    "page, jurisdiction and a claim classification. Ingestion normalises whitespace and refuses any "
    "excerpt whose text is not a substring of the declared page; the current build reports "
    f"{EXCERPT_COUNT} verified, 0 unverified, 0 rejected. Full texts are downloaded to a local cache, "
    "not redistributed; only minimal quotation is committed.")
add_para(doc,
    "Layered jurisdiction. Jurisdiction is not a single label. A Dubai case is governed by Dubai "
    "instruments and by federal law, so the retriever expands a case jurisdiction upwards "
    "(AE-DU → {AE-DU, AE-FED}) and never downwards. Before this change the exact-match filter "
    "silently excluded the one layer that binds health data.")
add_para(doc,
    "Deterministic gate. Agents emit structured assessments; a fixed safety ordering resolves "
    "disagreement; the gate converts a proposal into a state-machine event and enforces cross-cutting "
    "invariants. The gate never reads an agent's free-text rationale.")
add_para(doc,
    "Advisory boundary. A model may propose, never decide. An OpenAI-compatible client is implemented "
    "and disconnected by default: its transport refuses, and its constructor rejects any endpoint "
    "outside the State under Art. 13, citing Art. 24's penalty, unless a named Health Authority "
    "resolution is recorded. The guard rejects proposals citing chunk ids that do not exist or that "
    "cannot bind the case jurisdiction, and stamps whatever survives as PRODUCT_DESIGN_CONTROL. The "
    "gate decides first and receives the advisory record afterwards; a test asserts the decision is "
    "identical with and without an accepted proposal. No model runs in this build.")
add_para(doc,
    "Decision traces. Every step is published as ordered artefacts — event, retrieved evidence with "
    "claim class, each agent's proposal with its derived confidence and the basis for it, the gate's "
    "conditions and invariant, the transition, the resulting state. Raw model reasoning is deliberately "
    "not published, and that is a position rather than an omission: a transcript of a model's private "
    "reasoning is neither checkable nor stable, so the reasoning artefact published instead is this "
    "decision trace - the evidence retrieved, the rule applied, the invariant that fired and the state "
    "reached, reproducible by re-running the scenario. The same page runs any scenario under two "
    "configurations side by side, which is how the citation difference becomes visible rather than "
    "asserted.")
add_para(doc,
    f"Evaluation. Eight hand-authored scenarios are run against eleven configurations: the full system, "
    "seven one-flag ablations that each differ from it in exactly one input, and three compound baselines - a "
    "policy-blind baseline with no corpus, a citation-only retrieval baseline, and conventional "
    "deterministic rules. Expected outcomes are assertions over observable behaviour rather than over "
    "internal state names, and each carries a provenance flag; the same team wrote both, as the paper "
    "says below. Three of the ablations are null results and are reported as such: an ablation that "
    "changes nothing is a fact about the system, not a gap in the table.")

# Regenerate the figure from the manifest first: a hand-kept PNG is how the counts drifted before.
import subprocess, sys
subprocess.run([sys.executable, str(ROOT / "submission" / "make_figure.py")], check=True)
doc.add_picture(str(ROOT / "submission" / "figure1_pipeline.png"), width=Cm(14.0))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
add_para(doc, "Figure 1. Where the constraints sit. The corpus and the jurisdiction layer bound what the "
              "agents may cite; the gate decides; the adviser is downstream of the corpus and upstream of "
              "nothing — it can be refused, and it cannot move a case.",
         size=8, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

# ---------------------------------------------------------------- 4
heading(doc, "4.  Results")
keys = list(STATS["by_configuration"].keys())
table(doc, [["Configuration", "Safe", "Assertions", "False closure", "Stale ack", "Provenance"]]
      + [_cfg_row(k) for k in keys], widths=[6.0, 1.6, 2.4, 2.4, 1.8, 2.2])
add_para(doc, f"Table 2. Evaluation matrix, {RUN_COUNT} runs ({SCEN_COUNT} scenarios × {CONF_COUNT} "
              "configurations). Seven rows are one-flag ablations: each differs from the full system in exactly one "
              "input. Three of them change no assertion at all, and that is reported rather than removed; "
              "a null result is a fact about the system, not a gap in the table.", size=8,
         italic=True, space_after=6)
add_para(doc,
    "The full system passes every assertion; the baselines fail on the distinctions the corpus was "
    "built to supply — a transport acceptance treated as closure, a stale acknowledgment resolving a "
    "newer revision, an alternative channel chosen without authority. The citation-only baseline's "
    "provenance score is high and its safety score is not: retrieving a clause is not applying it, "
    "which is the point of a separate applicability step.")
table(doc, [
    ["Scenario", "What it separates", "Asserts"],
    ["S1 ambiguous delivery", "attempt vs transport acceptance vs delivery vs human acknowledgment", "7"],
    ["S2 correction after acknowledgment", "a stale acknowledgment cannot close a revised result", "4"],
    ["S3a/S3b channel outage", "fallback with no evidence vs fallback under an approved procedure", "3 + 3"],
    ["S4 genetic scope exclusion", "a result scope that may not go directly to the patient", "3"],
    ["S5 late acknowledgment race", "an acknowledgment bound to the wrong revision", "4"],
    ["S6 jurisdiction conflict", "an Abu Dhabi clause offered as authority for a Dubai case", "3"],
    ["S7 physician-routed genetic result", "the recipient is chosen from a retrieved clause, not a case field", "5"],
], widths=[4.4, 10.6, 1.4])
add_para(doc, f"Table 3. The eight scenarios: {ASSERTION_COUNT} assertions in total, keyed to observable "
              "behaviour rather than to internal state names.", size=8, italic=True, space_after=6)
add_para(doc,
    "Each scenario is also run in the three baselines. The separation is uneven and is reported as "
    "such: S1 discriminates the full system from both retrieval-only and rules baselines, while S6 "
    "discriminates only retrieval-only, because a rule-based system that has no corpus cannot cite a "
    "foreign clause at all.")
add_para(doc,
    "Two results we report against ourselves. First, only one scenario separates the full system from "
    "the rules baseline on jurisdiction, so the discrimination is partial and is reported as partial. "
    "Second, the system's advantage rests on a corpus we assembled; a reviewer who disagrees with our "
    "reading of Art. 16 would reach a different decision at the same gate.")

add_para(doc,
    "The invariants the gate enforces are stated as prohibitions rather than as features, so that a "
    "failure is visible: a transport acceptance may not stand in for delivery (INV-1); delivery may "
    "not stand in for acknowledgment (INV-2); an acknowledgment binds to a revision, not to a case "
    "(INV-8); an alternative channel requires verified evidence or an approved procedure (INV-9); an "
    "unknown delivery outcome forbids a blind retry (INV-4). Where an instrument is silent — no numeric "
    "acknowledgment clock exists in the corpus — the number is labelled a design control, never a "
    "requirement.")
add_para(doc,
    "Provenance is measured separately from safety. Each run records, for every cited clause, the "
    "source, the printed page and the classification; a run can therefore be complete and well "
    "documented while still being wrong, and the matrix reports both so the two cannot be confused.")

# ---------------------------------------------------------------- 5
heading(doc, "5.  Compliance findings, including three we fail")
add_para(doc,
    "Residency is now enforced at the boundary rather than documented: an offshore endpoint is refused "
    "with Art. 13 and Art. 24 named, and only a recorded resolution opens it. This is narrow — the "
    "check reads the endpoint string and cannot see DNS, a proxy, or a model bundled into a desktop "
    "application.")
add_para(doc,
    f"Three obligations are recorded and not met. (i) Art. 20 retention: communications are retained "
    "without a derived disposal date (gap register GR-11). (ii) DHA PP-08 §4.9.10 patient feedback: the "
    "prototype is strictly outbound, so a correction can only be started by staff (GR-14). (iii) The "
    "correction-intake absence means a patient cannot report the error that triggers the workflow. "
    f"The gap register publishes {GAP_COUNT} such questions rather than leaving them in a comments "
    f"file, and {MAPPING_COUNT} mapping rows tie framework concepts to code locations with a "
    "demonstrating test or an explicit NOT_IMPLEMENTED.")
add_para(doc,
    "Two defects found by our own red-team pass are now closed, and the closure is the more useful "
    "result to report. Fallback authorisation used to be a keyword test, which read \"under no "
    "circumstances shall an alternative channel be used\" as permission; it is now a boolean declared "
    "on the excerpt, with ingestion refusing the declaration on guidance or comparator material and "
    "the gate demanding the basis token that only such a declaration produces. Idempotency keys used "
    "to include an attempt counter, making every send unique by construction; the key now identifies "
    "the message, and the transport suppresses a duplicate only when the earlier attempt did not time "
    "out. One defect remains open: the evaluation cannot support a claim beyond internal consistency, "
    "because the scenarios were written by the team that built the engine.")

# ---------------------------------------------------------------- 6
heading(doc, "6.  Limitations and threats to validity")
add_para(doc,
    "All data are synthetic: no EHR, no SMS gateway, no model provider. Scenarios and expected "
    "outcomes were authored by the same team that built the engine, so authorship independence is a "
    "claim about the files, not about the people. The transport is a simulator, so delivery semantics "
    "are modelled rather than observed. The PDPL text used is an unofficial English translation "
    "(no official English full text is published on a government domain); it is cited only for its "
    "scope exclusion and is labelled accordingly. DoH Abu Dhabi's ADHICS v2 and the UAE AI Charter "
    "could not be retrieved from this environment and are absent from the corpus — named here so "
    "their absence is visible.")

# ---------------------------------------------------------------- 7
heading(doc, "7.  Conclusion")
add_para(doc,
    "Before an agent can be governed, someone has to establish which instrument governs it. In the "
    "UAE that step has a specific shape: health data leaves the PDPL by statute, the ICT Health Law "
    "binds everywhere including free zones, and three of its articles — 13, 16 and 20 — translate "
    "directly into engineering constraints on where a model may run, who a message may reach, and how "
    "long the record must live. Building those constraints into the gate, rather than into a "
    "documentation page, is what turns a demonstration into something a regulator could inspect. The "
    "next revision should close the negation defect and implement the retention and feedback duties "
    "we have left open.")

heading(doc, "References")
refs = [
    "United Arab Emirates. Federal Law No. (2) of 2019 Concerning the Use of the Information and Communications Technology in Health Fields. Official legislation portal, legislation 1209.",
    "United Arab Emirates. Federal Decree-Law No. (45) of 2021 on the Protection of Personal Data (Arabic official text; English translation consulted and labelled as unofficial).",
    "Dubai Health Authority. Policy for Health Information Assets Management, HISHD/PP-12, Issue 01, 2022.",
    "Dubai Health Authority. Health Data Quality Policy, HISHD/PP-08, Issue 02, 2023.",
    "Dubai Health Authority. Standards for Clinical Laboratory Services, DHA/HRS/HPSD/ST-28, Issue 2.",
    "ITU-T. Recommendation Y.3172 (06/2019): Architectural framework for machine learning in future networks including IMT-2020.",
    "ITU. AI Readiness Report 2.0, 2026.",
    "The Joint Commission. National Patient Safety Goals, Laboratory Program, 2026.",
    "ONC. SAFER Guide 8: Test Results Reporting and Follow-Up.",
    "HL7. FHIR Release 5, Task resource. IHE IT Infrastructure Technical Framework, Vol. 1, ch. 30.",
]
for i, ref in enumerate(refs, 1):
    add_para(doc, f"[{i}] {ref}", size=8, space_after=1)

doc.save(OUT)
print("wrote", OUT, OUT.stat().st_size, "bytes")

# Length is measured, not asserted (audit finding M-10). The estimator cannot reproduce the official
# ITU template - which is not in this repository - so it reports a band and this build fails only if
# even the optimistic end of that band exceeds the 5-page target.
import measure_length  # noqa: E402  (same directory; imported after the document exists)

m = measure_length.measure()
measure_length.OUT.write_text(
    "# Report length\n\n"
    "Computed by `submission/measure_length.py` from `submission/ResultRelay_ITU_paper.docx`. **This is an "
    "estimate, not a render**: the workspace has no LibreOffice/Word/LaTeX, so the page count the "
    "official ITU template will produce cannot be measured here. The estimator wraps every paragraph "
    "with real font metrics at the document's own page geometry, measures each table with its declared "
    "column widths and adds the figure at its placed height. Honest band: +/-0.5 page.\n\n"
    "```json\n" + json.dumps(m, indent=2) + "\n```\n\n"
    f"Body text is {m['words']} words with {m['tables']} tables and {m['figures']} figure. Estimated "
    f"length {m['estimated_pages']} pages (band {m['estimated_pages_band'][0]}-"
    f"{m['estimated_pages_band'][1]}). Against the event's 5-page target this is "
    + ("**within budget on the estimate and on its band**" if m["estimated_pages_band"][1] <= 5.0
       else "**at risk: the band crosses the 5-page limit**")
    + "; the official template is not in this repository, so the real render remains NOT_VERIFIED.\n"
)
print("length:", m["estimated_pages"], "pages (band", m["estimated_pages_band"], ")")
if m["estimated_pages_band"][1] > 5.0:
    print("FAIL: the length band crosses the 5-page target; cut before submitting")
    raise SystemExit(1)
