"""A deterministic stand-in adviser.

This exists so the containment path can be *tested* without a model. It is not an AI: it reads the
retrieved evidence and applies three ordered rules. Its value is that it can be made to misbehave on
demand (propose a send when the case is unresolved, or cite a foreign clause), which is how the
guard's refusal paths get exercised in CI rather than asserted in prose.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.advisers.base import AdvisoryProposal
from app.models.schemas import RecommendedAction


@dataclass
class RuleBasedAdviser:
    """Not a model. Deterministic, offline, and only ever proposes."""

    name: str = "rule-based-stub"

    def propose(self, *, jurisdiction: str, situation: str, evidence: list[dict]) -> AdvisoryProposal:
        cited = tuple(str(c.get("chunk_id")) for c in evidence if c.get("chunk_id"))
        text = (situation or "").lower()
        if not evidence:
            return AdvisoryProposal(
                candidate_action=RecommendedAction.AWAIT_EVIDENCE,
                rationale="no applicable clause was retrieved, so nothing authorises an action",
                citation_chunk_ids=(),
                confidence=0.2,
                is_model_generated=False,
            )
        if "delivery unknown" in text or "timeout" in text:
            action = RecommendedAction.RECONCILE_ATTEMPT
            why = "delivery state is indeterminate; reconciliation is read-only and cannot duplicate a send"
        elif "corrected" in text or "revised" in text:
            action = RecommendedAction.OPEN_CORRECTION_TASK
            why = "a correction needs its own workflow and a fresh acknowledgment"
        else:
            action = RecommendedAction.SEND_PRIMARY
            why = "the retrieved clause permits reporting the result to the patient"
        return AdvisoryProposal(
            candidate_action=action,
            rationale=why,
            citation_chunk_ids=cited[:3],
            confidence=0.5,
            is_model_generated=False,
        )
