"""Agent A - Laboratory Workflow Agent.

Scope: result identity and revision lineage only. It cannot see contact details, channel
state, or transport outcomes, and it may not authorise an exceptional communication action.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import Agent, assessment_confidence, citation, scope_view
from app.kb.retriever import search
from app.models.schemas import (
    AgentAssessment,
    AssessmentStatus,
    ClaimClassification,
    RecommendedAction,
)

AGENT_ID = "lab_workflow"

#: The question this agent asks the corpus when a correction is in play.
CORRECTION_QUERY = "correcting erroneous result revised original and corrected reports maintained"
#: Relevance floor, matching the policy agent: below it the honest answer is "nothing retrieved".
POLICY_MIN_SCORE = 1.0


class LabWorkflowAgent(Agent):
    agent_id = AGENT_ID
    allowed_fields = (
        "case_id",
        # Which corpus layer can bind the case. It cannot see contact details, channel state or
        # transport outcomes, and it still may not authorise an exceptional action.
        "jurisdiction",
        "case_scope",
        "current_revision_id",
        "revisions",
        "state",
        "event",
        "documentation_recorded",
    )

    def assess(self, snapshot: dict[str, Any]) -> AgentAssessment:
        view = scope_view(snapshot, self.allowed_fields)
        event = view.get("event") or {}
        current = view.get("current_revision_id")
        revisions = view.get("revisions") or []
        unresolved: list[str] = []
        checked: list[str] = []
        sources: list = []

        ev_type = event.get("type")
        ev_rev = event.get("result_revision_id")

        checked.append(f"event type = {ev_type}; event revision = {ev_rev}; current revision = {current}")

        # 1. A correction must reference the revision it supersedes.
        if ev_type == "result.corrected":
            supersedes = event.get("supersedes_revision_id")
            if not supersedes:
                unresolved.append("corrected result does not identify the revision it supersedes (INV-6)")
            elif supersedes not in {r.get("revision_id") for r in revisions}:
                unresolved.append(f"corrected result references unknown revision {supersedes}")
            else:
                checked.append(f"correction lineage resolved: {supersedes} -> {current}")
            # Retrieved, not remembered. The previous version appended a literal dict for
            # S1 9.1.5(g) with ``score: 0.0`` and never called the retriever, so the citation was
            # printed whether or not the clause was in the corpus at all (red-team finding H-1).
            correction_hits = search(
                CORRECTION_QUERY,
                jurisdiction=view.get("jurisdiction", "AE-DU"),
                scope="applicable",
                top_k=3,
                min_score=POLICY_MIN_SCORE,
            )
            correction_clauses = [
                c for c in correction_hits.chunks
                if c.source_id == "S1" and "correction" in (c.topics or [])
            ]
            if correction_clauses:
                sources.append(correction_clauses[0].model_dump())
                checked.append(
                    f"correction clause retrieved: {correction_clauses[0].source_id} "
                    f"{correction_clauses[0].section_id}"
                )
            else:
                unresolved.append(
                    "no applicable clause on correcting erroneous results was retrieved; the "
                    "correction duty is unsourced for this case"
                )

        # 2. Stale-event detection: an event for an older revision must not advance the case.
        if ev_rev and current and ev_rev != current:
            unresolved.append(
                f"event refers to revision {ev_rev}, which is not the current revision {current}; "
                "the event is preserved but cannot satisfy the current communication requirement"
            )

        # 3. Required structured information.
        if not view.get("revisions"):
            unresolved.append("no result revision is present in the case record")
        # 4. Recommendation is deliberately conservative and never an authorisation.
        if unresolved:
            action = RecommendedAction.OPEN_CORRECTION_TASK if ev_type == "result.corrected" else RecommendedAction.AWAIT_EVIDENCE
            status = AssessmentStatus.REQUIRES_HUMAN
        elif ev_type == "result.finalized":
            action = RecommendedAction.SEND_PRIMARY
            status = AssessmentStatus.OK
        else:
            action = RecommendedAction.NO_ACTION
            status = AssessmentStatus.OK

        confidence, confidence_basis = assessment_confidence(
            checks=len(checked), unresolved=len(unresolved), citations=len(sources)
        )
        return AgentAssessment(
            agent_id=self.agent_id,
            case_id=view.get("case_id", "unknown"),
            assessment_status=status,
            recommended_action=action,
            applicable_sources=[citation(c, ClaimClassification.BINDING_REQUIREMENT) for c in sources],
            conditions_checked=checked,
            conditions_unresolved=unresolved,
            confidence=confidence,
            requires_human_review=bool(unresolved),
            concise_rationale=(
                f"Revision {current} is current. " + ("; ".join(unresolved) if unresolved else
                "Result lineage is consistent and the communication may reference this revision.")
            ),
            data={
                "current_revision": current,
                "event_revision": ev_rev,
                "confidence_basis": confidence_basis,
                # Lineage and stale-revision defects block closure; they also drive escalation.
                "blocking_conditions": [
                    u for u in unresolved
                    if "revision" in u or "supersede" in u or "correction duty is unsourced" in u
                ],
            },
            context_scope=list(self.allowed_fields),
        )
