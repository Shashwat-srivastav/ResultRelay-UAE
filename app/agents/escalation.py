"""Agent D - Clinical Escalation Coordinator.

It decides *when a human must act*, not what the clinical answer is. It never asserts a
universal statutory deadline; the clock it uses is explicitly the configured profile value.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import Agent, assessment_confidence, scope_view
from app.models.schemas import AgentAssessment, AssessmentStatus, RecommendedAction

AGENT_ID = "escalation_coordinator"

#: Citations that are *product design controls*, never presented as regulation.
DESIGN_CONTROL_REFS = {
    "acknowledgment_transfer": "INV-8 / P1 institutional procedure (no source retrieved states that an earlier "
                               "acknowledgment satisfies a corrected result)",
}


class EscalationCoordinator(Agent):
    agent_id = AGENT_ID
    allowed_fields = (
        "case_id",
        "state",
        "current_revision_id",
        "revisions",
        "attempts",
        "acknowledgments",
        "profile_timers",
        "documentation_recorded",
        "event",
    )

    def assess(self, snapshot: dict[str, Any]) -> AgentAssessment:
        view = scope_view(snapshot, self.allowed_fields)
        current = view.get("current_revision_id")
        acks = view.get("acknowledgments") or []
        timers = view.get("profile_timers") or {}
        checked: list[str] = []
        reasons: list[str] = []

        current_acks = [a for a in acks if a.get("result_revision_id") == current]
        stale_acks = [a for a in acks if a.get("result_revision_id") != current]
        checked.append(
            f"acknowledgments: {len(current_acks)} for current revision {current}, "
            f"{len(stale_acks)} for other revisions"
        )

        correction_pending = view.get("state") == "CORRECTION_PENDING"
        correction_attempts = [a for a in (view.get("attempts") or []) if a.get("result_revision_id") == current]

        if stale_acks and not correction_pending:
            reasons.append(
                "an acknowledgment exists for an earlier revision only; it does not satisfy the configured "
                "acknowledgment requirement for the current revision (" + DESIGN_CONTROL_REFS["acknowledgment_transfer"] + ")"
            )

        deliveries = [a for a in view.get("attempts") or [] if a.get("delivered")]
        elapsed = timers.get("elapsed_minutes_since_delivery")
        clock = timers.get("acknowledgment_clock_minutes")
        if deliveries and not current_acks:
            if clock is not None and elapsed is not None and elapsed < clock:
                checked.append(
                    f"delivery confirmed {elapsed} min ago; the configured acknowledgment window "
                    f"({clock} min) has not elapsed, so no escalation is raised yet"
                )
            else:
                reasons.append(
                    f"delivery was confirmed (or the configured window of {clock} min elapsed) but no human "
                    f"acknowledged revision {current}; a delivery receipt is not an acknowledgment"
                )

        # Gateway acceptance with no receipt is not progress. Without this rule an accepted-but-lost
        # message waited forever: nothing else escalates a case that never reaches delivery (gap GR-15).
        waiting = timers.get("elapsed_minutes_since_acceptance_without_delivery")
        if not deliveries and not current_acks and waiting is not None:
            if clock is not None and waiting < clock:
                checked.append(
                    f"message accepted by the provider {waiting} min ago with no delivery receipt; the configured "
                    f"window ({clock} min) has not elapsed"
                )
            else:
                reasons.append(
                    f"the provider accepted the message {waiting} min ago and no delivery receipt or acknowledgment "
                    f"has arrived (configured window {clock} min); gateway acceptance is not delivery, so a person "
                    "must reach the recipient"
                )

        if clock is not None:
            checked.append(
                f"acknowledgment clock {clock} min is the configured institutional value "
                f"({timers.get('acknowledgment_clock_basis', 'basis not recorded')}), not a statutory deadline"
            )

        # The coordinator owns the question "is the configured acknowledgment workflow satisfied?".
        # It may therefore propose closure - but only when a current-revision acknowledgment and a
        # confirmed delivery both exist and no record has been written yet.
        else_action = None
        if correction_pending and not correction_attempts and not current_acks:
            # A corrected revision needs its own communication workflow. This requires a named human
            # to approve superseding the communicated result, so it is proposed, not auto-executed.
            else_action = RecommendedAction.SEND_PRIMARY
            checked.append(
                f"correction pending for revision {current}: a new communication workflow is required; "
                "the earlier acknowledgment does not transfer (INV-8)"
            )
        elif current_acks and deliveries and not view.get("documentation_recorded"):
            else_action = RecommendedAction.RECORD_DOCUMENTATION
            checked.append(
                "current-revision acknowledgment and delivery are both present; the communication record may be written"
            )

        escalate = bool(reasons)
        confidence, confidence_basis = assessment_confidence(
            checks=len(checked), unresolved=len(reasons), citations=0
        )
        return AgentAssessment(
            agent_id=self.agent_id,
            case_id=view.get("case_id", "unknown"),
            assessment_status=AssessmentStatus.REQUIRES_HUMAN if escalate else AssessmentStatus.OK,
            recommended_action=(
                RecommendedAction.ESCALATE_HUMAN if (escalate and else_action is None)
                else (else_action or RecommendedAction.NO_ACTION)
            ),
            applicable_sources=[],
            conditions_checked=checked,
            conditions_unresolved=reasons,
            confidence=confidence,
            requires_human_review=escalate,
            concise_rationale=(
                "Escalation to the configured responsible role is required: " + "; ".join(reasons[:2])
                if escalate
                else "No human decision is required at this step."
            ),
            data={
                "confidence_basis": confidence_basis,
                "escalation_role": (timers.get("escalation_role") or "SUPERVISOR"),
                "escalation_after_minutes": timers.get("escalation_after_minutes"),
                "basis": "PRODUCT_DESIGN_CONTROL",
                # Escalation reasons are advisory: closure is blocked by the documentation guard,
                # not by this agent's opinion.
                "blocking_conditions": [],
            },
            context_scope=list(self.allowed_fields),
        )
