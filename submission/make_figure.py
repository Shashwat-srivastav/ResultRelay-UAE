#!/usr/bin/env python3
"""Figure 1: where the constraints sit in the pipeline."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Counts come from the built manifest, never from a literal, so the figure cannot drift from the corpus.
ROOT = Path(__file__).resolve().parent.parent
_manifest = json.loads((ROOT / "web/public/data/manifest.json").read_text())
_SOURCES = len(_manifest["knowledge_base"]["sources"])
_EXCERPTS = len(_manifest["excerpts"])

fig, ax = plt.subplots(figsize=(9.4, 3.9), dpi=300)
ax.set_xlim(0, 100); ax.set_ylim(0, 40); ax.axis("off")

def box(x, y, w, h, title, sub, fc="#ffffff", ec="#222222", ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.0",
                                linewidth=1.0, edgecolor=ec, facecolor=fc, linestyle=ls))
    ax.text(x + w/2, y + h*0.66, title, ha="center", va="center", fontsize=8.4, weight="bold")
    ax.text(x + w/2, y + h*0.30, sub, ha="center", va="center", fontsize=6.6,
            color="#333333", linespacing=1.35)

def arrow(p1, p2, ls="-", color="#222222"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=10,
                                 linewidth=1.0, color=color, linestyle=ls,
                                 shrinkA=0, shrinkB=0))

Y, H = 25, 12
box(1,  Y, 17, H, "Corpus", f"{_SOURCES} sources\n{_EXCERPTS} verified excerpts")
box(23, Y, 17, H, "Agents", "structured\nassessments only")
box(45, Y, 17, H, "Deterministic gate", "state machine\n+ invariants")
box(67, Y, 17, H, "Transport", "attempt ≠ delivery\n≠ acknowledgment")
box(89, Y, 10, H, "Audit", "hash-\nchained")

arrow((18.4, Y+H/2), (22.6, Y+H/2))
arrow((40.4, Y+H/2), (44.6, Y+H/2))
arrow((62.4, Y+H/2), (66.6, Y+H/2))
arrow((84.4, Y+H/2), (88.6, Y+H/2))

box(23, 6, 17, 11, "Jurisdiction layer", "AE-DU → {AE-DU, AE-FED}\nwidens up, never down",
    fc="#eef4fb", ec="#1f4e79")
box(45, 6, 17, 11, "Adviser", "may propose,\nnever decide", fc="#fff6e5", ec="#a06000", ls="--")

arrow((31.5, 17.4), (31.5, 24.6))
arrow((53.5, 17.4), (53.5, 24.6), ls="--", color="#a06000")

ax.text(64.5, 9.0,
        "refused at the boundary:\noffshore endpoint (Art. 13)\nunresolvable citation\nforeign clause as authority",
        ha="left", va="center", fontsize=6.4, style="italic", color="#8a4b00", linespacing=1.4)

plt.tight_layout(pad=0.2)
out = ROOT / "submission" / "figure1_pipeline.png"
fig.savefig(out, bbox_inches="tight", facecolor="white")
print(f"figure -> {out} ({_SOURCES} sources, {_EXCERPTS} excerpts)")
