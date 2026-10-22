"""Deterministic transition table and guard conditions.

Design rules honoured here:

* The table is *data*, reviewed independently of the orchestration engine.
* Guards are pure functions of an explicit context object, so they are unit-testable
  without an HTTP server, a database, or any agent.
* Explicit ``FORBIDDEN`` entries exist for the dangerous conflations named in the
  problem statement. A forbidden pair is rejected even if a permissive rule could
  also match, because forbidden rules are evaluated first.
* Nothing in this module can be influenced by retrieved document text or model output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from app.state_machine.states import CaseState


class EventType(str, Enum):
    RESULT_FINALIZED = "result.finalized"
    RESULT_CORRECTED = "result.corrected"
    TRANSMISSION_REQUESTED = "transmission.requested"
    TRANSPORT_ACCEPTED = "transport.accepted"
    TRANSPORT_TIMEOUT = "transport.timeout"
    TRANSPORT_DELIVERY_RECEIPT = "transport.delivery_receipt"
    TRANSPORT_DELIVERY_FAILED = "transport.delivery_failed"
    TRANSPORT_STATUS_UNKNOWN = "transport.status_unknown"
    RECONCILIATION_RESULT = "reconciliation.result"
    CLINICAL_ACKNOWLEDGMENT = "clinical.acknowledgment"
    PATIENT_CALLBACK_NO_ACCESS = "patient.callback_no_access"
    FALLBACK_CHANNEL_PROPOSED = "channel.fallback_proposed"
    ESCALATION_REQUESTED = "escalation.requested"
    ESCALATION_RESOLVED = "escalation.resolved"
    DOCUMENTATION_RECORDED = "documentation.recorded"
    SUPERSEDE = "result.supersede"
    POLICY_SOURCE_UPDATED = "policy.source_updated"


@dataclass
class Attempt:
    attempt_id: str
    idempotency_key: str
    channel: str
    result_revision_id: str
    transport_accepted: bool = False
    delivery_receipt: bool = False
    #: A delivery *receipt event* has been applied. Distinct from ``delivery_receipt``, which is the
    #: adapter's own belief that the message arrived (the simulator's delivery plan sets it).
    receipt_recorded: bool = False
    last_outcome: str = "UNKNOWN"  # UNKNOWN | ACCEPTED | DELIVERED | FAILED
    reconciled: bool = False
    duplicate_suppressed: bool = False


@dataclass
class Acknowledgment:
    ack_id: str
    result_revision_id: str
    role: str
    actor: str
    channel: str
    identity_verified: bool = True


@dataclass
class MachineContext:
    """Everything a guard is allowed to look at. Nothing else is in scope."""

    case_id: str
    state: CaseState
    current_revision_id: str
    revision_ids: list[str] = field(default_factory=list)
    superseded_revision_ids: list[str] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)
    acknowledgments: list[Acknowledgment] = field(default_factory=list)
    event: dict = field(default_factory=dict)
    #: Institutional profile (facility procedure). Explicitly *not* law.
    profile: dict = field(default_factory=dict)
    #: Structured output of the policy-applicability agent, already validated.
    evidence: dict = field(default_factory=dict)
    documentation_recorded: bool = False
    unresolved_conditions: list[str] = field(default_factory=list)
    case_scope: str = "WALK_IN"  # WALK_IN | GENETIC | OTHER
    #: True when the current revision supersedes an earlier one.
    correction_lineage: bool = False
    open_escalation: dict | None = None

    # -- helpers ---------------------------------------------------------
    def attempt_by_id(self, attempt_id: str | None) -> Attempt | None:
        if not attempt_id:
            return None
        for a in self.attempts:
            if a.attempt_id == attempt_id:
                return a
        return None

    def latest_attempt(self) -> Attempt | None:
        return self.attempts[-1] if self.attempts else None

    def fallback_authorised(self) -> tuple[bool, str]:
        """INV-9: an unavailable channel never authorises an alternative by itself.

        Authorisation must come either from verified evidence classified as binding
        for this jurisdiction, or from an explicitly recorded institutional procedure.
        """
        ev = self.evidence or {}
        # The boolean alone is not enough. It must be accompanied by the refs it rests on *and* the
        # basis token that only a declared excerpt field produces, so that an agent (deterministic or
        # otherwise) cannot manufacture authorisation by setting a flag.
        if (
            ev.get("fallback_authorised") is True
            and ev.get("fallback_evidence_refs")
            and ev.get("fallback_authorisation_basis") == "DECLARED_EXCERPT_FIELD"
        ):
            return True, "authorised by a clause that declares it: " + ", ".join(ev["fallback_evidence_refs"])
        if self.profile.get("fallback_channel_approved") is True:
            ref = self.profile.get("fallback_procedure_ref", "institutional procedure (unreferenced)")
            return True, f"authorised by institutional procedure {ref}"
        return False, "no verified policy evidence or approved institutional procedure authorises an alternative channel"


@dataclass
class TransitionResult:
    status: str  # APPLIED | BLOCKED | NO_RULE
    next_state: CaseState
    reason: str
    invariant: str | None = None
    conditions_checked: list[str] = field(default_factory=list)
    requires_human: bool = False
    requires_approval: bool = False
    audit_event: str = "state.transition.rejected"
    policy_ref: str | None = None

    @property
    def applied(self) -> bool:
        return self.status == "APPLIED"


Guard = Callable[[MachineContext], tuple[bool, str]]


@dataclass
class TransitionRule:
    from_states: tuple[CaseState, ...]
    event: EventType
    to_state: CaseState
    guard: Guard
    description: str
    policy_ref: str | None = None
    requires_human: bool = False
    requires_approval: bool = False
    audit_event: str = "state.transition"


@dataclass
class ForbiddenRule:
    from_states: tuple[CaseState, ...]
    event: EventType
    invariant: str
    reason: str


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def _ok(msg: str) -> tuple[bool, str]:
    return True, msg


def _no(msg: str) -> tuple[bool, str]:
    return False, msg


def g_result_current(ctx: MachineContext) -> tuple[bool, str]:
    rev = ctx.event.get("result_revision_id")
    if not rev:
        return _no("event does not identify a result revision")
    if rev != ctx.current_revision_id:
        return _no(
            f"event refers to revision {rev} but the current revision is {ctx.current_revision_id}; "
            "a stale-revision event may not advance the current case"
        )
    return _ok("event revision matches current revision")


def g_transmission_preconditions(ctx: MachineContext) -> tuple[bool, str]:
    # Scope applicability is an *evidence* question answered by the policy agent; the state machine
    # only enforces the answer it is given. (A hardcoded jurisdiction rule here would silently make
    # every baseline compliant and would misrepresent what a static rule set can know.)
    if ctx.evidence.get("scope_permitted") is False:
        return _no("policy assessment prohibits this communication path for this case scope")
    if not ctx.profile.get("direct_patient_communication_enabled", False):
        return _no("institutional profile does not enable direct patient communication")
    return _ok("result finalized, scope permitted, institutional profile enables direct communication")


def g_receipt_matches_attempt(ctx: MachineContext) -> tuple[bool, str]:
    attempt_id = ctx.event.get("attempt_id")
    attempt = ctx.attempt_by_id(attempt_id)
    if attempt is None:
        return _no(
            "delivery receipt does not reference a known attempt id; an unmatched receipt cannot "
            "confirm delivery of this case (INV-3)"
        )
    if attempt.result_revision_id and ctx.current_revision_id and attempt.result_revision_id != ctx.current_revision_id:
        return _no(
            f"receipt belongs to attempt {attempt_id} for revision {attempt.result_revision_id}, but the "
            f"current revision is {ctx.current_revision_id}; a receipt for an earlier revision cannot "
            "confirm delivery of the current one (INV-6/INV-8)"
        )
    via_reconciliation = bool(ctx.event.get("reconciliation"))
    # The event payload cannot assert its own novelty: the attempt's stored state decides whether
    # this is a first receipt or a repeat. (Audit finding H-2.)
    if attempt.receipt_recorded and not via_reconciliation:
        return _no("duplicate receipt for an attempt already marked delivered (INV-5 idempotency)")
    if via_reconciliation and not attempt.reconciled:
        return _no("reconciliation outcome reported before the reconciliation was recorded")
    return _ok(f"receipt matches attempt {attempt_id}")


def g_ack_matches_current_revision(ctx: MachineContext) -> tuple[bool, str]:
    rev = ctx.event.get("result_revision_id")
    if rev != ctx.current_revision_id:
        return _no(
            f"acknowledgment is for revision {rev}, current revision is {ctx.current_revision_id}; "
            "an acknowledgment of an earlier revision does not satisfy the requirement for this "
            "revision (INV-8)"
        )
    if ctx.event.get("identity_verified") is False:
        return _no("acknowledgment identity is not verified; a contact match alone is not proof of identity")
    return _ok("acknowledgment revision and identity are consistent")


def g_not_a_correction(ctx: MachineContext) -> tuple[bool, str]:
    if ctx.correction_lineage:
        return _no("the current revision is a correction; it must follow the corrected-result acknowledgment path, not the original one")
    return _ok("current revision is not a correction")


def g_is_a_correction(ctx: MachineContext) -> tuple[bool, str]:
    if not ctx.correction_lineage:
        return _no("the current revision is not a correction")
    return _ok("current revision supersedes an earlier revision")


def g_ack_requires_prior_delivery(ctx: MachineContext) -> tuple[bool, str]:
    delivered = any(a.delivery_receipt for a in ctx.attempts)
    undocumented = ctx.event.get("observed_channel") == "TELEPHONE_WITH_CONTEMPORANEOUS_RECORD"
    if not delivered and not undocumented:
        return _no(
            "no delivery receipt exists and the acknowledgment was not captured through a documented "
            "contemporaneous channel; acknowledgment provenance is unresolved"
        )
    return _ok("acknowledgment provenance is established")


def g_retry_reconciled(ctx: MachineContext) -> tuple[bool, str]:
    attempt = ctx.attempt_by_id(ctx.event.get("attempt_id")) or ctx.latest_attempt()
    if attempt is None:
        return _no("no prior attempt to reconcile")
    if not attempt.reconciled:
        return _no(
            "prior attempt has not been reconciled against the transport ledger; a retry before "
            "reconciliation risks a duplicate message (INV-4)"
        )
    if not ctx.profile.get("retry_enabled", False):
        return _no("institutional profile disables automated retry")
    max_retries = int(ctx.profile.get("max_retries", 1))
    if len(ctx.attempts) > max_retries:
        return _no(f"attempt count exceeds the configured maximum of {max_retries}; escalation is the only permitted path")
    return _ok("prior attempt reconciled and retry budget available")


def g_correction_reference(ctx: MachineContext) -> tuple[bool, str]:
    prev = ctx.event.get("supersedes_revision_id")
    if not prev:
        return _no("corrected result does not reference the revision it supersedes (INV-6)")
    if prev not in ctx.revision_ids:
        return _no(f"corrected result references unknown revision {prev}")
    return _ok(f"corrected revision supersedes {prev}")


def g_fallback_authorised(ctx: MachineContext) -> tuple[bool, str]:
    return ctx.fallback_authorised()


def g_documentation_complete(ctx: MachineContext) -> tuple[bool, str]:
    if ctx.unresolved_conditions:
        return _no(
            "workflow cannot be closed while conditions remain unresolved: "
            + "; ".join(ctx.unresolved_conditions)
            + " (INV-10)"
        )
    if not any(a.result_revision_id == ctx.current_revision_id for a in ctx.acknowledgments):
        return _no("no acknowledgment exists for the current revision")
    if not ctx.documentation_recorded:
        return _no("no communication record has been recorded (DHA ST-28 §11.1.3 condition not met in-workflow)")
    return _ok("acknowledgment and communication record both present")


def g_always(ctx: MachineContext) -> tuple[bool, str]:
    return _ok("no additional precondition")


def g_escalation_target_exists(ctx: MachineContext) -> tuple[bool, str]:
    if not ctx.profile.get("escalation_role"):
        return _no("no responsible role configured in the institutional profile")
    return _ok(f"escalation role {ctx.profile['escalation_role']} is configured")


# ---------------------------------------------------------------------------
# Forbidden transitions (evaluated first; these encode the core invariants)
# ---------------------------------------------------------------------------

#: State-specific forbidden pairs. These block regardless of any permissive rule.
FORBIDDEN: tuple[ForbiddenRule, ...] = (
    ForbiddenRule(
        from_states=(CaseState.TRANSPORT_ACCEPTED, CaseState.DELIVERY_STATE_UNKNOWN),
        event=EventType.CLINICAL_ACKNOWLEDGMENT,
        invariant="INV-8",
        reason=(
            "an acknowledgment arriving while delivery is unconfirmed cannot be bound to a specific "
            "revision with provenance; it must be reconciled by a human before it closes the loop"
        ),
    ),
    ForbiddenRule(
        from_states=(CaseState.DELIVERY_STATE_UNKNOWN,),
        event=EventType.TRANSMISSION_REQUESTED,
        invariant="INV-4",
        reason=(
            "a new transmission may not be initiated from an unknown outcome state before the prior "
            "attempt has been reconciled; doing so risks an uncontrolled duplicate"
        ),
    ),
)


@dataclass
class ConflationRule:
    """A (trigger event -> resulting state) combination that must never be reachable.

    This is the structural defence behind INV-1 and INV-2: even if a future edit added a
    transition rule that mapped a transport observation onto a human-completion state, the
    combination check would still reject it.
    """

    event: EventType
    forbids_states: tuple[CaseState, ...]
    invariant: str
    reason: str


_HUMAN_COMPLETION = (
    CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED,
    CaseState.COMMUNICATION_DOCUMENTED,
    CaseState.CORRECTED_RESULT_ACKNOWLEDGED,
)

CONFLATIONS: tuple[ConflationRule, ...] = (
    ConflationRule(
        event=EventType.TRANSPORT_ACCEPTED,
        forbids_states=(CaseState.DELIVERY_CONFIRMED,) + _HUMAN_COMPLETION,
        invariant="INV-1/INV-2",
        reason=(
            "provider acceptance may only ever produce TRANSPORT_ACCEPTED. It is neither endpoint "
            "delivery nor human acknowledgment."
        ),
    ),
    ConflationRule(
        event=EventType.TRANSPORT_DELIVERY_RECEIPT,
        forbids_states=_HUMAN_COMPLETION,
        invariant="INV-2",
        reason="an endpoint receipt proves a mailbox received bytes; it does not prove a human read or understood anything",
    ),
    ConflationRule(
        event=EventType.TRANSMISSION_REQUESTED,
        forbids_states=(CaseState.DELIVERY_CONFIRMED,) + _HUMAN_COMPLETION,
        invariant="INV-1",
        reason="initiating a transmission cannot itself establish delivery or acknowledgment",
    ),
    ConflationRule(
        event=EventType.TRANSPORT_TIMEOUT,
        forbids_states=(CaseState.DELIVERY_CONFIRMED, CaseState.DELIVERY_FAILED) + _HUMAN_COMPLETION,
        invariant="INV-3",
        reason="a timeout is an absence of information; it may not be resolved into success or failure",
    ),
    ConflationRule(
        event=EventType.CLINICAL_ACKNOWLEDGMENT,
        forbids_states=(CaseState.COMMUNICATION_DOCUMENTED,),
        invariant="INV-10",
        reason="an acknowledgment alone does not satisfy the communication-record condition of the configured workflow",
    ),
)


# ---------------------------------------------------------------------------
# Transition table
# ---------------------------------------------------------------------------

TRANSITIONS: tuple[TransitionRule, ...] = (
    # --- laboratory lifecycle -------------------------------------------
    TransitionRule(
        (CaseState.RESULT_DRAFT,),
        EventType.RESULT_FINALIZED,
        CaseState.RESULT_FINALIZED,
        g_result_current,
        "A finalized result becomes communication-eligible; nothing is sent automatically.",
        policy_ref="S1 §11.1.1",
    ),
    TransitionRule(
        (CaseState.RESULT_FINALIZED,),
        EventType.TRANSMISSION_REQUESTED,
        CaseState.TRANSMISSION_QUEUED,
        g_transmission_preconditions,
        "Sender queues a communication task. Queuing is not sending.",
        policy_ref="S1 §11.1.1; P1 institutional profile",
    ),
    TransitionRule(
        (CaseState.TRANSMISSION_QUEUED,),
        EventType.TRANSMISSION_REQUESTED,
        CaseState.TRANSMISSION_ATTEMPTED,
        g_transmission_preconditions,
        "Queued task is released to the transport adapter.",
        policy_ref="S1 §11.1.1",
    ),
    # --- network observation --------------------------------------------
    TransitionRule(
        (CaseState.TRANSMISSION_ATTEMPTED,),
        EventType.TRANSPORT_ACCEPTED,
        CaseState.TRANSPORT_ACCEPTED,
        g_always,
        "Provider accepted the message. Delivery is NOT established.",
        policy_ref="G2 2.1 (comparator); INV-1",
    ),
    TransitionRule(
        (CaseState.TRANSMISSION_ATTEMPTED, CaseState.TRANSPORT_ACCEPTED),
        EventType.TRANSPORT_TIMEOUT,
        CaseState.DELIVERY_STATE_UNKNOWN,
        g_always,
        "A timeout is an absence of information, not a failure. The case becomes explicitly uncertain.",
        policy_ref="INV-3",
    ),
    TransitionRule(
        (CaseState.TRANSMISSION_ATTEMPTED, CaseState.TRANSPORT_ACCEPTED),
        EventType.TRANSPORT_STATUS_UNKNOWN,
        CaseState.DELIVERY_STATE_UNKNOWN,
        g_always,
        "Provider reports it cannot determine outcome. Explicit unknown.",
        policy_ref="INV-3",
    ),
    TransitionRule(
        (CaseState.TRANSMISSION_ATTEMPTED, CaseState.TRANSPORT_ACCEPTED),
        EventType.TRANSPORT_DELIVERY_RECEIPT,
        CaseState.DELIVERY_CONFIRMED,
        g_receipt_matches_attempt,
        "Endpoint delivery receipt matched to a known attempt id. Still not acknowledgment.",
        policy_ref="INV-1; INV-3",
    ),
    TransitionRule(
        (CaseState.TRANSMISSION_ATTEMPTED, CaseState.TRANSPORT_ACCEPTED),
        EventType.TRANSPORT_DELIVERY_FAILED,
        CaseState.DELIVERY_FAILED,
        g_always,
        "Definite transport-level failure permits (but does not force) a retry decision.",
    ),
    # --- reconciliation --------------------------------------------------
    TransitionRule(
        (CaseState.DELIVERY_STATE_UNKNOWN,),
        EventType.RECONCILIATION_RESULT,
        CaseState.RETRY_PENDING,
        g_retry_reconciled,
        "Reconciled unknown outcome may open a retry window within the configured budget.",
        policy_ref="INV-4; P1 institutional profile",
    ),
    TransitionRule(
        (CaseState.DELIVERY_STATE_UNKNOWN, CaseState.DELIVERY_FAILED),
        EventType.RECONCILIATION_RESULT,
        CaseState.DELIVERY_CONFIRMED,
        g_receipt_matches_attempt,
        "Reconciliation may resolve uncertainty only by producing a matched receipt.",
        policy_ref="INV-3",
    ),
    TransitionRule(
        (CaseState.DELIVERY_STATE_UNKNOWN,),
        EventType.TRANSPORT_DELIVERY_RECEIPT,
        CaseState.DELIVERY_CONFIRMED,
        g_receipt_matches_attempt,
        "A late receipt that matches a known attempt resolves uncertainty: unknown becomes delivered, "
        "never assumed.",
        policy_ref="INV-3",
    ),
    TransitionRule(
        (CaseState.RETRY_PENDING,),
        EventType.TRANSMISSION_REQUESTED,
        CaseState.TRANSMISSION_ATTEMPTED,
        g_retry_reconciled,
        "Retry released with a new idempotency key after reconciliation.",
        policy_ref="INV-4 / INV-5",
    ),
    # --- human acknowledgment -------------------------------------------
    TransitionRule(
        (CaseState.DELIVERY_CONFIRMED, CaseState.TRANSPORT_ACCEPTED),
        EventType.CLINICAL_ACKNOWLEDGMENT,
        CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED,
        lambda ctx: _combine(
            g_ack_matches_current_revision(ctx),
            g_ack_requires_prior_delivery(ctx),
            g_not_a_correction(ctx),
        ),
        "A named human acknowledged the current revision with established provenance.",
        policy_ref="P1 institutional profile (acknowledgment requirement); G2 2.1 (comparator)",
        requires_human=True,
    ),
    TransitionRule(
        (CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED,),
        EventType.DOCUMENTATION_RECORDED,
        CaseState.COMMUNICATION_DOCUMENTED,
        g_documentation_complete,
        "Communication record captured; the configured workflow is complete for this revision.",
        policy_ref="S1 §11.1.3",
        requires_human=True,
    ),
    # --- corrections -----------------------------------------------------
    TransitionRule(
        (CaseState.CORRECTED_RESULT_FINALIZED,),
        EventType.RESULT_CORRECTED,
        CaseState.CORRECTION_PENDING,
        g_correction_reference,
        "A newer revision supersedes the communicated one; bound messages become stale.",
        policy_ref="S1 §9.1.5(g); S1 §13.4 not applicable",
    ),
    TransitionRule(
        (CaseState.RESULT_FINALIZED, CaseState.TRANSMISSION_QUEUED, CaseState.TRANSMISSION_ATTEMPTED,
         CaseState.TRANSPORT_ACCEPTED, CaseState.DELIVERY_CONFIRMED,
         CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED, CaseState.COMMUNICATION_DOCUMENTED,
         CaseState.DELIVERY_STATE_UNKNOWN, CaseState.RETRY_PENDING, CaseState.DELIVERY_FAILED),
        EventType.RESULT_CORRECTED,
        CaseState.CORRECTION_PENDING,
        g_correction_reference,
        "Correction received while a communication is in flight: pending messages are invalidated.",
        policy_ref="S1 §9.1.5(g)",
    ),
    TransitionRule(
        (CaseState.CORRECTION_PENDING,),
        EventType.TRANSMISSION_REQUESTED,
        CaseState.CORRECTED_RESULT_DELIVERY_PENDING,
        g_transmission_preconditions,
        "A reviewed correction task may open a *new* communication workflow for the corrected revision.",
        policy_ref="S1 §9.1.5(g); P1",
        requires_human=True,
        requires_approval=True,
    ),
    TransitionRule(
        (CaseState.CORRECTED_RESULT_DELIVERY_PENDING,),
        EventType.TRANSMISSION_REQUESTED,
        CaseState.TRANSMISSION_ATTEMPTED,
        g_transmission_preconditions,
        "Release the corrected revision to the transport adapter.",
        policy_ref="S1 §9.1.5(g); S1 §11.1.1",
        requires_approval=True,
    ),
    TransitionRule(
        (CaseState.CORRECTED_RESULT_DELIVERY_PENDING, CaseState.DELIVERY_CONFIRMED),
        EventType.CLINICAL_ACKNOWLEDGMENT,
        CaseState.CORRECTED_RESULT_ACKNOWLEDGED,
        lambda ctx: _combine(
            g_ack_matches_current_revision(ctx),
            g_ack_requires_prior_delivery(ctx),
            g_is_a_correction(ctx),
        ),
        "Corrected revision requires its own acknowledgment; the earlier one does not transfer.",
        policy_ref="INV-8; P1",
        requires_human=True,
    ),
    TransitionRule(
        (CaseState.CORRECTION_PENDING,),
        EventType.SUPERSEDE,
        CaseState.SUPERSEDED,
        g_correction_reference,
        "Superseded revision retained for history; not deleted.",
        policy_ref="S1 §9.1.5(g) - both the original and corrected reports must be maintained",
    ),
    # --- escalation ------------------------------------------------------
    TransitionRule(
        (CaseState.DELIVERY_STATE_UNKNOWN, CaseState.RETRY_PENDING, CaseState.DELIVERY_FAILED,
         CaseState.CORRECTION_PENDING, CaseState.ESCALATION_IN_REVIEW),
        EventType.ESCALATION_REQUESTED,
        CaseState.ESCALATION_REQUIRED,
        g_escalation_target_exists,
        "Deterministic gate routes the case to a named human role.",
        policy_ref="P1 institutional procedure (no universal statutory clock found)",
        requires_human=True,
    ),
    TransitionRule(
        (CaseState.ESCALATION_REQUIRED,),
        EventType.ESCALATION_RESOLVED,
        CaseState.ESCALATION_IN_REVIEW,
        g_always,
        "A named reviewer opens the case; automated actions remain blocked.",
        requires_human=True,
    ),
)

# Transitions that are legal from *any* non-terminal state because they carry information
# forward without resolving anything (they must still be recorded).
INFORMATIONAL_EVENTS: frozenset[EventType] = frozenset(
    {EventType.PATIENT_CALLBACK_NO_ACCESS, EventType.FALLBACK_CHANNEL_PROPOSED, EventType.POLICY_SOURCE_UPDATED}
)


def _combine(*results: tuple[bool, str]) -> tuple[bool, str]:
    reasons = []
    for ok, reason in results:
        if not ok:
            return False, reason
        reasons.append(reason)
    return True, "; ".join(reasons)


def evaluate(ctx: MachineContext, event_type: EventType) -> TransitionResult:
    """Resolve one (state, event) pair against the formal table."""
    # 1. State-specific forbidden pairs win over any permissive rule.
    for rule in FORBIDDEN:
        if ctx.state in rule.from_states and rule.event is event_type:
            return TransitionResult(
                status="BLOCKED",
                next_state=ctx.state,
                reason=rule.reason,
                invariant=rule.invariant,
                audit_event="state.transition.blocked",
            )

    # 2. Conflation check: no transport observation may resolve into human completion.
    forbidden_states: dict[CaseState, ConflationRule] = {}
    for confl in CONFLATIONS:
        if confl.event is event_type:
            for st in confl.forbids_states:
                forbidden_states[st] = confl

    # 2. Informational events are recorded but never move the state.
    if event_type in INFORMATIONAL_EVENTS:
        return TransitionResult(
            status="BLOCKED",
            next_state=ctx.state,
            reason="informational event recorded; it does not by itself change workflow state",
            audit_event="event.informational",
        )

    # 3. First matching, passing rule.
    blocked: list[TransitionResult] = []
    for rule in TRANSITIONS:
        if ctx.state not in rule.from_states or rule.event is not event_type:
            continue
        ok, reason = rule.guard(ctx)
        if ok:
            if rule.to_state in forbidden_states:
                confl = forbidden_states[rule.to_state]
                return TransitionResult(
                    status="BLOCKED",
                    next_state=ctx.state,
                    reason=f"{confl.reason} (invariant {confl.invariant})",
                    invariant=confl.invariant,
                    audit_event="state.transition.blocked",
                )
            return TransitionResult(
                status="APPLIED",
                next_state=rule.to_state,
                reason=f"{rule.description} Precondition: {reason}",
                conditions_checked=[reason],
                requires_human=rule.requires_human,
                requires_approval=rule.requires_approval,
                audit_event=rule.audit_event,
                policy_ref=rule.policy_ref,
            )
        blocked.append(
            TransitionResult(
                status="BLOCKED",
                next_state=ctx.state,
                reason=f"{reason}",
                conditions_checked=[reason],
                requires_human=rule.requires_human,
                audit_event="state.transition.blocked",
                policy_ref=rule.policy_ref,
            )
        )

    if blocked:
        return blocked[0]

    return TransitionResult(
        status="NO_RULE",
        next_state=ctx.state,
        reason=(
            f"event {event_type.value} has no defined transition from state {ctx.state.value}; "
            "the case is left unchanged and the event is recorded for human review"
        ),
        audit_event="state.transition.no_rule",
    )


def transition_table_as_dicts() -> list[dict]:
    """Serialised table for the /api/meta/state-machine endpoint and the docs page."""
    rows: list[dict] = []
    for rule in TRANSITIONS:
        rows.append(
            {
                "kind": "permitted",
                "from_states": [s.value for s in rule.from_states],
                "event": rule.event.value,
                "to_state": rule.to_state.value,
                "description": rule.description,
                "policy_ref": rule.policy_ref,
                "requires_human": rule.requires_human,
            }
        )
    for rule in CONFLATIONS:
        rows.append(
            {
                "kind": "forbidden_combination",
                "from_states": ["*"],
                "event": rule.event.value,
                "to_state": ", ".join(s.value for s in rule.forbids_states),
                "description": rule.reason,
                "invariant": rule.invariant,
                "requires_human": False,
            }
        )
    for rule in FORBIDDEN:
        rows.append(
            {
                "kind": "forbidden",
                "from_states": [s.value for s in rule.from_states],
                "event": rule.event.value,
                "to_state": None,
                "description": rule.reason,
                "invariant": rule.invariant,
                "requires_human": False,
            }
        )
    return rows
