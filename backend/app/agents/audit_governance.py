"""Agent E - Audit and Governance Agent.

It validates that consequential proposals are traceable, and it is able to *reject* an
assessment emitted by another agent. It never edits history; it only appends findings.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import Agent, scope_view
from app.kb.retriever import all_chunks
from app.models.schemas import (
    AgentAssessment,
    AssessmentStatus,
    ClaimClassification,
    RecommendedAction,
)

AGENT_ID = "audit_governance"

CONSEQUENTIAL = {
    RecommendedAction.SEND_PRIMARY,
    RecommendedAction.RETRY_SAME_CHANNEL,
    RecommendedAction.PROPOSE_FALLBACK,
    RecommendedAction.ESCALATE_HUMAN,
    RecommendedAction.OPEN_CORRECTION_TASK,
    RecommendedAction.RECORD_DOCUMENTATION,
}


class AuditGovernanceAgent(Agent):
    agent_id = AGENT_ID
    allowed_fields = ("case_id", "jurisdiction", "current_revision_id", "assessments", "gate_decision", "state")

    def assess(self, snapshot: dict[str, Any]) -> AgentAssessment:
        view = scope_view(snapshot, self.allowed_fields)
        jurisdiction = view.get("jurisdiction", "AE-DU")
        current = view.get("current_revision_id")
        assessments: list[AgentAssessment] = view.get("assessments") or []
        gate = view.get("gate_decision") or {}

        known_chunks = {c["chunk_id"]: c for c in all_chunks()}
        known_refs = {(c["source_id"], c["section_id"]): c for c in all_chunks()}

        findings: list[str] = []
        checked: list[str] = []

        for a in assessments:
            # Transport and escalation agents cite no sources by design; the gate is not an agent.
            if a.agent_id in {"audit_governance", "network_delivery", "escalation_coordinator", "deterministic_gate"}:
                continue
            if a.recommended_action in CONSEQUENTIAL and not a.applicable_sources:
                # Permitted only when the action is explicitly a product design control.
                if a.agent_id == "escalation_coordinator":
                    continue
                findings.append(
                    f"{a.agent_id} proposed {a.recommended_action.value} without an applicable source citation"
                )
            for src in a.applicable_sources:
                ref = known_refs.get((src.source_id, src.section))
                if ref is None:
                    findings.append(
                        f"{a.agent_id} cited {src.source_id} {src.section} which is not in the verified corpus "
                        "(possible invented citation)"
                    )
                    continue
                if ref["jurisdiction"] != jurisdiction and src.claim_type in (
                    ClaimClassification.BINDING_REQUIREMENT,
                    ClaimClassification.OFFICIAL_GUIDANCE,
                ):
                    findings.append(
                        f"{a.agent_id} treated {src.source_id} ({ref['jurisdiction']}) as "
                        f"{src.claim_type.value} for a {jurisdiction} case - jurisdiction violation"
                    )
                if current and "revision" in ref["text"].lower() and current not in (a.data.get("current_revision") or current):
                    findings.append(f"{a.agent_id} assessment appears bound to a stale revision")

        checked.append(f"validated {len(assessments)} assessment(s) against {len(known_chunks)} verified chunk(s)")

        gate_grounded = bool(gate.get("reason"))
        if gate and not gate_grounded:
            findings.append("gate decision recorded without a reason")

        return AgentAssessment(
            agent_id=self.agent_id,
            case_id=view.get("case_id", "unknown"),
            assessment_status=AssessmentStatus.REQUIRES_HUMAN if findings else AssessmentStatus.OK,
            recommended_action=RecommendedAction.NO_ACTION,
            applicable_sources=[],
            conditions_checked=checked,
            conditions_unresolved=findings,
            confidence=0.75,
            requires_human_review=bool(findings),
            concise_rationale=(
                "Audit findings: " + "; ".join(findings[:3]) if findings
                else "All consequential proposals are traceable to verified sources or declared design controls."
            ),
            data={"findings": findings, "gate_grounded": gate_grounded},
            context_scope=list(self.allowed_fields),
        )
