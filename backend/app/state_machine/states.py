"""Communication state model for ResultRelay.

The states below deliberately separate four things that are routinely conflated in
healthcare messaging products:

  1. what the laboratory produced          (RESULT_*)
  2. what the sender asked the network to do (TRANSMISSION_*)
  3. what the network observed             (TRANSPORT_ACCEPTED / DELIVERY_* / *_UNKNOWN)
  4. what a human did                      (CLINICAL_ACKNOWLEDGMENT_CONFIRMED / DOCUMENTED)

No state in category 2 or 3 implies a state in category 4. This is enforced in
``transitions.py`` and asserted in ``backend/tests/test_state_machine.py``.
"""

from __future__ import annotations

from enum import Enum


class CaseState(str, Enum):
    # --- laboratory-record states -------------------------------------------
    RESULT_DRAFT = "RESULT_DRAFT"
    RESULT_FINALIZED = "RESULT_FINALIZED"

    # --- sender-side intent --------------------------------------------------
    TRANSMISSION_QUEUED = "TRANSMISSION_QUEUED"
    TRANSMISSION_ATTEMPTED = "TRANSMISSION_ATTEMPTED"

    # --- network-observed states --------------------------------------------
    TRANSPORT_ACCEPTED = "TRANSPORT_ACCEPTED"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    DELIVERY_STATE_UNKNOWN = "DELIVERY_STATE_UNKNOWN"

    # --- human-observed states ----------------------------------------------
    CLINICAL_ACKNOWLEDGMENT_CONFIRMED = "CLINICAL_ACKNOWLEDGMENT_CONFIRMED"
    COMMUNICATION_DOCUMENTED = "COMMUNICATION_DOCUMENTED"

    # --- workflow-control states --------------------------------------------
    RETRY_PENDING = "RETRY_PENDING"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    ESCALATION_IN_REVIEW = "ESCALATION_IN_REVIEW"
    CORRECTION_PENDING = "CORRECTION_PENDING"

    # --- corrected-result states --------------------------------------------
    CORRECTED_RESULT_FINALIZED = "CORRECTED_RESULT_FINALIZED"
    CORRECTED_RESULT_DELIVERY_PENDING = "CORRECTED_RESULT_DELIVERY_PENDING"
    CORRECTED_RESULT_ACKNOWLEDGED = "CORRECTED_RESULT_ACKNOWLEDGED"

    # --- terminal record states ---------------------------------------------
    SUPERSEDED = "SUPERSEDED"


#: States from which no further communication action may be taken without a human.
TERMINAL_STATES: frozenset[CaseState] = frozenset(
    {CaseState.CORRECTED_RESULT_ACKNOWLEDGED, CaseState.SUPERSEDED}
)

#: States in which the workflow is *not* allowed to be reported as "complete".
#: Used by invariant INV-10.
INCOMPLETE_CONTROL_STATES: frozenset[CaseState] = frozenset(
    {
        CaseState.DELIVERY_STATE_UNKNOWN,
        CaseState.RETRY_PENDING,
        CaseState.ESCALATION_REQUIRED,
        CaseState.ESCALATION_IN_REVIEW,
        CaseState.CORRECTION_PENDING,
        CaseState.CORRECTED_RESULT_DELIVERY_PENDING,
    }
)

#: Human-readable descriptions surfaced in the UI so evaluators never have to guess
#: what a badge means.
STATE_DESCRIPTIONS: dict[CaseState, str] = {
    CaseState.RESULT_DRAFT: "Result exists but is not finalized; it must not be communicated.",
    CaseState.RESULT_FINALIZED: "Result finalized and released by the laboratory. Nothing sent yet.",
    CaseState.TRANSMISSION_QUEUED: "A send is queued locally. Queuing is not sending.",
    CaseState.TRANSMISSION_ATTEMPTED: "A send request left ResultRelay. Outcome not yet observed.",
    CaseState.TRANSPORT_ACCEPTED: "The transport provider accepted the message. This does not mean it reached the endpoint.",
    CaseState.DELIVERY_CONFIRMED: "The endpoint returned a delivery receipt. A human has still not acknowledged anything.",
    CaseState.DELIVERY_FAILED: "The transport reported a definite delivery failure.",
    CaseState.DELIVERY_STATE_UNKNOWN: "Outcome not established. Neither success nor failure may be assumed.",
    CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED: "A named human acknowledged the specific result revision in view.",
    CaseState.COMMUNICATION_DOCUMENTED: "The configured acknowledgement + documentation conditions for this revision are met.",
    CaseState.RETRY_PENDING: "A retry is permitted only after the prior attempt has been reconciled.",
    CaseState.ESCALATION_REQUIRED: "Deterministic gate routed the case to a human; no automated send is authorised.",
    CaseState.ESCALATION_IN_REVIEW: "A named reviewer has the case open.",
    CaseState.CORRECTION_PENDING: "A result revision changed; messages bound to the old revision are stale.",
    CaseState.CORRECTED_RESULT_FINALIZED: "Corrected revision is final and linked to its predecessor.",
    CaseState.CORRECTED_RESULT_DELIVERY_PENDING: "Corrected revision still needs its own communication workflow.",
    CaseState.CORRECTED_RESULT_ACKNOWLEDGED: "A human acknowledged the corrected revision specifically.",
    CaseState.SUPERSEDED: "An earlier revision retained for history but no longer current.",
}


def is_complete(state: CaseState) -> bool:
    """Only these states may be presented to an evaluator as 'workflow complete'."""
    return state in {
        CaseState.COMMUNICATION_DOCUMENTED,
        CaseState.CORRECTED_RESULT_ACKNOWLEDGED,
    }
