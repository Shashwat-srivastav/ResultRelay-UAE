"""Typed schemas shared by the API, the agents, and the evaluation harness.

Every agent response is validated by Pydantic before the orchestrator may act on it.
A malformed or ungrounded assessment is rejected, not repaired by an LLM.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ClaimClassification(str, Enum):
    BINDING_REQUIREMENT = "BINDING_REQUIREMENT"
    OFFICIAL_GUIDANCE = "OFFICIAL_GUIDANCE"
    INSTITUTIONAL_PROCEDURE = "INSTITUTIONAL_PROCEDURE"
    GLOBAL_COMPARATOR = "GLOBAL_COMPARATOR"
    PRODUCT_DESIGN_CONTROL = "PRODUCT_DESIGN_CONTROL"
    RESEARCH_HYPOTHESIS = "RESEARCH_HYPOTHESIS"
    UNRESOLVED = "UNRESOLVED"


class AssessmentStatus(str, Enum):
    OK = "OK"
    HOLD_FOR_EVIDENCE = "HOLD_FOR_EVIDENCE"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RecommendedAction(str, Enum):
    SEND_PRIMARY = "SEND_PRIMARY"
    AWAIT_EVIDENCE = "AWAIT_EVIDENCE"
    RECONCILE_ATTEMPT = "RECONCILE_ATTEMPT"
    RETRY_SAME_CHANNEL = "RETRY_SAME_CHANNEL"
    PROPOSE_FALLBACK = "PROPOSE_FALLBACK"
    AWAIT_ACKNOWLEDGMENT = "AWAIT_ACKNOWLEDGMENT"
    RECORD_DOCUMENTATION = "RECORD_DOCUMENTATION"
    OPEN_CORRECTION_TASK = "OPEN_CORRECTION_TASK"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    VERIFY_RECIPIENT = "VERIFY_RECIPIENT"
    NO_ACTION = "NO_ACTION"


class SourceCitation(BaseModel):
    source_id: str
    section: str
    page: int = Field(ge=1)
    claim_type: ClaimClassification
    quote: str | None = None

    @field_validator("section")
    @classmethod
    def _non_empty_section(cls, v: str) -> str:
        if not v or v.strip() in {"", "-", "n/a", "N/A"}:
            raise ValueError("a citation must identify an exact section, not just a document title")
        return v


class AgentAssessment(BaseModel):
    """The structured message every agent must emit."""

    agent_id: str
    case_id: str
    assessment_status: AssessmentStatus
    recommended_action: RecommendedAction
    applicable_sources: list[SourceCitation] = Field(default_factory=list)
    conditions_checked: list[str] = Field(default_factory=list)
    conditions_unresolved: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    requires_human_review: bool
    concise_rationale: str
    #: Free-form structured extras (never instructions).
    data: dict[str, Any] = Field(default_factory=dict)
    #: Which fields the agent was allowed to see; proves information asymmetry.
    context_scope: list[str] = Field(default_factory=list)
    mode: Literal["DETERMINISTIC", "LLM"] = "DETERMINISTIC"

    @field_validator("concise_rationale")
    @classmethod
    def _rationale_len(cls, v: str) -> str:
        if len(v) > 1200:
            raise ValueError("rationale too long; this field is a summary, not a reasoning dump")
        return v


class EvidenceChunk(BaseModel):
    chunk_id: str
    source_id: str
    title: str
    issuer: str
    jurisdiction: str
    document_version: str
    section_id: str
    page_start: int
    page_end: int
    publication_date: str
    effective_date: str
    source_type: str
    applicability: str
    claim_classification: ClaimClassification
    text: str
    source_url: str
    verification_status: str
    #: Outcome of the quote check against the source text (see app/kb/ingest.py).
    excerpt_status: str = ""
    #: Physical PDF page, which can differ from the printed page a reader sees.
    pdf_page_start: int | None = None
    pdf_page_end: int | None = None
    support_note: str = ""
    #: Declared on the excerpt, never inferred from its words. True only where the quoted clause
    #: itself authorises an alternative channel; the policy agent reads this field instead of
    #: pattern-matching the text (see the H-1 finding in docs/audit-disposition.md).
    authorises_fallback: bool = False
    topics: list[str] = Field(default_factory=list)
    score: float | None = None
    matched_terms: list[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    query: str
    filters: dict[str, Any] = Field(default_factory=dict)
    chunks: list[EvidenceChunk] = Field(default_factory=list)
    considered: int = 0
    excluded_by_filter: int = 0
    notes: list[str] = Field(default_factory=list)


class GateDecision(BaseModel):
    """The deterministic decision. Never produced by an agent."""

    permitted: bool
    enforced_action: RecommendedAction
    reason: str
    invariant: str | None = None
    blocked_actions: list[str] = Field(default_factory=list)
    conditions_checked: list[str] = Field(default_factory=list)
    requires_human: bool = False
    policy_refs: list[str] = Field(default_factory=list)
    #: The advisory layer's record, attached after the decision was computed. Present only when an
    #: adviser was configured; never read by the gate.
    advisory: dict[str, Any] | None = None
    #: True when an adviser proposed something the gate did not enforce.
    advisory_overruled: bool = False
