"""The exported manifest is the project's public claim surface, so it is tested like one.

If a reviewer downloads `manifest.json` and it disagrees with the index, the gap register or the
last evaluation, every other number in the project becomes suspect.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def manifest() -> dict:
    spec = importlib.util.spec_from_file_location("export_manifest", REPO / "scripts" / "export_manifest.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.build()


def test_manifest_counts_match_the_index(manifest, repo_root):
    index = json.loads((repo_root / "kb" / "index" / "chunks.json").read_text(encoding="utf-8"))
    kb = manifest["knowledge_base"]
    assert kb["chunk_count"] == index["chunk_count"]
    assert len(manifest["excerpts"]) == index["chunk_count"]
    assert kb["verification"]["verified"] == index["verification"]["verified"]
    assert kb["verification"]["rejected"] == index["verification"]["mismatch"]


def test_no_unverified_excerpt_is_published_as_verified(manifest):
    for excerpt in manifest["excerpts"]:
        assert excerpt["excerpt_status"] == "VERIFIED_AGAINST_SOURCE", excerpt["chunk_id"]


def test_manifest_carries_the_synthetic_disclaimer(manifest):
    assert manifest["synthetic_data_only"] is True
    assert "not a clinical service" in manifest["disclaimer"].lower()


def test_gap_register_is_exported_with_its_classifications(manifest):
    gaps = manifest["gaps"]
    assert len(gaps) >= 10
    allowed = {
        "SOURCE_AMBIGUITY", "INSUFFICIENT_EVIDENCE", "CANDIDATE_POLICY_GAP",
        "SOURCE_CONFLICT", "IMPLEMENTATION_GAP", "INTEROPERABILITY_GAP",
    }
    for gap in gaps:
        assert gap["classification"] in allowed, gap["gap_id"]
        assert gap["question"].strip(), gap["gap_id"]


def test_mapping_statuses_are_limited_to_real_states(manifest):
    """No 'compliant' or 'certified' status may creep into a mapping row.

    The Y.3172 mapping is descriptive (concept -> component) and carries no status column at all;
    what it must carry, like every other mapping row, is a stated limitation.
    """
    allowed = {"IMPLEMENTED", "PARTIAL", "NOT_IMPLEMENTED"}
    for name, rows in manifest["mappings"].items():
        assert rows, name
        for row in rows:
            if "status" in row:
                assert row["status"].strip().upper() in allowed, f"{name}: {row['status']}"
            assert row.get("limitations", "").strip(), f"{name}/{row.get('mapping_id')}: no limitation stated"


def test_mapping_citations_point_at_files_that_exist(manifest, repo_root):
    """The readiness mapping cites code and test paths; a citation to nothing is a false claim."""
    for name, rows in manifest["mappings"].items():
        for row in rows:
            for field, value in row.items():
                if not value or not isinstance(value, str):
                    continue
                for token in value.replace(";", " ").split():
                    token = token.strip("(),`")
                    if "/" in token and (
                        token.startswith(("app/", "tests/", "web/", "scripts/", "kb/", "docs/", "scenarios/"))
                    ):
                        path = token.split("::")[0]
                        # Glob patterns are allowed when a row cites a family of files.
                        matches = list(repo_root.glob(path)) if any(c in path for c in "*?[") else [repo_root / path]
                        assert any(m.exists() for m in matches), f"{name}: cites missing path {path}"


def test_evaluation_section_matches_the_latest_results(manifest, repo_root):
    latest = repo_root / "evaluation" / "results" / "latest.json"
    if not latest.exists():
        pytest.skip("no evaluation results; run `make eval`")
    results = json.loads(latest.read_text(encoding="utf-8"))
    assert manifest["evaluation"]["run_count"] == results["run_count"]
    assert manifest["evaluation"]["summary"] == results["summary"]


def test_manifest_is_serialisable_and_written(manifest, repo_root):
    text = json.dumps(manifest, indent=2)
    assert len(text) > 1000
    written = repo_root / "web" / "public" / "data" / "manifest.json"
    if written.exists():
        on_disk = json.loads(written.read_text(encoding="utf-8"))
        assert set(on_disk) == set(manifest)
