#!/usr/bin/env python3
"""Regenerate every chart in the README and the submission report from the repository's own data.

    python docs/figures/make_figures.py

Every number drawn comes from a file read below; nothing is typed in by hand, so a figure cannot drift
from the evaluation, the recorded council run or the knowledge base. Sources:

    evaluation/results/latest.json        fully-safe counts and final states (12 scenarios x 12 configurations)
    evaluation/demo_run.json              the recorded agent-council run (18 decision points)
    kb/index/chunks.json                  the 96 traceable excerpts
    kb/source_register.csv                the 24 source documents
    kb/gap_register.csv                   the 18 policy / standards gaps
    kb/framework/ai_readiness_mapping.csv ITU AI Readiness 2.0, 13 dimensions
    evaluation/retrieval_check.md         BM25 vs hybrid retrieval on seven questions
    app/state_machine/states.py           the case states (counted, for the pipeline figure)

README figures are written as docs/figures/<name>.png; compact report variants as docs/figures/report_<name>.png.
"""
from __future__ import annotations

import collections
import csv
import json
import logging
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# --- palette (dataviz reference instance, light mode, white surface) ------------------------------
SURFACE = "#ffffff"
INK = "#0b0b0b"          # primary text
INK2 = "#52514e"         # secondary text
MUTED = "#898781"        # axis / tick labels
GRID = "#e1e0d9"         # hairline grid
BASE = "#c3c2b7"         # baseline / axis
ACCENT = "#2a78d6"       # categorical slot 1 (emphasis)
ACCENT_TINT = "#cde2fb"  # blue ramp step 100
SLOT2 = "#eb6834"        # categorical slot 2 (orange): escalation / intervention
SLOT2_TINT = "#fbe1d6"
CONTEXT = "#bdbbb3"      # de-emphasis grey for context bars
CONTEXT_TINT = "#f2f1ee"
GOOD, WARNING, CRITICAL = "#0ca30c", "#fab219", "#d03b3b"   # status colours: always with a glyph + label
GOOD_TINT, WARNING_TINT, CRITICAL_TINT = "#e3f4e3", "#fef3d9", "#fbe2e2"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 10,
    "text.color": INK,
    "axes.edgecolor": BASE,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": INK,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})

DPI = 200          # README figures
DPI_REPORT = 300   # report figures (printed at their real size)


# --- data -----------------------------------------------------------------------------------------

def load_eval() -> dict:
    return json.loads((ROOT / "evaluation/results/latest.json").read_text(encoding="utf-8"))


def load_council() -> dict:
    return json.loads((ROOT / "evaluation/demo_run.json").read_text(encoding="utf-8"))


def load_chunks() -> list[dict]:
    return json.loads((ROOT / "kb/index/chunks.json").read_text(encoding="utf-8"))["chunks"]


def load_csv(rel: str) -> list[dict]:
    with open(ROOT / rel, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def short_scenario(sid: str) -> str:
    return sid.split("-")[0]          # "S9-reply-from-someone-else" -> "S9"


def scenario_order(sid: str) -> tuple:
    m = re.match(r"S(\d+)([a-z]*)", short_scenario(sid))
    return (int(m.group(1)), m.group(2)) if m else (999, sid)


# Display order for ties: the comparison the README makes first, then ablations and baselines.
PRIORITY = {"resultrelay_council": 0, "resultrelay": 1, "static_rules": 2, "retrieval_only": 8, "policy_blind": 9}
SHORT_LABEL = {
    "resultrelay_council": "Rules + agent council",
    "resultrelay": "Rules only (ResultRelay)",
    "static_rules": "Hand-written rules",
    "ablate_no_audit_agent": "Control: no audit assessor",
    "ablate_full_context": "Control: full context",
    "ablate_no_applicability_filter": "No jurisdiction filter",
    "ablate_no_kb": "No knowledge base",
    "ablate_ack_any": "Ack. of any revision",
    "ablate_optimistic_transport": "Optimistic transport",
    "ablate_no_invariants": "No invariant gate",
    "retrieval_only": "Citation-only RAG",
    "policy_blind": "Policy-blind",
}
STATE_SHORT = {
    "COMMUNICATION_DOCUMENTED": "DOC",
    "ESCALATION_REQUIRED": "ESC",
    "ESCALATION_IN_REVIEW": "REV",
    "CORRECTED_RESULT_ACKNOWLEDGED": "CORR",
    "DELIVERY_CONFIRMED": "DLV",
    "CLINICAL_ACKNOWLEDGMENT_CONFIRMED": "ACK",
}


def eval_rows(ev: dict) -> list[dict]:
    """One row per configuration: fully-safe count and the scenarios it is not safe on."""
    by_conf = ev["summary"]["by_configuration"]
    by_scen = ev["summary"]["by_scenario"]
    n = ev["scenario_count"]
    rows = []
    for key, s in by_conf.items():
        # Fully safe = all assertions passed AND the workflow completed in an allowed state; re-derive it
        # from the per-run records and refuse to draw if the summary disagrees.
        runs = [r for r in ev["runs"] if r["configuration"] == key]
        derived = sum(1 for r in runs if r["all_assertions_passed"] and r["workflow_completed"])
        assert derived == s["scenarios_fully_safe"], (key, derived, s["scenarios_fully_safe"])
        misses = [short_scenario(sc) for sc in sorted(by_scen, key=scenario_order) if not by_scen[sc][key]["safe"]]
        rows.append({"key": key, "safe": s["scenarios_fully_safe"], "n": n, "misses": misses,
                     "provenance": s["mean_provenance_completeness"]})
    rows.sort(key=lambda r: (-r["safe"], PRIORITY.get(r["key"], 5), r["key"]))
    return rows


def council_counts(run: dict) -> dict:
    c = collections.Counter()
    for sc in run["runs"]:
        for d in sc["deliberations"]:
            s = d["summary"]
            c["decision_points"] += 1
            c["flagged"] += s["flagged"]
            c["corrected"] += s["corrected"]
            c["upheld"] += s["upheld"]
            c["disputed"] += len(s["disputed"])
            obj = d["messages"]["reviewer"]["answers"].get("objection", {}).get("choice")
            if obj not in (None, "NONE"):
                c["objections"] += 1
                if d["reviews"]["reviewer"]["outcome"] == "OBJECTION_REJECTED":
                    c["objections_rejected"] += 1
                else:
                    c["objections_acted"] += 1
            c["escalate" if d["decision"] == "ESCALATE" else "proceed"] += 1
            if d["decision"] == "ESCALATE" and "reviewer objection" in str(d.get("escalation") or ""):
                c["escalate_on_objection"] += 1
    t = run["totals"]
    for k_ours, k_file in (("decision_points", "decision_points"), ("flagged", "flagged"), ("corrected", "corrected"),
                           ("upheld", "upheld"), ("objections", "objections"),
                           ("objections_rejected", "objections_rejected"), ("escalate", "escalations")):
        assert c[k_ours] == t[k_file], (k_ours, c[k_ours], t[k_file])
    return c


# --- marks ----------------------------------------------------------------------------------------

def _px(ax):
    """Pixels per data unit along x and y (axes limits and figure size must already be final)."""
    (x0, y0), (x1, y1) = ax.transData.transform([(0, 0), (1, 1)])
    return abs(x1 - x0), abs(y1 - y0)


def hbar(ax, y, left, width, height, color, radius_pt=3.0, square_left=True):
    """A horizontal bar with a rounded data-end and a square baseline end (dataviz mark spec)."""
    if width <= 0:
        return
    pxx, pxy = _px(ax)
    r_px = radius_pt / 72 * ax.figure.dpi
    r_x = min(r_px / pxx, width / 2)
    aspect = pxx / pxy
    ax.add_patch(FancyBboxPatch((left, y - height / 2), width, height,
                                boxstyle=f"round,pad=0,rounding_size={r_x}", mutation_aspect=aspect,
                                facecolor=color, edgecolor="none", zorder=3))
    if square_left:
        ax.add_patch(Rectangle((left, y - height / 2), min(width / 2, r_x * 1.6), height,
                               facecolor=color, edgecolor="none", zorder=3))


def block(ax, x, y, w, h, color, radius_pt=3.0):
    """A fully rounded block (segment of a tall segmented bar, heat-map cell)."""
    pxx, pxy = _px(ax)
    r_x = min(radius_pt / 72 * ax.figure.dpi / pxx, w / 2)
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r_x}",
                                mutation_aspect=pxx / pxy, facecolor=color, edgecolor="none", zorder=3))


def gap_units(ax, pt=2.0):
    """A 2px-at-1x surface gap, in x data units."""
    return pt / 72 * ax.figure.dpi / _px(ax)[0]


def title(fig, text, sub=None, size=12, x=0.0, y=1.0):
    fig.text(x, y, text, ha="left", va="bottom", fontsize=size, weight="bold", color=INK,
             transform=fig.transFigure)
    if sub:
        fig.text(x, y - 0.012, sub, ha="left", va="top", fontsize=size * 0.78, color=INK2,
                 transform=fig.transFigure)


def save(fig, name, dpi):
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=dpi, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print(f"  {path.relative_to(ROOT)}")


def clean_axes(ax, x_grid=True):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0, colors=MUTED)
    if x_grid:
        ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)


# --- 1. evaluation: fully safe by configuration ---------------------------------------------------

def fig_eval(ev, compact=False):
    rows = eval_rows(ev)
    n = rows[0]["n"]
    if compact:
        fig = plt.figure(figsize=(3.2, 2.1))
        ax = fig.add_axes([0.40, 0.10, 0.50, 0.74])
        fs, lab = 6.3, [SHORT_LABEL.get(r["key"], r["key"]) for r in rows]
    else:
        fig = plt.figure(figsize=(8.6, 4.6))
        ax = fig.add_axes([0.33, 0.08, 0.55, 0.78])
        fs, lab = 9.5, [r["key"] for r in rows]
    ys = list(range(len(rows)))[::-1]
    ax.set_xlim(0, n)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    clean_axes(ax)
    ax.set_xticks(range(0, n + 1, 2))
    ax.tick_params(axis="x", labelsize=fs - 0.5)
    ax.set_yticks(ys)
    ax.set_yticklabels(lab, fontsize=fs, family=("Segoe UI" if compact else "Consolas"))
    for t, r in zip(ax.get_yticklabels(), rows):
        if r["key"] == "resultrelay_council":
            t.set_fontweight("bold")
    for y, r in zip(ys, rows):
        hero = r["key"] == "resultrelay_council"
        hbar(ax, y, 0, r["safe"], 0.62, ACCENT if hero else CONTEXT, radius_pt=2.2 if compact else 3)
        note = f"{r['safe']}/{n}"
        if 0 < len(r["misses"]) <= 3:
            note += "  ·  misses " + ", ".join(r["misses"])
        ax.text(r["safe"] + n * 0.012, y, note, va="center", ha="left", fontsize=fs - 0.4,
                color=INK if hero else INK2, weight="bold" if hero else "normal", zorder=4, clip_on=False)
    ax.set_xlabel(f"scenarios fully safe (of {n})", fontsize=fs - 0.5, color=MUTED)
    if compact:
        title(fig, "Fully safe scenarios by configuration", f"{ev['run_count']} runs; fully safe = all assertions + allowed end state",
              size=7.6, x=0.02, y=0.93)
        save(fig, "report_eval_fully_safe", DPI_REPORT)
    else:
        top = [r for r in rows if r["safe"] == rows[0]["safe"]]
        head = (f"Only {top[0]['key']} is fully safe on all {n} scenarios" if len(top) == 1 and top[0]["safe"] == n
                else "Fully safe scenarios by configuration")
        title(fig, head,
              f"{ev['scenario_count']} scenarios × {len(rows)} configurations = {ev['run_count']} runs · "
              "fully safe = every assertion passed and the case ended in an allowed state",
              size=12.5, x=0.02, y=0.935)
        save(fig, "eval_fully_safe", DPI)


# --- 2. evaluation: scenario x configuration heat map ---------------------------------------------

def fig_heatmap(ev, compact=False):
    rows = eval_rows(ev)
    by_scen = ev["summary"]["by_scenario"]
    scen = sorted(by_scen.keys(), key=scenario_order)
    nr, nc = len(rows), len(scen)
    if compact:
        fig = plt.figure(figsize=(6.5, 2.45))
        ax = fig.add_axes([0.20, 0.10, 0.79, 0.70])
        fs = 5.8
    else:
        fig = plt.figure(figsize=(9.6, 5.4))
        ax = fig.add_axes([0.25, 0.12, 0.74, 0.70])
        fs = 8.4
    ax.set_xlim(0, nc)
    ax.set_ylim(0, nr)
    ax.invert_yaxis()
    ax.axis("off")
    g = 0.04
    for i, r in enumerate(rows):
        lbl = SHORT_LABEL.get(r["key"], r["key"]) if compact else r["key"]
        ax.text(-0.12, i + 0.5, lbl, ha="right", va="center", fontsize=fs + 0.4,
                family="Segoe UI" if compact else "Consolas",
                weight="bold" if r["key"] == "resultrelay_council" else "normal")
        for j, sc in enumerate(scen):
            cell = by_scen[sc][r["key"]]
            safe = cell["safe"]
            block(ax, j + g, i + g, 1 - 2 * g, 1 - 2 * g, GOOD_TINT if safe else CRITICAL_TINT, radius_pt=1.6)
            code = STATE_SHORT.get(cell["final_state"], cell["final_state"][:4])
            ax.text(j + 0.30, i + 0.5, "✓" if safe else "✗", ha="center", va="center", fontsize=fs + 1,
                    color=GOOD if safe else CRITICAL, weight="bold", zorder=5, family="DejaVu Sans")
            ax.text(j + 0.40, i + 0.5, code, ha="left", va="center", fontsize=fs,
                    color=INK if not safe else INK2, weight="bold" if not safe else "normal", zorder=5)
    for j, sc in enumerate(scen):
        ax.text(j + 0.5, -0.25, short_scenario(sc), ha="center", va="bottom", fontsize=fs + 0.6, weight="bold")
    used = sorted({c[k]["final_state"] for c in by_scen.values() for k in c}, key=lambda s: STATE_SHORT.get(s, s))
    legend = "   ".join(f"{STATE_SHORT.get(s, s)} = {s}" for s in used)
    ax.text(0, nr + 0.25, "✓ fully safe    ✗ not fully safe (end state not allowed, or an assertion failed)\n"
            "final state:  " + legend, ha="left", va="top", fontsize=fs - 0.6, color=INK2, linespacing=1.5)
    if compact:
        title(fig, "Final state of every run (✓ fully safe, ✗ not)", None, size=7.6, x=0.01, y=0.90)
        save(fig, "report_eval_heatmap", DPI_REPORT)
    else:
        title(fig, f"Where each configuration fails: final state of all {ev['run_count']} runs",
              "rows = configurations (ordered as above) · columns = scenarios · cell = final state; red = not fully safe",
              size=12.5, x=0.02, y=0.90)
        save(fig, "eval_heatmap", DPI)


# --- 3. council outcomes --------------------------------------------------------------------------

def fig_council(run, compact=False):
    c = council_counts(run)
    rows = [
        (f"Analyst claims flagged by assurance: {c['flagged']}",
         [(c["corrected"], "corrected" if compact else "corrected after feedback", SLOT2),
          (c["upheld"], "upheld", ACCENT)],
         f"{c['disputed']} disputed"),
        (f"Reviewer objections raised: {c['objections']}",
         [(c["objections_rejected"], "rejected by code", ACCENT), (c["objections_acted"], "acted on", SLOT2)],
         f"each rejected one contradicted the case record; {c['escalate_on_objection']} acted on → escalation"),
        (f"Orchestrator decisions: {c['decision_points']} decision points",
         [(c["proceed"], "proceed" if compact else "proceed (gate decides)", ACCENT), (c["escalate"], "escalate", SLOT2)],
         "agents can only add an escalation to a person"),
    ]
    xmax = max(sum(v for v, _, _ in segs) for _, segs, _ in rows)
    if compact:
        fig = plt.figure(figsize=(3.2, 2.1))
        ax = fig.add_axes([0.03, 0.02, 0.94, 0.80])
        fs, h, step = 6.2, 0.42, 1.25
    else:
        fig = plt.figure(figsize=(8.6, 3.2))
        ax = fig.add_axes([0.02, 0.04, 0.96, 0.78])
        fs, h, step = 9.5, 0.46, 1.3
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.7, step * (len(rows) - 1) + 0.62)
    ax.axis("off")
    gap = gap_units(ax, 1.4)
    for i, (label, segs, note) in enumerate(rows):
        y = step * (len(rows) - 1 - i)
        ax.text(0, y + h / 2 + 0.12, label, ha="left", va="bottom", fontsize=fs + 0.4, weight="bold")
        x = 0
        for v, name, col in segs:
            if v <= 0:
                continue
            block(ax, x, y - h / 2, v - gap, h, col, radius_pt=2.4 if compact else 3)
            txt = f"{v} {name}"
            # Print the label inside only if it fits; otherwise the row note carries it.
            tw = len(txt) * fs * 0.55 / 72 * fig.dpi / _px(ax)[0]
            if tw < v - gap - 0.3:
                ax.text(x + 0.25, y, txt, ha="left", va="center", fontsize=fs, color="#ffffff", weight="bold", zorder=5)
            else:
                ax.text(x + (v - gap) / 2, y, str(v), ha="center", va="center", fontsize=fs, color="#ffffff",
                        weight="bold", zorder=5)
            x += v
        ax.text(0, y - h / 2 - 0.08, note, ha="left", va="top", fontsize=fs - 0.8, color=INK2)
    if compact:
        title(fig, "Agent council, recorded run", "orange = changed or escalated · blue = stood / proceeded",
              size=7.6, x=0.02, y=0.93)
        save(fig, "report_council_outcomes", DPI_REPORT)
    else:
        title(fig, "What the council's checks did in the recorded run",
              f"{len(run['runs'])} demo scenarios · {c['decision_points']} decision points · orange = the check changed "
              "the answer or escalated · blue = the answer stood / the step proceeded",
              size=12.5, x=0.02, y=0.94)
        save(fig, "council_outcomes", DPI)


# --- 4. council trace: every decision point -------------------------------------------------------

def fig_council_trace(run):
    scen = run["runs"]
    ncol = max(len(s["deliberations"]) for s in scen)
    fig = plt.figure(figsize=(10.4, 5.6))
    ax = fig.add_axes([0.13, 0.04, 0.86, 0.80])
    ax.set_xlim(0, ncol)
    ax.set_ylim(0, len(scen))
    ax.invert_yaxis()
    ax.axis("off")
    g = 0.035
    outcome_word = {"ACCEPTED": "accepted", "CORRECTED": "corrected", "UPHELD": "upheld", "DISPUTED": "disputed"}
    for i, s in enumerate(scen):
        ax.text(-0.06, i + 0.40, f"{s['scenario']} · {short_scenario(s['source'])}", ha="right", va="center",
                fontsize=10, weight="bold")
        ax.text(-0.06, i + 0.64, s["final"], ha="right", va="center", fontsize=7.2, color=INK2, family="Consolas")
        for j, d in enumerate(s["deliberations"]):
            esc = d["decision"] == "ESCALATE"
            block(ax, j + g, i + g, 1 - 2 * g, 1 - 2 * g, SLOT2_TINT if esc else CONTEXT_TINT, radius_pt=3)
            ax.add_patch(Rectangle((j + g, i + g), 0.035, 1 - 2 * g, facecolor=SLOT2 if esc else CONTEXT,
                                   edgecolor="none", zorder=4))
            obj = d["messages"]["reviewer"]["answers"].get("objection", {})
            kind = obj.get("choice")
            if kind in (None, "NONE"):
                rv = "no objection"
            elif d["reviews"]["reviewer"]["outcome"] == "OBJECTION_REJECTED":
                rv = f"{kind}\nrejected by code"
            else:
                rv = f"{kind}\np {obj.get('confidence', 0):.2f} · not rejected by code"
            an = d["reviews"]["analyst"]["outcome"]
            claim = "analyst " + outcome_word.get(an, an.lower())
            if "institution" in d["reviews"]:
                claim += " · TDRA " + outcome_word.get(d["reviews"]["institution"]["outcome"],
                                                     d["reviews"]["institution"]["outcome"].lower())
            x0 = j + 0.10
            ax.text(x0, i + 0.17, d["action_under_review"], fontsize=7.6, family="Consolas", weight="bold", va="center")
            ax.text(x0, i + 0.42, rv, fontsize=6.9, color=INK2, va="center", linespacing=1.15)
            ax.text(x0, i + 0.68, claim, fontsize=6.9, color=INK2, va="center")
            ax.text(x0, i + 0.86, "▶ ESCALATE" if esc else "PROCEED", fontsize=7.6, va="center",
                    weight="bold", color=INK)
    for j in range(ncol):
        ax.text(j + 0.5, -0.08, f"decision point {j + 1}", ha="center", va="bottom", fontsize=8, color=MUTED)
    c = council_counts(run)
    title(fig, f"Every decision point of the recorded council run ({c['decision_points']})",
          "per step: action under review · the reviewer's objection and what code did with it · analyst outcome · "
          "orchestrator decision (orange = escalated)", size=12.5, x=0.02, y=0.925)
    save(fig, "council_trace", DPI)


# --- 5. knowledge base composition ----------------------------------------------------------------

LAYER = {"AE-DU": "Dubai", "AE-FED": "Federal (UAE)", "AE-AZ": "Abu Dhabi (comparator)", "GLOBAL": "International (comparator)"}
VERIF = {  # README groups the official repository copies with official downloads ("74 ... official downloads")
    "VERIFIED_OFFICIAL": "Official download", "VERIFIED_OFFICIAL_REPOSITORY": "Official download",
    "VERIFIED_TRANSCRIPTION": "Recorded transcription", "VERIFIED_THIRD_PARTY_COPY": "Third-party copy",
    "VERIFIED_MIRROR": "Mirror",
}
CLAIM = {"BINDING_REQUIREMENT": "Binding requirement", "GLOBAL_COMPARATOR": "Global comparator",
         "OFFICIAL_GUIDANCE": "Official guidance"}


def kb_panels():
    sources = load_csv("kb/source_register.csv")
    chunks = load_chunks()
    p1 = collections.Counter(LAYER.get(s["jurisdiction"], s["jurisdiction"]) for s in sources)
    p2 = collections.Counter(VERIF.get(c["verification_status"], c["verification_status"]) for c in chunks)
    p3 = collections.Counter(CLAIM.get(c["claim_classification"], c["claim_classification"]) for c in chunks)
    order1 = [LAYER[k] for k in ("AE-DU", "AE-FED", "AE-AZ", "GLOBAL") if LAYER[k] in p1]
    return [
        (f"{len(sources)} source documents, by layer", [(k, p1[k]) for k in order1]),
        (f"{len(chunks)} quotations, by how they were verified", p2.most_common()),
        (f"{len(chunks)} quotations, by claim class", p3.most_common()),
    ]


def _bar_panel(ax, name, items, fs, compact):
    ys = list(range(len(items)))[::-1]
    xmax = max(v for _, v in items)
    ax.set_xlim(0, xmax * 1.18)
    ax.set_ylim(-0.6, len(items) - 0.4)
    clean_axes(ax, x_grid=False)
    ax.spines["bottom"].set_visible(False)
    ax.set_xticks([])
    ax.set_yticks(ys)
    ax.set_yticklabels([k for k, _ in items], fontsize=fs)
    for y, (_, v) in zip(ys, items):
        hbar(ax, y, 0, v, 0.62, ACCENT, radius_pt=2 if compact else 3)
        ax.text(v + xmax * 0.025, y, str(v), va="center", fontsize=fs, color=INK)
    ax.axvline(0, color=BASE, linewidth=0.8, zorder=4)
    ax.set_title(name, loc="left", fontsize=fs + 0.6, weight="bold", pad=3 if compact else 6)


def fig_kb(compact=False):
    panels = kb_panels()
    if compact:
        fig = plt.figure(figsize=(3.2, 2.15))
        heights = [len(p[1]) for p in panels]
        tot = sum(heights) + 1.6 * len(panels)
        top = 0.86
        for (name, items), h in zip(panels, heights):
            hh = 0.80 * h / tot
            ax = fig.add_axes([0.44, top - hh, 0.48, hh])
            _bar_panel(ax, name, items, 6.0, True)
            top -= hh + 0.80 * 1.6 / tot
        title(fig, "Knowledge base composition", None, size=7.6, x=0.02, y=0.94)
        save(fig, "report_kb_composition", DPI_REPORT)
    else:
        fig = plt.figure(figsize=(11.0, 2.9))
        lefts = [0.13, 0.47, 0.81]
        row_h = 0.17
        top = 0.06 + row_h * max(len(p[1]) for p in panels)
        for (name, items), left in zip(panels, lefts):
            ax = fig.add_axes([left, top - row_h * len(items), 0.15, row_h * len(items)])
            _bar_panel(ax, name, items, 9.2, False)
        title(fig, "Knowledge base: what is in it and how each quotation was checked",
              "only a binding requirement from a source that binds the case jurisdiction can block an action",
              size=12.5, x=0.01, y=1.08)
        save(fig, "kb_composition", DPI)


# --- 6. gap register ------------------------------------------------------------------------------

GAP_LABEL = {"CANDIDATE_POLICY_GAP": "Candidate policy gap", "SOURCE_AMBIGUITY": "Source ambiguity",
             "INSUFFICIENT_EVIDENCE": "Insufficient evidence", "IMPLEMENTATION_GAP": "Implementation gap",
             "INTEROPERABILITY_GAP": "Interoperability gap", "SOURCE_CONFLICT": "Source conflict"}


def fig_gaps(compact=False):
    gaps = load_csv("kb/gap_register.csv")
    with_c = collections.Counter()
    without = collections.Counter()
    for gp in gaps:
        none = gp["global_comparator"].strip().lower().startswith("none")
        (without if none else with_c)[gp["classification"]] += 1
    classes = sorted(set(with_c) | set(without), key=lambda k: (-(with_c[k] + without[k]), k))
    n_with = sum(with_c.values())
    if compact:
        fig = plt.figure(figsize=(3.2, 2.1))
        ax = fig.add_axes([0.40, 0.24, 0.50, 0.58])
        fs = 6.2
    else:
        fig = plt.figure(figsize=(8.6, 3.4))
        ax = fig.add_axes([0.24, 0.20, 0.62, 0.58])
        fs = 9.5
    xmax = max(with_c[k] + without[k] for k in classes)
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.6, len(classes) - 0.4)
    clean_axes(ax)
    ax.set_xticks(range(0, xmax + 1, 2))
    ax.tick_params(axis="x", labelsize=fs - 0.5)
    ys = list(range(len(classes)))[::-1]
    ax.set_yticks(ys)
    ax.set_yticklabels([GAP_LABEL.get(k, k) for k in classes], fontsize=fs)
    gap = gap_units(ax, 1.4)
    for y, k in zip(ys, classes):
        a, b = with_c[k], without[k]
        r = 2 if compact else 3
        if a and b:   # first segment square at both ends, a surface gap, then the rounded data-end
            ax.add_patch(Rectangle((0, y - 0.31), a - gap, 0.62, facecolor=ACCENT, edgecolor="none", zorder=3))
            hbar(ax, y, a, b, 0.62, CONTEXT, radius_pt=r)
        elif a:
            hbar(ax, y, 0, a, 0.62, ACCENT, radius_pt=r)
        elif b:
            hbar(ax, y, 0, b, 0.62, CONTEXT, radius_pt=r)
        ax.text(a + b + xmax * 0.02, y, str(a + b), va="center", fontsize=fs, color=INK)
    lx = 0
    for col, name in ((ACCENT, f"comparator retrieved ({n_with})"),
                      (CONTEXT, f"none retrieved ({len(gaps) - n_with})")):
        ax.add_patch(Rectangle((lx, -1.75), xmax * 0.03, 0.32, facecolor=col, edgecolor="none", clip_on=False))
        ax.text(lx + xmax * 0.045, -1.59, name, va="center", fontsize=fs - 0.4, color=INK2, clip_on=False)
        lx += xmax * (0.62 if compact else 0.42)
    if compact:
        title(fig, f"{len(gaps)} policy and standards gaps, by type", f"{n_with} with a global comparator",
              size=7.6, x=0.02, y=0.93)
        save(fig, "report_gap_register", DPI_REPORT)
    else:
        title(fig, f"{len(gaps)} policy and standards gaps, by type",
              f"{n_with} of {len(gaps)} name a comparator from another jurisdiction (column global_comparator)",
              size=12.5, x=0.02, y=0.93)
        save(fig, "gap_register", DPI)


# --- 7. retrieval check ---------------------------------------------------------------------------

def fig_retrieval():
    rows = []
    for line in (ROOT / "evaluation/retrieval_check.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[2] in ("hit", "miss"):
            rows.append((cells[0], cells[1].strip("`"), cells[2] == "hit", cells[3] == "hit"))
    n = len(rows)
    bm, hy = sum(r[2] for r in rows), sum(r[3] for r in rows)
    fig = plt.figure(figsize=(8.6, 3.5))
    ax = fig.add_axes([0.02, 0.04, 0.96, 0.76])
    ax.set_xlim(0, 10)
    ax.set_ylim(n - 0.4, -1.1)
    ax.axis("off")
    cx = (7.6, 9.0)
    ax.text(cx[0], -0.85, f"BM25\n{bm}/{n}", ha="center", va="center", fontsize=9.5, weight="bold", linespacing=1.2)
    ax.text(cx[1], -0.85, f"Hybrid\n{hy}/{n}", ha="center", va="center", fontsize=9.5, weight="bold", linespacing=1.2)
    for i, (q, clause, b, h) in enumerate(rows):
        ax.axhline(i + 0.5, color=GRID, linewidth=0.8, xmin=0, xmax=1)
        ax.text(0.05, i, f"“{q}”", va="center", fontsize=9.5)
        ax.text(6.1, i, clause, va="center", ha="left", fontsize=8.5, color=INK2, family="Consolas")
        for x, hit in zip(cx, (b, h)):
            if hit:
                ax.plot(x, i, "o", ms=10, color=ACCENT, mec=SURFACE, mew=2, zorder=4)
            else:
                ax.plot(x, i, "o", ms=9, mfc=SURFACE, mec=CONTEXT, mew=1.6, zorder=4)
    ax.text(6.1, -0.85, "expected clause", ha="left", va="center", fontsize=8.5, color=MUTED)
    title(fig, f"Retrieval check: expected clause in the top 5 — hybrid {hy}/{n}, BM25 {bm}/{n}",
          "● hit   ○ miss · plain-language questions written by the authors: a smoke test, not a benchmark",
          size=12.5, x=0.02, y=0.93)
    save(fig, "retrieval_check", DPI)


# --- 8. ITU AI Readiness 2.0 ----------------------------------------------------------------------

def fig_readiness():
    rows = load_csv("kb/framework/ai_readiness_mapping.csv")
    status_style = {"IMPLEMENTED": (GOOD, GOOD_TINT, "✓", "Implemented"),
                    "PARTIAL": (WARNING, WARNING_TINT, "◐", "Partial"),
                    "NOT_IMPLEMENTED": (CRITICAL, CRITICAL_TINT, "✗", "Not implemented")}
    cnt = collections.Counter(r["status"] for r in rows)
    n = len(rows)
    fig = plt.figure(figsize=(8.6, 0.30 * n + 1.0))
    ax = fig.add_axes([0.02, 0.03, 0.96, 0.80])
    ax.set_xlim(0, 10)
    ax.set_ylim(n - 0.5, -1.1)
    ax.axis("off")
    for i, r in enumerate(rows):
        col, tint, glyph, word = status_style.get(r["status"], (MUTED, CONTEXT_TINT, "?", r["status"]))
        ax.axhline(i + 0.5, color=GRID, linewidth=0.7)
        ax.text(0.05, i, r["framework_dimension"], va="center", fontsize=9.5)
        ax.text(4.6, i, r["framework_index"].replace("Basic-framework pillar: ", ""), va="center",
                fontsize=8.5, color=INK2)
        block(ax, 7.0, i - 0.36, 1.75, 0.72, tint, radius_pt=3)
        ax.text(7.18, i, glyph, va="center", fontsize=10, color=col, weight="bold", family="DejaVu Sans", zorder=5)
        ax.text(7.55, i, word, va="center", fontsize=9, color=INK, zorder=5)
    ax.text(4.6, -0.8, "Readiness pillar", fontsize=8.5, color=MUTED, va="center")
    ax.text(7.0, -0.8, "Status in ResultRelay", fontsize=8.5, color=MUTED, va="center")
    parts = " · ".join(f"{cnt[k]} {status_style[k][3].lower()}" for k in status_style if cnt[k])
    title(fig, f"ITU AI Readiness 2.0: {n} dimensions — {parts}",
          "statuses from kb/framework/ai_readiness_mapping.csv; each row there names the code, the test and the limitation",
          size=12.5, x=0.02, y=0.95)
    save(fig, "ai_readiness", DPI)


# --- 9. compact pipeline (report) -----------------------------------------------------------------

def fig_pipeline_report():
    from app.state_machine.states import CaseState
    chunks = load_chunks()
    n_src = len(load_csv("kb/source_register.csv"))
    n_states = len(list(CaseState))
    fig = plt.figure(figsize=(6.5, 1.3))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 22)
    ax.axis("off")
    boxes = [
        ("Verified corpus", f"{n_src} sources\n{len(chunks)} quotations", CONTEXT_TINT, INK2),
        ("Agent council (LLM)", "policy analyst (DHA)\nTDRA lens · reviewer", ACCENT_TINT, ACCENT),
        ("Assurance (code)", "fact & policy checks;\norchestrator: go / escalate", CONTEXT_TINT, INK2),
        ("Deterministic gate", f"{n_states} states, invariants\ndecides every transition", CONTEXT_TINT, INK2),
        ("Transport", "attempt ≠ delivery\n≠ acknowledgment", CONTEXT_TINT, INK2),
        ("Audit", "hash chain\nsigned checkpoints", CONTEXT_TINT, INK2),
    ]
    w, gap, y, h = 14.6, 2.3, 7.5, 13.0
    for k, (head, sub, fc, ec) in enumerate(boxes):
        x = 0.5 + k * (w + gap)
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", mutation_aspect=1.6,
                                    facecolor=fc, edgecolor=ec, linewidth=0.8))
        ax.text(x + w / 2, y + h * 0.72, head, ha="center", va="center", fontsize=6.8, weight="bold")
        ax.text(x + w / 2, y + h * 0.33, sub, ha="center", va="center", fontsize=5.7, color=INK2, linespacing=1.3)
        if k:
            ax.add_patch(FancyArrowPatch((x - gap + 0.15, y + h / 2), (x - 0.15, y + h / 2), arrowstyle="-|>",
                                         mutation_scale=7, linewidth=0.8, color=INK2))
    ax.text(0.5, 3.4, "Blue = language models (advise only) · grey = deterministic code or data. Agents can only add an "
            "escalation to a person;\nonly clauses that bind the case jurisdiction can block or authorise an action; "
            "a real case is refused on an offshore model endpoint.", fontsize=5.7, color=INK2, va="center",
            linespacing=1.35)
    save(fig, "report_pipeline", DPI_REPORT)


def main():
    ev, run = load_eval(), load_council()
    print("README figures:")
    fig_eval(ev)
    fig_heatmap(ev)
    fig_council(run)
    fig_council_trace(run)
    fig_kb()
    fig_gaps()
    fig_retrieval()
    fig_readiness()
    print("report figures:")
    fig_pipeline_report()
    fig_eval(ev, compact=True)
    fig_council(run, compact=True)
    fig_kb(compact=True)
    fig_gaps(compact=True)
    fig_heatmap(ev, compact=True)


if __name__ == "__main__":
    main()
