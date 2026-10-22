"""The containment wrapper.

Everything an adviser produces passes through here before anything else sees it. The guard:

1. refuses to run at all when the model boundary is closed (the shipped default);
2. applies the Article 13 residency check and refuses an endpoint that is not inside the State
   without a recorded Health Authority resolution;
3. rejects a proposal that cites a chunk id which does not exist, or one whose jurisdiction cannot
   bind the case (an Abu Dhabi clause can inform a Dubai case, never authorise it);
4. stamps whatever survives as ``PRODUCT_DESIGN_CONTROL`` - advisory design opinion, not policy.

It returns an :class:`AdvisoryRecord`, never an action.
"""

from __future__ import annotations

from app.advisers.base import AdvisoryProposal, AdvisoryRecord, AdvisoryStatus, Adviser
from app.advisers.residency import authorise
from app.core.config import settings
from app.kb import retriever
from app.models.schemas import RecommendedAction

_ALLOWED = {a.value for a in RecommendedAction}


def advise(
    *,
    jurisdiction: str,
    situation: str,
    evidence: list[dict],
    adviser: Adviser | None = None,
    endpoint: str | None = None,
    resolution_ref: str | None = None,
    enabled: bool | None = None,
) -> AdvisoryRecord:
    """Produce an advisory record for this situation, or explain why none was produced."""
    on = settings.enable_llm if enabled is None else enabled
    checks: list[str] = []

    if not on or adviser is None:
        return AdvisoryRecord(
            status=AdvisoryStatus.DISABLED,
            mode="DETERMINISTIC",
            reason=(
                "the model boundary is closed (RESULTRELAY_ADVISE is off and no adviser was supplied); "
                "the deterministic agent set produced the proposal. This is the shipped configuration."
            ),
            checks=("adviser boundary: closed",),
        )

    decision = authorise(endpoint, resolution_ref)
    if not decision.permitted:
        return AdvisoryRecord(
            status=AdvisoryStatus.REFUSED_RESIDENCY,
            mode="ADVISORY",
            reason=decision.reason,
            policy_refs=decision.policy_refs,
            residency=decision.residency.value,
            endpoint=endpoint,
            checks=("residency: refused",),
        )
    checks.append(f"residency: {decision.residency.value}")
    checks.append(decision.reason)

    try:
        proposal = adviser.propose(jurisdiction=jurisdiction, situation=situation, evidence=evidence)
    except Exception as exc:  # noqa: BLE001 - an adviser failure must never propagate as an action
        return AdvisoryRecord(
            status=AdvisoryStatus.REJECTED_MALFORMED,
            mode="ADVISORY",
            reason=f"adviser raised {type(exc).__name__}: {exc}. A failure to advise is not authority to act.",
            policy_refs=decision.policy_refs,
            residency=decision.residency.value,
            endpoint=endpoint,
            checks=tuple(checks),
        )

    if not isinstance(proposal, AdvisoryProposal) or proposal.candidate_action.value not in _ALLOWED:
        return AdvisoryRecord(
            status=AdvisoryStatus.REJECTED_MALFORMED,
            mode="ADVISORY",
            reason="adviser returned something that is not a proposal over the known action set",
            policy_refs=decision.policy_refs,
            residency=decision.residency.value,
            endpoint=endpoint,
            checks=tuple(checks),
        )

    index = {c["chunk_id"]: c for c in retriever.all_chunks()}
    missing = [cid for cid in proposal.citation_chunk_ids if cid not in index]
    if missing:
        return AdvisoryRecord(
            status=AdvisoryStatus.REJECTED_UNGROUNDED,
            mode="ADVISORY",
            reason=f"cited chunk id(s) not present in the corpus: {missing}. A citation that cannot be resolved is not evidence.",
            policy_refs=decision.policy_refs,
            residency=decision.residency.value,
            endpoint=endpoint,
            checks=tuple(checks),
        )

    # A citation offered as the basis of a proposal must come from the applicable set, whatever its
    # class. A comparator may inform a human reading, but it may not underwrite an action - the
    # classification alone is not enough, because a downgraded class can always be re-read as
    # persuasive.
    applicable = retriever.applicable_jurisdictions(jurisdiction) or set()
    foreign = [
        cid for cid in proposal.citation_chunk_ids
        if index[cid]["jurisdiction"] not in applicable
    ]
    if foreign:
        return AdvisoryRecord(
            status=AdvisoryStatus.REJECTED_OUT_OF_JURISDICTION,
            mode="ADVISORY",
            reason=(
                f"proposal cites material from {sorted({index[c]['jurisdiction'] for c in foreign})}, "
                f"which cannot underwrite a {jurisdiction} case (applicable set: {sorted(applicable)}): {foreign}. "
                "Comparator material may inform a human, never the basis of a proposal."
            ),
            policy_refs=decision.policy_refs,
            residency=decision.residency.value,
            endpoint=endpoint,
            checks=tuple(checks),
        )

    checks.append("citations resolve to corpus chunks inside the applicable jurisdiction set")
    return AdvisoryRecord(
        status=AdvisoryStatus.ADVISORY_ONLY,
        mode="ADVISORY",
        reason=(
            "recorded as advisory design opinion (PRODUCT_DESIGN_CONTROL). It is not a policy basis, it "
            "cannot authorise a transition, and the gate decision was computed without reading it."
        ),
        proposal=proposal,
        policy_refs=decision.policy_refs,
        residency=decision.residency.value,
        endpoint=endpoint,
        checks=tuple(checks),
    )
