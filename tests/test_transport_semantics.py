"""H-4: the "optimistic transport" baseline changed a label and no behaviour.

The configuration claimed to model a system that treats provider acceptance as delivery. Before this
fix the only difference was a string in the gate's ``conditions_checked`` list and an audit note, so
the ablation row in the evaluation report was measuring nothing. These tests pin the difference at
the level of the ledger and the state machine, which is where it has to exist to be comparable.

They deliberately do not assert anything about the seven benchmarked scenarios: none of them
distinguishes the two semantics (see the note in evaluation/report.md), and a test that claimed they
did would be false.
"""

from __future__ import annotations

import copy

import pytest

from app.orchestration.engine import load_scenario, run_scenario
from app.state_machine.states import CaseState


def _accepted_without_receipt() -> dict:
    """A case whose provider accepts the message and where no endpoint receipt ever arrives."""
    scenario = copy.deepcopy(load_scenario("S1-ambiguous-delivery"))
    scenario["scenario_id"] = "SYN-TEST-ACCEPTED-NO-RECEIPT"
    scenario["network"]["attempts"] = [{"outcome": "ACCEPTED", "accept_after_minutes": 0.3}]
    scenario["network"]["reconciliations"] = [
        {"attempt_id": None, "result": "STILL_UNKNOWN", "note": "no receipt to reconcile against"}
    ]
    # Keep the send and the patient's report; drop the receipt, acknowledgment and documentation
    # steps, which only exist once a delivery is believed to have happened.
    scenario["steps"] = [s for s in scenario["steps"] if int(s["step"]) <= 5]
    return scenario


def test_strict_semantics_leave_the_delivery_state_unknown():
    rt = run_scenario(_accepted_without_receipt(), "resultrelay")
    assert rt.state is CaseState.TRANSPORT_ACCEPTED
    attempt = rt.network.attempts[-1]
    assert attempt.accepted is True
    assert attempt.delivered is False
    assert not [l for l in rt.network.ledger if l["event"] == "ACCEPTANCE_RECORDED_AS_DELIVERY"]


def test_optimistic_semantics_now_actually_conflate_acceptance_with_delivery():
    rt = run_scenario(_accepted_without_receipt(), "ablate_optimistic_transport")
    attempt = rt.network.attempts[-1]
    assert attempt.delivered is True, "the ablation must reach the ledger, not only the audit log"
    assert [l for l in rt.network.ledger if l["event"] == "ACCEPTANCE_RECORDED_AS_DELIVERY"]
    assert rt.state is not CaseState.TRANSPORT_ACCEPTED
    assert rt.state in {CaseState.DELIVERY_CONFIRMED, CaseState.COMMUNICATION_DOCUMENTED,
                        CaseState.CLINICAL_ACKNOWLEDGMENT_CONFIRMED}, rt.state


def test_the_two_configurations_differ_in_observed_state_not_only_in_a_label():
    strict = run_scenario(_accepted_without_receipt(), "resultrelay")
    optimistic = run_scenario(_accepted_without_receipt(), "ablate_optimistic_transport")
    assert strict.state is not optimistic.state


@pytest.mark.parametrize("name", ["resultrelay", "ablate_optimistic_transport"])
def test_the_reason_is_recorded_either_way(name):
    rt = run_scenario(_accepted_without_receipt(), name)
    notes = [e for e in rt.audit.entries if "conflation" in str(e).lower()]
    if name == "resultrelay":
        assert not notes
    else:
        assert notes, "a configuration that conflates must say so in the audit log"
