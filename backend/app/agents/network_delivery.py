"""Agent C - Network and Delivery Agent.

Scope: transport evidence only. It may not see patient identity or clinical content, and it
cannot declare that a human received or understood anything.

Its single most important job is refusing to collapse four different facts into one:
  attempted < accepted < delivered < acknowledged.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import Agent, scope_view
from app.models.schemas import AgentAssessment, AssessmentStatus, RecommendedAction

AGENT_ID = "network_delivery"


class NetworkDeliveryAgent(Agent):
    agent_id = AGENT_ID
    allowed_fields = (
        "case_id",
        "state",
        "attempts",
        "channels",
        "profile_retry",
        "event",
        "current_revision_id",
    )

    def assess(self, snapshot: dict[str, Any]) -> AgentAssessment:
        view = scope_view(snapshot, self.allowed_fields)
        current = view.get("current_revision_id")
        all_attempts = view.get("attempts") or []
        # Evidence from an older revision is retained in the case but must not drive this revision.
        attempts = [a for a in all_attempts if a.get("result_revision_id") in (current, None)]
        stale_attempts = [a for a in all_attempts if a.get("result_revision_id") not in (current, None)]
        channels = view.get("channels") or []
        checked: list[str] = []
        unresolved: list[str] = []

        accepted = [a for a in attempts if a.get("accepted")]
        delivered = [a for a in attempts if a.get("delivered")]
        unknown = [a for a in attempts if a.get("outcome") in ("TIMEOUT", "UNKNOWN")]
        unreconciled = [a for a in unknown if not a.get("reconciled")]
        failed = [a for a in attempts if a.get("failed")]
        suppressed = [a for a in attempts if a.get("duplicate_suppressed")]

        checked.append(f"attempts={len(attempts)} accepted={len(accepted)} delivered={len(delivered)} "
                       f"unknown={len(unknown)} unreconciled={len(unreconciled)} failed={len(failed)}")
        if stale_attempts:
            checked.append(
                f"{len(stale_attempts)} attempt(s) belong to an earlier revision and are excluded from this revision's state"
            )

        if accepted and not delivered:
            checked.append("provider acceptance observed without an endpoint receipt: this is NOT delivery")

        if len(delivered) > 1:
            unresolved.append(f"{len(delivered)} delivery receipts observed - possible duplicate fulfilment")

        if unreconciled:
            status = AssessmentStatus.HOLD_FOR_EVIDENCE
            action = RecommendedAction.RECONCILE_ATTEMPT
            checked.append("outcome uncertain; reconciliation is required before any retry (INV-4)")
        elif delivered:
            status = AssessmentStatus.OK
            action = RecommendedAction.AWAIT_ACKNOWLEDGMENT
        elif failed and [c for c in channels if c.get("primary") and c.get("status") != "UP"]:
            status = AssessmentStatus.REQUIRES_HUMAN
            action = RecommendedAction.PROPOSE_FALLBACK
        elif failed:
            status = AssessmentStatus.OK
            action = RecommendedAction.RETRY_SAME_CHANNEL
        elif attempts and any(a.get("reconciled") for a in attempts):
            if [c for c in channels if c.get("primary") and c.get("status") != "UP"]:
                status = AssessmentStatus.REQUIRES_HUMAN
                action = RecommendedAction.PROPOSE_FALLBACK
            else:
                status = AssessmentStatus.OK
                action = RecommendedAction.RETRY_SAME_CHANNEL
        elif not attempts:
            status = AssessmentStatus.OK
            action = RecommendedAction.SEND_PRIMARY
        else:
            status = AssessmentStatus.HOLD_FOR_EVIDENCE
            action = RecommendedAction.RECONCILE_ATTEMPT

        # Channel outage is reported as a fact. It is not an authorisation.
        primary_down = [c for c in channels if c.get("primary") and c.get("status") != "UP"]
        if primary_down:
            checked.append(
                f"primary channel {primary_down[0]['channel_id']} is {primary_down[0]['status']}; "
                "a channel outage does not authorise an alternative recipient or channel (INV-9)"
            )

        return AgentAssessment(
            agent_id=self.agent_id,
            case_id=view.get("case_id", "unknown"),
            assessment_status=status,
            recommended_action=action,
            applicable_sources=[],
            conditions_checked=checked,
            conditions_unresolved=unresolved,
            confidence=0.85,
            requires_human_review=bool(unreconciled) or bool(primary_down),
            concise_rationale="; ".join(checked[-2:]) if checked else "no transport activity observed",
            data={
                "attempted": len(attempts),
                "accepted": len(accepted),
                "delivered": len(delivered),
                "unknown": len(unknown),
                "unreconciled": len(unreconciled),
                "failed": len(failed),
                "duplicates_suppressed": len(suppressed),
                "primary_channel_down": bool(primary_down),
                "blocking_conditions": unresolved,
            },
            context_scope=list(self.allowed_fields),
        )
