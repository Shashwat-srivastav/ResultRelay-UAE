#!/usr/bin/env python3
"""Export a single static JSON manifest of the project's evidence claims.

The manifest exists so a reviewer can check the numbers without running the system: what was
retrieved, which quotations verified, which gaps are open, what each mapping claims, and what the
last evaluation found. It is written to ``frontend/public/data/manifest.json`` so the built UI can
serve it as a downloadable artefact.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "knowledge_base"
OUT = ROOT / "frontend" / "public" / "data" / "manifest.json"


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def build() -> dict:
    index = json.loads((KB / "index" / "chunks.json").read_text(encoding="utf-8"))
    latest = ROOT / "evaluation" / "results" / "latest.json"
    evaluation = json.loads(latest.read_text(encoding="utf-8")) if latest.exists() else None

    return {
        "manifest_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_data_only": True,
        "disclaimer": (
            "Demonstration prototype with synthetic data. Not a clinical service and not evidence of "
            "clinical safety, effectiveness or regulatory compliance."
        ),
        "knowledge_base": {
            "built_at": index["built_at"],
            "chunk_count": index["chunk_count"],
            "index_sha256": index.get("index_sha256", ""),
            "verification": {
                "verified": index["verification"]["verified"],
                "unverified": index["verification"]["unverified"],
                "rejected": index["verification"]["mismatch"],
                "method": (
                    "Each quotation is normalised and required to appear as a contiguous substring of "
                    "the declared source page. Wrong page or wrong wording is rejected and excluded "
                    "from the index."
                ),
            },
            "sources": _csv(KB / "source_register.csv"),
        },
        "excerpts": [
            {
                "chunk_id": c["chunk_id"],
                "source_id": c["source_id"],
                "section": c["section_id"],
                "printed_pages": [c["page_start"], c["page_end"]],
                "pdf_pages": [c.get("pdf_page_start"), c.get("pdf_page_end")],
                "claim_classification": c["claim_classification"],
                "jurisdiction": c["jurisdiction"],
                "excerpt_status": c.get("excerpt_status"),
                "text_sha256": c.get("text_sha256"),
            }
            for c in index["chunks"]
        ],
        "gaps": _csv(KB / "gap_register.csv"),
        "mappings": {
            "itu_y3172": _csv(KB / "mappings" / "itu_y3172_mapping.csv"),
            "ai_readiness": _csv(KB / "mappings" / "ai_readiness_mapping.csv"),
        },
        "evaluation": None if evaluation is None else {
            "run_started": evaluation["run_started"],
            "run_finished": evaluation["run_finished"],
            "scenario_count": evaluation["scenario_count"],
            "run_count": evaluation["run_count"],
            "summary": evaluation["summary"],
            "caveats": evaluation["caveats"],
        },
        "tests": {
            "command": "make test",
            "note": "Backend test suite; see backend/tests/.",
        },
    }


def main() -> int:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"manifest -> {OUT}")
    print(f"  sources {len(payload['knowledge_base']['sources'])}, "
          f"excerpts {len(payload['excerpts'])}, gaps {len(payload['gaps'])}, "
          f"mapping rows {sum(len(v) for v in payload['mappings'].values())}")
    if payload["evaluation"] is None:
        print("  no evaluation results present; run `make eval` first")
    return 0


if __name__ == "__main__":
    sys.exit(main())
