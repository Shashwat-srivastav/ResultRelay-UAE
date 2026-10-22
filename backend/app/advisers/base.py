"""Types shared by every adviser.

An :class:`AdvisoryProposal` is deliberately poorer than an :class:`AgentAssessment`: it has no
status, no gate decision and no ability to write to a case. It carries a candidate action, the
chunks it relies on, and its own confidence - nothing that the state machine reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from app.models.schemas import RecommendedAction


class AdvisoryStatus(str, Enum):
    DISABLED = "DISABLED"
    REFUSED_RESIDENCY = "REFUSED_RESIDENCY"
    REJECTED_UNGROUNDED = "REJECTED_UNGROUNDED"
    REJECTED_OUT_OF_JURISDICTION = "REJECTED_OUT_OF_JURISDICTION"
    REJECTED_MALFORMED = "REJECTED_MALFORMED"
    ADVISORY_ONLY = "ADVISORY_ONLY"


@dataclass(frozen=True)
class AdvisoryProposal:
    """What an adviser is allowed to return."""

    candidate_action: RecommendedAction
    rationale: str
    citation_chunk_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    is_model_generated: bool = True


@dataclass(frozen=True)
class AdvisoryRecord:
    """What the system keeps, and the only thing the gate ever sees."""

    status: AdvisoryStatus
    mode: str
    reason: str
    proposal: AdvisoryProposal | None = None
    policy_refs: tuple[str, ...] = ()
    residency: str | None = None
    endpoint: str | None = None
    checks: tuple[str, ...] = ()

    @property
    def considered(self) -> bool:
        return self.status is AdvisoryStatus.ADVISORY_ONLY

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "mode": self.mode,
            "reason": self.reason,
            "residency": self.residency,
            "endpoint": self.endpoint,
            "policy_refs": list(self.policy_refs),
            "checks": list(self.checks),
            "candidate_action": (
                self.proposal.candidate_action.value if self.proposal else None
            ),
            "citation_chunk_ids": (
                list(self.proposal.citation_chunk_ids) if self.proposal else []
            ),
            "confidence": self.proposal.confidence if self.proposal else None,
            "classification": "PRODUCT_DESIGN_CONTROL" if self.proposal else None,
        }


class Adviser(Protocol):
    """Anything that can return a proposal. It is never given the ability to act."""

    name: str

    def propose(self, *, jurisdiction: str, situation: str, evidence: list[dict]) -> AdvisoryProposal:
        ...
