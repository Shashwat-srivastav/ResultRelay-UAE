"""The knowledge base earns its citations or it does not get cited.

The first test is the important one: every excerpt in the corpus is checked against the official
source text. When the source cache is absent the test skips with an explicit reason rather than
passing quietly on an unchecked corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.kb import ingest, retriever

REGISTER_REQUIRED = {
    "source_id", "title", "issuing_authority", "jurisdiction", "document_type",
    "version_or_issue", "publication_date", "official_url", "retrieved_at",
    "applicability", "legal_or_guidance_status", "license_or_reuse_notes", "verification_status",
}


@pytest.fixture(scope="module")
def index_payload(repo_root: Path) -> dict:
    path = repo_root / "knowledge_base" / "index" / "chunks.json"
    assert path.exists(), "run `python -m app.kb.ingest` first"
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_excerpt_verifies():
    """Quote-by-quote verification against the fetched source text."""
    if not ingest.SOURCE_CACHE.exists():
        pytest.skip(
            f"source cache absent at {ingest.SOURCE_CACHE}; run `python scripts/fetch_sources.py` "
            "to verify quotes against the official documents"
        )
    chunks, summary = ingest.build_chunks()
    assert summary["mismatch"] == 0, [d for d in summary["details"] if d["status"] not in (
        "VERIFIED_AGAINST_SOURCE",
    )]
    assert summary["unverified"] == 0
    assert summary["verified"] == len(chunks) > 0


def test_chunk_metadata_complete(index_payload):
    for chunk in index_payload["chunks"]:
        for field in ("chunk_id", "source_id", "title", "issuer", "jurisdiction", "section_id",
                      "page_start", "page_end", "claim_classification", "text", "source_url"):
            assert chunk.get(field) not in (None, ""), f"{chunk['chunk_id']} missing {field}"
        assert chunk["claim_classification"] in {
            "BINDING_REQUIREMENT", "OFFICIAL_GUIDANCE", "INSTITUTIONAL_PROCEDURE",
            "GLOBAL_COMPARATOR", "PRODUCT_DESIGN_CONTROL", "RESEARCH_HYPOTHESIS", "UNRESOLVED",
        }
        assert chunk["page_start"] >= 1
        assert len(chunk["text"]) > 20


def test_source_register_fields_are_complete(repo_root: Path):
    rows = ingest.load_register()
    assert rows
    for sid, row in rows.items():
        assert REGISTER_REQUIRED.issubset(row.keys()), sid
        assert row["jurisdiction"] in {"AE-DU", "AE-AZ", "AE-FED", "GLOBAL"}, sid


def test_only_the_local_and_federal_layers_can_be_binding_for_a_dubai_case(index_payload):
    """Binding material is Dubai *or* federal; never another emirate, never a global body.

    The federal layer is the one that governs health data (Federal Law 2/2019, Article 2 applies
    in every emirate including free zones), so excluding it would have been the bug.
    """
    binding = {
        c["jurisdiction"] for c in index_payload["chunks"]
        if c["claim_classification"] == "BINDING_REQUIREMENT"
    }
    assert binding == {"AE-DU", "AE-FED"}
    assert "AE-AZ" not in binding and "GLOBAL" not in binding


def test_federal_law_is_applicable_to_a_dubai_case_but_dubai_policy_is_not_federal():
    dubai = retriever.applicable_jurisdictions("AE-DU")
    assert {"AE-DU", "AE-FED"} <= dubai
    assert "AE-AZ" not in dubai
    # the widening is one-directional: a federal case is not governed by a Dubai policy
    assert retriever.applicable_jurisdictions("AE-FED") == {"AE-FED"}


def test_applicability_filter_excludes_other_jurisdictions():
    result = retriever.search("critical result notification", jurisdiction="AE-DU", scope="applicable", top_k=10)
    assert result.chunks
    assert all(c.jurisdiction in {"AE-DU", "AE-FED"} for c in result.chunks)
    assert result.excluded_by_filter > 0


def test_comparator_scope_never_returns_an_applicable_source():
    result = retriever.search("critical result notification", jurisdiction="AE-DU", scope="comparator", top_k=10)
    assert result.chunks
    assert all(c.jurisdiction != "AE-DU" for c in result.chunks)
    assert any("never be applied" in n for n in result.notes)


def test_without_the_filter_a_foreign_rule_outranks_the_local_one():
    """This is the retrieval-only failure mode, demonstrated rather than asserted."""
    query = "critical result must be notified immediately to the responsible clinician read back"
    unfiltered = retriever.search(query, jurisdiction="AE-DU", scope="all", top_k=3)
    filtered = retriever.search(query, jurisdiction="AE-DU", scope="applicable", top_k=3)
    assert all(c.jurisdiction == "AE-DU" for c in filtered.chunks)
    assert unfiltered.chunks[0].jurisdiction != "AE-DU", (
        "expected an out-of-jurisdiction clause to dominate the unfiltered ranking"
    )


def test_retrieval_is_deterministic():
    a = retriever.search("genetic result patient communication", jurisdiction="AE-DU", top_k=5)
    b = retriever.search("genetic result patient communication", jurisdiction="AE-DU", top_k=5)
    assert [(c.chunk_id, c.score) for c in a.chunks] == [(c.chunk_id, c.score) for c in b.chunks]


def test_section_ids_are_searchable():
    result = retriever.search("13.4", jurisdiction="AE-DU", scope="applicable", top_k=3)
    assert any(c.section_id.startswith("13.4") for c in result.chunks)


def test_absent_evidence_is_reported_as_absent_not_as_permission():
    result = retriever.search("quantum teleportation of laboratory results", jurisdiction="AE-DU", top_k=3)
    if not result.chunks:
        assert any("NOT evidence" in n for n in result.notes)
