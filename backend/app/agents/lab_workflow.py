"""Agent A - Laboratory Workflow Agent.

Scope: result identity and revision lineage only. It cannot see contact details, channel
state, or transport outcomes, and it may not authorise an exceptional communication action.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import Agent, citation, scope_view
from app.models.schemas import (
    AgentAssessment,
    AssessmentStatus,
    ClaimClassification,
    RecommendedAction,
)

AGENT_ID = "lab_workflow"


class LabWorkflowAgent(Agent):
    agent_id = AGENT_ID
    allowed_fields = (
        "case_id",
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
            sources.append(
                {
                    "chunk_id": "S1-9.1.5.g",
                    "source_id": "S1",
                    "section_id": "9.1.5(g)",
                    "page_start": 29,
                    "claim_classification": "BINDING_REQUIREMENT",
                    "text": "The laboratory shall have a mechanism for correcting erroneous result in a manner that identifies the corrected result as revised and the date and time of correction.",
                    "score": 0.0,
                }
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

        return AgentAssessment(
            agent_id=self.agent_id,
            case_id=view.get("case_id", "unknown"),
            assessment_status=status,
            recommended_action=action,
            applicable_sources=[citation(c, ClaimClassification.BINDING_REQUIREMENT) for c in sources],
            conditions_checked=checked,
            conditions_unresolved=unresolved,
            confidence=0.9 if not unresolved else 0.6,
            requires_human_review=bool(unresolved),
            concise_rationale=(
                f"Revision {current} is current. " + ("; ".join(unresolved) if unresolved else
                "Result lineage is consistent and the communication may reference this revision.")
            ),
            data={
                "current_revision": current,
                "event_revision": ev_rev,
                "confidence_basis": "deterministic rule coverage",
                # Lineage and stale-revision defects block closure; they also drive escalation.
                "blocking_conditions": [u for u in unresolved if "revision" in u or "supersede" in u],
            },
            context_scope=list(self.allowed_fields),
        )
