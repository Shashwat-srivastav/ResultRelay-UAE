"""The deterministic gate.

No model output reaches an action without passing through this module. The gate:

1. converts a *proposal* into the event the state machine understands;
2. asks the state machine (``transitions.evaluate``) whether that event may move the case;
3. applies the cross-cutting invariants that are not expressible as a single transition;
4. records what it refused and why.

The gate never reads the free-text rationale of an agent. It reads structured fields.

The same is true of the advisory layer. ``enforce`` accepts an optional
:class:`~app.advisers.base.AdvisoryRecord` and attaches it to the decision *after* the decision is
computed, so an adviser can be inspected, scored and disagreed with but cannot influence the
outcome. The wrapper at the bottom of this module is the only place the two meet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.advisers.base import AdvisoryRecord
from app.models.schemas import AgentAssessment, GateDecision, RecommendedAction
from app.state_machine.states import CaseState
from app.state_machine.transitions import EventType, MachineContext, evaluate

#: Proposal -> state-machine event. ``None`` means the proposal has no state-machine effect.
ACTION_TO_EVENT: dict[RecommendedAction, EventType | None] = {
    RecommendedAction.SEND_PRIMARY: EventType.TRANSMISSION_REQUESTED,
    RecommendedAction.RETRY_SAME_CHANNEL: EventType.TRANSMISSION_REQUESTED,
    RecommendedAction.RECONCILE_ATTEMPT: EventType.RECONCILIATION_RESULT,
    RecommendedAction.ESCALATE_HUMAN: EventType.ESCALATION_REQUESTED,
    RecommendedAction.RECORD_DOCUMENTATION: EventType.DOCUMENTATION_RECORDED,
    RecommendedAction.PROPOSE_FALLBACK: None,
    RecommendedAction.AWAIT_ACKNOWLEDGMENT: None,
    RecommendedAction.AWAIT_EVIDENCE: None,
    RecommendedAction.OPEN_CORRECTION_TASK: None,
    RecommendedAction.VERIFY_RECIPIENT: None,
    RecommendedAction.NO_ACTION: None,
}

#: Actions that carry operational risk and therefore need an evidence basis.
HIGH_RISK = {
    RecommendedAction.SEND_PRIMARY,
    RecommendedAction.RETRY_SAME_CHANNEL,
    RecommendedAction.PROPOSE_FALLBACK,
    RecommendedAction.RECORD_DOCUMENTATION,
}


@dataclass
class GateConfig:
    """Baseline behaviour switches. The proposed system uses the defaults."""

    enforce_invariants: bool = True
    acknowledgement_scope: str = "revision"  # revision | any
    transport_semantics: str = "strict"  # strict | optimistic
    require_evidence_for_high_risk: bool = True
    block_on_jurisdiction_violation: bool = True


def _proposal_order(action: RecommendedAction) -> int:
    """Safety ordering when agents disagree: the most conservative proposal wins ties."""
    order = {
        RecommendedAction.ESCALATE_HUMAN: 0,
        RecommendedAction.AWAIT_EVIDENCE: 1,
        RecommendedAction.RECONCILE_ATTEMPT: 1,
        RecommendedAction.VERIFY_RECIPIENT: 2,
        RecommendedAction.RECORD_DOCUMENTATION: 2,
        RecommendedAction.AWAIT_ACKNOWLEDGMENT: 3,
        RecommendedAction.OPEN_CORRECTION_TASK: 3,
        RecommendedAction.PROPOSE_FALLBACK: 4,
        RecommendedAction.RETRY_SAME_CHANNEL: 5,
        RecommendedAction.SEND_PRIMARY: 5,

        RecommendedAction.NO_ACTION: 7,
    }
    return order.get(action, 7)


#: The rule by which a contested step is decided. It is a fixed precedence over actions, not over
#: agents, so no agent can win a disagreement by being listed first or by being called last.
RESOLUTION_RULE = (
    "safety-first precedence over proposed actions (escalate > hold for evidence/reconcile > verify/"
    "document > await acknowledgment/correction > fallback > retry/send); ties broken by agent id"
)


def resolve_proposals(
    assessments: list[AgentAssessment],
) -> tuple[RecommendedAction, list[str], dict[str, Any]]:
    """Resolve disagreement deterministically and *record* it.

    The earlier version returned only the winner and a flat trace, so a step on which the agents
    disagreed was indistinguishable in the record from a step on which they agreed. Disagreement is
    the thing the event asks these agents to produce, so it is now a first-class artefact: which
    agents proposed what, which proposals were outvoted, and the rule that decided it.
    """
    proposals = [
        (a.recommended_action, a.agent_id)
        for a in assessments
        if a.recommended_action != RecommendedAction.NO_ACTION
    ]
    if not proposals:
        return RecommendedAction.NO_ACTION, ["no agent proposed an action"], {
            "rule": RESOLUTION_RULE,
            "proposals": [],
            "chosen": RecommendedAction.NO_ACTION.value,
            "dissent": [],
            "conflict": False,
        }
    ranked = sorted(proposals, key=lambda p: (_proposal_order(p[0]), p[1]))
    chosen = ranked[0][0]
    trace = [f"{aid} -> {act.value}" for act, aid in ranked]
    dissent = [{"agent_id": aid, "proposed": act.value} for act, aid in ranked[1:]]
    distinct = sorted({act.value for act, _ in ranked})
    resolution = {
        "rule": RESOLUTION_RULE,
        "proposals": [{"agent_id": aid, "proposed": act.value} for act, aid in ranked],
        "chosen": chosen.value,
        "dissent": dissent,
        # A "conflict" means at least two different actions were on the table. Two agents proposing
        # the same action is corroboration, not disagreement, and is recorded separately.
        "conflict": len(distinct) > 1,
        "corroboration": len(distinct) == 1 and len(ranked) > 1,
    }
    return chosen, trace, resolution


def _enforce(
    *,
    proposal: RecommendedAction,
    review_revision: str,
    ctx: MachineContext,
    assessments: list[AgentAssessment],
    config: GateConfig | None = None,
    kb_available: bool = True,
    documentation_recorded: bool = False,
    approvals: dict[str, dict] | None = None,
) -> GateDecision:
    cfg = config or GateConfig()
    blocked: list[str] = []
    checked: list[str] = []
    refs: list[str] = []
    invariant: str | None = None

    # --- 1. Evidence basis for high-risk actions --------------------------
    if cfg.require_evidence_for_high_risk and proposal in HIGH_RISK:
        grounded = any(a.applicable_sources for a in assessments if a.agent_id in ("policy_applicability", "lab_workflow"))
        declared_design_control = any(
            "PRODUCT_DESIGN_CONTROL" in (a.data.get("basis", "") if a.data else "") for a in assessments
        )
        if not grounded and not declared_design_control:
            blocked.append("high-risk action proposed without an applicable source citation or declared design control")
            checked.append("evidence basis check failed")
        else:
            checked.append("evidence basis check passed")
    if not kb_available:
        checked.append("knowledge base unavailable in this configuration; evidence basis cannot be established")

    # --- 2. Fallback authorisation (INV-9) --------------------------------
    if proposal == RecommendedAction.PROPOSE_FALLBACK:
        ok, why = ctx.fallback_authorised()
        checked.append(why)
        if not ok:
            invariant = "INV-9"
            blocked.append("alternative channel not authorised by verified policy evidence or approved procedure")
            proposal = RecommendedAction.ESCALATE_HUMAN
            checked.append("proposal downgraded to human escalation")
        else:
            return GateDecision(
                permitted=True,
                enforced_action=RecommendedAction.PROPOSE_FALLBACK,
                reason=f"alternative channel authorised: {why}",
                conditions_checked=checked,
                blocked_actions=blocked,
                policy_refs=refs,
                requires_human=True,
            )

    # --- 2b. Applicability / scope decision from evidence (not from a hardcoded rule) ------
    if (
        proposal in (RecommendedAction.SEND_PRIMARY, RecommendedAction.RETRY_SAME_CHANNEL)
        and ctx.evidence.get("scope_permitted") is False
        and ctx.evidence.get("recipient") == "PHYSICIAN"
    ):
        # The prohibition is on who receives the result, not on communicating at all. The recipient
        # is set by the policy assessor from a retrieved clause that declares it, and the gate can
        # only ever see that structured value - it never parses prose (red-team finding H-4).
        checked.append(
            "scope gate: direct patient communication is prohibited for this scope; the message is "
            "addressed to the referring/treating physician under a retrieved clause that declares "
            "that routing"
        )
    elif proposal in (RecommendedAction.SEND_PRIMARY, RecommendedAction.RETRY_SAME_CHANNEL,
                    RecommendedAction.PROPOSE_FALLBACK) and ctx.evidence.get("scope_permitted") is False:
        blocked.append(
            "the policy assessment establishes that direct patient communication is not permitted for "
            "this result scope; a separate approved protocol is required"
        )
        checked.append("scope gate: blocked on evidence")
        return GateDecision(
            permitted=False,
            enforced_action=RecommendedAction.NO_ACTION,
            reason="blocked: result scope is outside the direct-communication path for this jurisdiction",
            invariant="SCOPE_EXCLUSION",
            conditions_checked=checked,
            blocked_actions=blocked,
            policy_refs=refs,
            requires_human=True,
        )

    # --- 3. Acknowledgment scope -----------------------------------------
    if cfg.acknowledgement_scope == "revision":
        checked.append("acknowledgment must be bound to the current revision (INV-8)")
    else:
        checked.append("legacy mode: any acknowledgment closes the workflow regardless of revision")

    # --- 4. Transport semantics ------------------------------------------
    if cfg.transport_semantics == "strict":
        checked.append("provider acceptance is not delivery; delivery is not acknowledgment (INV-1/INV-2)")
    else:
        checked.append("legacy mode: provider acceptance is treated as successful delivery")

    # --- 5. Read-only actions are always safe to perform ------------------
    if proposal is RecommendedAction.RECONCILE_ATTEMPT:
        return GateDecision(
            permitted=True,
            enforced_action=proposal,
            reason=(
                "reconciliation is a read-only query against the transport ledger; it cannot create a "
                "duplicate message, so it is permitted even while delivery state is unknown"
            ),
            conditions_checked=checked + ["reconciliation is read-only"],
            blocked_actions=blocked,
            policy_refs=refs,
        )

    # --- 6. State machine -------------------------------------------------
    event_type = ACTION_TO_EVENT.get(proposal)
    if event_type is None:
        if proposal in (RecommendedAction.AWAIT_ACKNOWLEDGMENT, RecommendedAction.AWAIT_EVIDENCE,
                        RecommendedAction.OPEN_CORRECTION_TASK, RecommendedAction.VERIFY_RECIPIENT,
                        RecommendedAction.NO_ACTION):
            return GateDecision(
                permitted=True,
                enforced_action=proposal,
                reason="advisory/no-op proposal: no state change is authorised by this step",
                conditions_checked=checked,
                blocked_actions=blocked,
                policy_refs=refs,
                requires_human=proposal == RecommendedAction.ESCALATE_HUMAN,
            )
        return GateDecision(
            permitted=False,
            enforced_action=RecommendedAction.NO_ACTION,
            reason="proposal has no defined state-machine effect",
            conditions_checked=checked,
            blocked_actions=blocked,
        )

    if documentation_recorded:
        # The documentation event *is* the record, so the guard must see it as present.
        ctx = MachineContext(**{**ctx.__dict__, "documentation_recorded": True})
    result = evaluate(ctx, event_type)
    checked.extend(result.conditions_checked)
    if result.policy_ref:
        refs.append(result.policy_ref)

    if not cfg.enforce_invariants and result.status == "BLOCKED":
        # Baseline configurations deliberately run without the invariant layer. The transition
        # still has to be legal for the state, but guards are not enforced.
        return GateDecision(
            permitted=True,
            enforced_action=proposal,
            reason="invariant layer disabled in this configuration; proposal passed through",
            conditions_checked=checked,
            blocked_actions=blocked,
            policy_refs=refs,
        )

    if result.status != "APPLIED":
        blocked.append(result.reason)
        invariant = result.invariant or invariant
        return GateDecision(
            permitted=False,
            enforced_action=RecommendedAction.NO_ACTION,
            reason=f"blocked by deterministic gate: {result.reason}",
            invariant=invariant,
            conditions_checked=checked,
            blocked_actions=blocked,
            policy_refs=refs,
            requires_human=result.requires_human,
        )

    if result.requires_approval and not (approvals or {}).get(proposal.value):
        return GateDecision(
            permitted=False,
            enforced_action=RecommendedAction.NO_ACTION,
            reason=(
                f"withheld pending named human approval: {result.reason} "
                "Superseding an already-communicated result is not an autonomous action."
            ),
            invariant="HUMAN_APPROVAL",
            conditions_checked=checked + ["approval gate: no approval recorded"],
            blocked_actions=blocked + ["approval not recorded"],
            policy_refs=refs,
            requires_human=True,
        )

    return GateDecision(
        permitted=True,
        enforced_action=proposal,
        reason=result.reason,
        invariant=result.invariant,
        conditions_checked=checked,
        blocked_actions=blocked,
        policy_refs=refs,
        requires_human=result.requires_human,
    )


def enforce(
    *,
    proposal: RecommendedAction,
    review_revision: str,
    ctx: MachineContext,
    assessments: list[AgentAssessment],
    config: GateConfig | None = None,
    kb_available: bool = True,
    documentation_recorded: bool = False,
    approvals: dict[str, dict] | None = None,
    advisory: AdvisoryRecord | None = None,
) -> GateDecision:
    """Deterministic decision, with the advisory layer attached afterwards and never before.

    The decision is computed by ``_enforce`` from structured fields only. The advisory record is
    attached afterwards, together with an explicit note when the adviser disagreed with the gate -
    which is the interesting case, because the gate is meant to win.
    """
    decision = _enforce(
        proposal=proposal,
        review_revision=review_revision,
        ctx=ctx,
        assessments=assessments,
        config=config,
        kb_available=kb_available,
        documentation_recorded=documentation_recorded,
        approvals=approvals,
    )
    if advisory is None:
        return decision

    update: dict[str, Any] = {"advisory": advisory.as_dict()}
    checked = list(decision.conditions_checked)
    checked.append(f"adviser status: {advisory.status.value} ({advisory.reason})")
    if advisory.considered and advisory.proposal is not None:
        candidate = advisory.proposal.candidate_action
        if candidate is not decision.enforced_action:
            checked.append(
                f"adviser proposed {candidate.value}; the gate enforced {decision.enforced_action.value} "
                "and did not read the proposal while deciding"
            )
            update["advisory_overruled"] = True
        else:
            checked.append(f"adviser agreed with the gate ({candidate.value}); agreement is not evidence")
    update["conditions_checked"] = checked
    return decision.model_copy(update=update)


def naive_gate(proposal: RecommendedAction, ctx: MachineContext) -> GateDecision:
    """The policy-blind baseline's decision logic, kept intentionally simple and explicit.

    This is a *plausible naive implementation*, not a strawman: it checks only that a result
    exists and that the transport reported something. It does not distinguish acceptance from
    delivery, and it closes the workflow on any acknowledgment.
    """
    attempts = ctx.attempts
    accepted = any(a.transport_accepted for a in attempts)
    delivered = any(a.delivery_receipt for a in attempts)
    acked = bool(ctx.acknowledgments)

    if proposal in (RecommendedAction.SEND_PRIMARY, RecommendedAction.RETRY_SAME_CHANNEL):
        return GateDecision(
            permitted=bool(ctx.current_revision_id),
            enforced_action=proposal,
            reason="result exists; sending is allowed",
            conditions_checked=["result present", "no invariant layer"],
        )
    if proposal == RecommendedAction.RECORD_DOCUMENTATION and (delivered or accepted):
        return GateDecision(
            permitted=True,
            enforced_action=proposal,
            reason="a provider response was observed, so the communication is treated as complete",
            conditions_checked=["provider response observed", "accepted/delivered treated as equivalent"],
        )
    if proposal == RecommendedAction.ESCALATE_HUMAN and not acked:
        return GateDecision(permitted=True, enforced_action=proposal, reason="no acknowledgment yet", requires_human=True)
    return GateDecision(
        permitted=True,
        enforced_action=proposal,
        reason="baseline: proposal accepted without invariant checks",
        conditions_checked=["no invariant layer"],
    )
