"""Agent B - Policy Applicability Agent.

Responsibilities: decide *whether* a retrieved instrument applies before treating it as a rule.
This is the agent whose behaviour the whole thesis turns on, so its failure modes are explicit:

* It never promotes a foreign-jurisdiction document to a binding requirement.
* It never invents a clause. Every citation is a chunk id returned by the retriever.
* When the corpus is silent, it returns HOLD_FOR_EVIDENCE and says what is unknown.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import Agent, citation, scope_view, support_score
from functools import partial

from app.kb.retriever import search as _search

# The gate's inputs come from BM25 over the verified index, always: they must not change with whether a vector
# store or Ollama happens to be available. Hybrid ranking serves /api/kb/search and the retrieval check.
search = partial(_search, engine="bm25")
from app.models.schemas import (
    AgentAssessment,
    AssessmentStatus,
    ClaimClassification,
    RecommendedAction,
)

AGENT_ID = "policy_applicability"

#: Which workflow stages need which policy question answered.
STAGE_QUERIES = {
    "finalize": "critical laboratory results reported clearly to the patient walk-in",
    "send": "critical laboratory results reported clearly to the patient walk-in permitted tests",
    "correction": "correcting erroneous result revised original and corrected reports maintained",
    "acknowledgment": "record of the communication with the patient acknowledgment",
    "fallback": "alternative channel notification method patient contact confidentiality",
    "scope": "genetic results communicated to patients referring treating physician",
    "walkin": "walk-in patients laboratory tests physician order permitted",
    "correction": "correcting erroneous result revised original and corrected reports maintained",
}


#: Relevance floor for policy retrieval.
#:
#: ``min_score=0`` meant the top-k chunks were always cited, whether or not they had anything to do
#: with the question — the "irrelevant evidence scores highly" failure in the audit (C2/C9). A small
#: positive floor makes an empty result possible, and an empty result is the honest answer when the
#: corpus does not address the question.
POLICY_MIN_SCORE = 1.0


class PolicyApplicabilityAgent(Agent):
    agent_id = AGENT_ID
    allowed_fields = (
        "case_id",
        "jurisdiction",
        "facility_type",
        "case_scope",
        "current_revision_id",
        "state",
        "workflow_stage",
        "event",
        "policy_profile",
        "applicability_filter",
    )

    def assess(self, snapshot: dict[str, Any]) -> AgentAssessment:
        view = scope_view(snapshot, self.allowed_fields)
        jurisdiction = view.get("jurisdiction", "AE-DU")
        stage = view.get("workflow_stage", "send")
        scope = view.get("case_scope", "WALK_IN")
        profile = view.get("policy_profile") or {}
        unresolved: list[str] = []
        #: Conditions that must prevent closure (INV-10), as distinct from open research questions.
        #: Emitting these at all is the fix for red-team finding H-6: the previous version returned
        #: an empty list unconditionally, so no policy-evidence failure could ever block a case.
        blocking: list[str] = []
        checked: list[str] = []

        query = STAGE_QUERIES.get(stage, STAGE_QUERIES["send"])
        if scope == "GENETIC":
            query = STAGE_QUERIES["scope"]

        # The applicability filter is a configuration capability: when it is disabled the agent
        # retrieves across jurisdictions, which is exactly the citation-only baseline's behaviour.
        filtered = bool(view.get("applicability_filter", True))
        applicable = search(
            query,
            jurisdiction=jurisdiction,
            scope="applicable" if filtered else "all",
            top_k=4,
        )
        comparators = search(query, jurisdiction=jurisdiction, scope="comparator", top_k=3)

        checked.append(
            f"retrieval: {len(applicable.chunks)} applicable chunk(s) for jurisdiction {jurisdiction}, "
            f"{len(comparators.chunks)} out-of-jurisdiction comparator(s) kept separate"
        )
        if not applicable.chunks:
            blocking.append(
                f"no applicable policy evidence retrieved for jurisdiction {jurisdiction}"
            )

        sources = []
        for c in applicable.chunks[:3]:
            if filtered:
                sources.append(citation(c.model_dump()))
            else:
                # Without an applicability filter the agent has no concept of a comparator: it
                # presents whatever scores highest as the governing rule. This is the defining
                # limitation of the citation-only baseline, modelled rather than asserted.
                sources.append(citation(c.model_dump(), ClaimClassification.BINDING_REQUIREMENT))

        # --- scope gate ---------------------------------------------------
        # The reason text is built from the chunk that was actually retrieved. The previous version
        # appended a hardcoded "(S1 13.4)" whatever the retriever returned, so deleting the clause
        # from the corpus left the citation in the trace: a fabricated authority shown to a human
        # reviewer (red-team finding H-1).
        scope_permitted = True
        # The recipient is an evidence question. A clause may *declare* that results of this class go
        # to the referring/treating physician (`routes_to_physician`, verified at ingest against the
        # quoted sentence). If such a clause is retrieved, the message is addressed to the physician;
        # if it is not, the recipient is the patient and the scope gate applies. Delete the clause
        # and the route disappears - which is the only sense in which this behaviour is
        # "evidence-driven" (red-team finding H-4).
        physician_route = next((c for c in applicable.chunks if c.routes_to_physician), None)
        recipient = "PHYSICIAN" if physician_route else "PATIENT"
        # Topic tags are declared on the excerpt, so this is a metadata lookup, not a keyword guess
        # over prose. A routing claim is only made from a chunk tagged for genetic results.
        genetic_hits = [
            c for c in applicable.chunks
            if c.source_id == "S1" and "genetic" in (c.topics or [])
        ]
        if scope == "GENETIC":
            # Direct-to-patient communication is not permitted for this scope in either case.
            scope_permitted = False
            if genetic_hits:
                route = genetic_hits[0]
                sources.append(citation(route.model_dump()))
                if physician_route is not None:
                    unresolved.append(
                        f"genetic results may not be communicated directly to the patient; "
                        f"{physician_route.source_id} {physician_route.section_id} directs them to the "
                        "referring/treating physician, so the message is addressed to that physician"
                    )
                else:
                    unresolved.append(
                        f"genetic results may not be communicated directly to the patient; "
                        f"{route.source_id} {route.section_id} governs this scope but no retrieved "
                        "clause declares a physician recipient, so no route is authorised"
                    )
                    blocking.append(
                        "genetic scope retrieved no clause naming a physician recipient: "
                        "the route is unsourced"
                    )
            else:
                unresolved.append(
                    "the case scope is genetic and no applicable clause governing genetic result "
                    "communication was retrieved; the physician route is unsourced and the case must "
                    "not close until a person resolves it"
                )
                blocking.append(
                    "genetic route is unsourced: no applicable clause on genetic result communication "
                    "was retrieved in this step"
                )
        else:
            # Applicability check: does a walk-in clause actually cover this case? Retrieved on its
            # own query rather than scratched out of the stage query's top four, which made the
            # answer depend on which stage the case happened to be in.
            walkin_pool = search(
                STAGE_QUERIES["walkin"], jurisdiction=jurisdiction,
                scope="applicable" if filtered else "all", top_k=4, min_score=POLICY_MIN_SCORE,
            )
            walkin_hits = [
                c for c in walkin_pool.chunks
                if c.source_id == "S1" and "walk_in_scope" in (c.topics or [])
            ]
            checked.append(
                "scope check: walk-in clause covers this case"
                if walkin_hits
                else "scope check: no walk-in-scope clause retrieved; scope remains unverified"
            )
            if not walkin_hits:
                unresolved.append("could not establish that the walk-in scope clause covers this result category")
                blocking.append(
                    "scope is unverified: no walk-in-scope clause was retrieved for this result category"
                )

        # --- acknowledgment clock ----------------------------------------
        clock_minutes = profile.get("acknowledgment_clock_minutes")
        if clock_minutes is not None:
            checked.append(
                f"acknowledgment clock {clock_minutes} min taken from the institutional profile "
                f"({profile.get('acknowledgment_clock_basis', 'no basis recorded')})"
            )
            # Explicitly test whether the corpus fixes a clock; it does not.
            clock_hits = [c for c in applicable.chunks if "minute" in c.text.lower() or "hours" in c.text.lower()]
            if not clock_hits:
                unresolved.append(
                    "no retrieved clause fixes a numeric acknowledgment clock for walk-in results; "
                    "the configured clock is an institutional control, not a statutory deadline"
                )

        # --- fallback authorisation (INV-9) -------------------------------
        # An alternative channel is authorised only by a clause that *declares* it in the corpus,
        # never by words that happen to co-occur. The previous implementation asked whether the text
        # contained "alternative"/"other channel"/"fallback" together with "shall", which is true of
        # a prohibition as well as a permission (audit finding H-1).
        fallback_hits = search(STAGE_QUERIES["fallback"], jurisdiction=jurisdiction, scope="applicable",
                               top_k=5, min_score=POLICY_MIN_SCORE)
        fallback_chunks = [c for c in fallback_hits.chunks if getattr(c, "authorises_fallback", False)]
        fallback_authorised = bool(fallback_chunks)
        checked.append(
            f"fallback check: {len(fallback_chunks)} applicable clause(s) declare an authorisation for an "
            "alternative channel"
            if fallback_authorised
            else "fallback check: no applicable clause declares an authorisation for an alternative "
                 "channel; absence of a prohibition is not permission"
        )

        # --- status -------------------------------------------------------
        # A physician-addressed message is a permitted path even though the direct-to-patient path is
        # closed: the prohibition is about *who receives the result*, not about sending at all.
        if scope_permitted is False and recipient != "PHYSICIAN":
            status = AssessmentStatus.REQUIRES_HUMAN
            action = RecommendedAction.ESCALATE_HUMAN
        elif not applicable.chunks:
            status = AssessmentStatus.HOLD_FOR_EVIDENCE
            action = RecommendedAction.AWAIT_EVIDENCE
        else:
            status = AssessmentStatus.OK
            action = RecommendedAction.SEND_PRIMARY

        comparator_note = (
            f"{len(comparators.chunks)} out-of-jurisdiction document(s) scored highly on relevance and were "
            "deliberately excluded from the governing rule set."
            if comparators.chunks
            else "no out-of-jurisdiction document competed for the governing rule."
        )

        return AgentAssessment(
            agent_id=self.agent_id,
            case_id=view.get("case_id", "unknown"),
            assessment_status=status,
            recommended_action=action,
            applicable_sources=sources,
            conditions_checked=checked,
            conditions_unresolved=unresolved,
            confidence=support_score([c.model_dump() for c in applicable.chunks]),
            # A blocking condition means a person must look, whatever the status says.
            requires_human_review=bool(blocking) or status != AssessmentStatus.OK,
            concise_rationale=(
                f"Applicable instrument(s) for {jurisdiction} retrieved and classified. {comparator_note} "
                + ("Unresolved: " + "; ".join(unresolved[:2]) if unresolved else "")
            ),
            data={
                "scope_permitted": scope_permitted,
                "recipient": recipient,
                "recipient_basis": (
                    {
                        "chunk_id": physician_route.chunk_id,
                        "source_id": physician_route.source_id,
                        "section": physician_route.section_id,
                        "page": physician_route.page_start,
                        "declared_field": "routes_to_physician",
                    }
                    if physician_route is not None
                    else None
                ),
                "fallback_authorised": fallback_authorised,
                "fallback_evidence_refs": [f"{c.source_id} {c.section_id}" for c in fallback_chunks],
                # A token the gate can require, so that a future agent cannot authorise a fallback
                # merely by setting the boolean above.
                "fallback_authorisation_basis": "DECLARED_EXCERPT_FIELD" if fallback_authorised else None,
                "comparators_retrieved": [
                    {"source_id": c.source_id, "section": c.section_id, "jurisdiction": c.jurisdiction}
                    for c in comparators.chunks
                ],
                "confidence_basis": "BM25 support score heuristic, not a calibrated probability",
                # Evidence failures block closure; open research questions (for example, that the
                # corpus fixes no numeric acknowledgment clock) do not.
                "blocking_conditions": list(blocking),
            },
            context_scope=list(self.allowed_fields),
        )
