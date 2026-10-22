"""Shared plumbing for the role-scoped agents.

Information asymmetry is implemented here, not merely documented: each agent declares the
fields it may see, and the orchestrator hands it a filtered view. The view keys are echoed
back inside every assessment (``context_scope``) so an evaluator can verify the scoping from
the audit log alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models.schemas import AgentAssessment, SourceCitation, ClaimClassification


class Agent(Protocol):
    agent_id: str
    allowed_fields: tuple[str, ...]

    def assess(self, view: dict[str, Any]) -> AgentAssessment: ...


def scope_view(snapshot: dict[str, Any], allowed: tuple[str, ...]) -> dict[str, Any]:
    """Return only the permitted fields. Absent fields are absent, not null - this keeps the
    audit record honest about what the agent could and could not know."""
    return {k: snapshot[k] for k in allowed if k in snapshot}


def citation(chunk: dict[str, Any], claim_type: ClaimClassification | None = None) -> SourceCitation:
    return SourceCitation(
        source_id=chunk["source_id"],
        section=chunk["section_id"],
        page=int(chunk["page_start"]),
        claim_type=claim_type or ClaimClassification(chunk["claim_classification"]),
        quote=(chunk["text"][:280] + ("..." if len(chunk["text"]) > 280 else "")),
    )


def support_score(chunks: list[dict[str, Any]], ceiling: float = 15.0) -> float:
    """A transparent heuristic, not a calibrated probability.

    Reported as ``confidence`` because the schema requires a number, and disclosed in
    ``data.confidence_basis`` so nobody mistakes it for model certainty.
    """
    if not chunks:
        return 0.35
    top = max(float(c.get("score") or 0.0) for c in chunks)
    return round(min(0.95, 0.35 + 0.55 * min(1.0, top / ceiling)), 3)
