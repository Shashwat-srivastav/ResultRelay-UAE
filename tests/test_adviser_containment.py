"""M-1 and M-4: what a model is allowed to put in an advisory record.

M-1  Confidence 9.9 was stored and displayed verbatim.
M-4  A citation was accepted if the chunk id existed anywhere in the corpus, even when the adviser
     had never been shown that chunk. A model could therefore cite a clause it did not read.
"""

from __future__ import annotations

import pytest

from app.advisers.base import AdvisoryProposal, AdvisoryStatus
from app.advisers.guard import advise
from app.kb import retriever
from app.models.schemas import RecommendedAction


class _StubAdviser:
    def __init__(self, proposal):  # noqa: ANN001 - test double
        self._proposal = proposal

    def propose(self, *, jurisdiction, situation, evidence):  # noqa: ANN001, ARG002
        return self._proposal


@pytest.fixture(scope="module")
def local_chunks():
    chunks = [
        c for c in retriever.all_chunks()
        if c["jurisdiction"] in (retriever.applicable_jurisdictions("AE-DU") or set())
    ]
    assert len(chunks) >= 2, "the corpus must carry at least two UAE clauses for this test"
    return chunks


def _evidence(chunks):  # noqa: ANN001, ANN202
    return [
        {
            "chunk_id": c["chunk_id"],
            "source_id": c["source_id"],
            "section_id": c["section_id"],
            "jurisdiction": c["jurisdiction"],
            "text": c["text"],
        }
        for c in chunks
    ]


def test_confidence_is_clamped_and_the_clamp_is_recorded(local_chunks):
    shown = local_chunks[:1]
    proposal = AdvisoryProposal(
        candidate_action=RecommendedAction.AWAIT_EVIDENCE,
        rationale="synthetic",
        citation_chunk_ids=(shown[0]["chunk_id"],),
        confidence=9.9,
    )
    record = advise(
        jurisdiction="AE-DU",
        situation="synthetic",
        evidence=_evidence(shown),
        adviser=_StubAdviser(proposal),
        endpoint="http://127.0.0.1:11434/api/generate",
        enabled=True,
    )
    assert record.status is AdvisoryStatus.ADVISORY_ONLY, record.reason
    assert record.proposal.confidence == pytest.approx(1.0)
    assert any("clamped" in c for c in record.checks)


def test_citation_outside_the_supplied_evidence_is_rejected(local_chunks):
    shown = local_chunks[:1]
    unseen = local_chunks[1]
    assert unseen["chunk_id"] != shown[0]["chunk_id"]
    proposal = AdvisoryProposal(
        candidate_action=RecommendedAction.AWAIT_EVIDENCE,
        rationale="synthetic",
        citation_chunk_ids=(unseen["chunk_id"],),
        confidence=0.5,
    )
    record = advise(
        jurisdiction="AE-DU",
        situation="synthetic",
        evidence=_evidence(shown),
        adviser=_StubAdviser(proposal),
        endpoint="http://127.0.0.1:11434/api/generate",
        enabled=True,
    )
    assert record.status is AdvisoryStatus.REJECTED_UNGROUNDED, record.status
    assert unseen["chunk_id"] in record.reason


def test_citation_inside_the_supplied_evidence_still_passes(local_chunks):
    shown = local_chunks[:2]
    proposal = AdvisoryProposal(
        candidate_action=RecommendedAction.AWAIT_EVIDENCE,
        rationale="synthetic",
        citation_chunk_ids=(shown[1]["chunk_id"],),
        confidence=0.4,
    )
    record = advise(
        jurisdiction="AE-DU",
        situation="synthetic",
        evidence=_evidence(shown),
        adviser=_StubAdviser(proposal),
        endpoint="http://127.0.0.1:11434/api/generate",
        enabled=True,
    )
    assert record.status is AdvisoryStatus.ADVISORY_ONLY, record.reason
    assert record.proposal.confidence == pytest.approx(0.4)
    assert any("evidence supplied" in c for c in record.checks)


def test_any_citation_when_no_evidence_was_supplied_is_rejected(local_chunks):
    proposal = AdvisoryProposal(
        candidate_action=RecommendedAction.AWAIT_EVIDENCE,
        rationale="synthetic",
        citation_chunk_ids=(local_chunks[0]["chunk_id"],),
        confidence=0.4,
    )
    record = advise(
        jurisdiction="AE-DU",
        situation="synthetic",
        evidence=[],
        adviser=_StubAdviser(proposal),
        endpoint="http://127.0.0.1:11434/api/generate",
        enabled=True,
    )
    assert record.status is AdvisoryStatus.REJECTED_UNGROUNDED, record.status
