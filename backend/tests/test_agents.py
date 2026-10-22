"""What each agent may see, and what it may not claim.

Information asymmetry is a safety property here, not a code-organisation preference: an agent
that cannot see the patient's phone number cannot leak it, and an agent that cannot see the
transport ledger cannot mistake a provider acknowledgment for a delivery receipt.
"""

from __future__ import annotations

import pytest

from app.kb.retriever import all_chunks


@pytest.fixture(scope="module")
def first_step(repo_root):
    from app.orchestration.engine import Orchestrator, build_runtime, load_scenario

    scenario = load_scenario("S1-ambiguous-delivery")
    rt = build_runtime(scenario, "resultrelay", run_id="TEST-AGENTS")
    result = Orchestrator(rt).step(scenario["steps"][0])
    return result, rt


def test_all_five_agents_report_on_the_same_event(first_step):
    result, _ = first_step
    ids = [a["agent_id"] for a in result["agents"]]
    assert ids == [
        "lab_workflow",
        "policy_applicability",
        "network_delivery",
        "escalation_coordinator",
        "audit_governance",
    ]


def test_each_assessment_is_well_formed(first_step):
    result, _ = first_step
    for a in result["agents"]:
        assert 0.0 <= a["confidence"] <= 1.0
        assert a["concise_rationale"]
        assert a["assessment_status"] in {"OK", "HOLD_FOR_EVIDENCE", "REQUIRES_HUMAN", "NOT_APPLICABLE"}
        assert a["mode"] == "DETERMINISTIC"
        assert isinstance(a["requires_human_review"], bool)


def test_context_scopes_are_declared_and_disjoint_where_it_matters(first_step):
    result, _ = first_step
    scopes = {a["agent_id"]: set(a["context_scope"]) for a in result["agents"]}

    # The delivery agent may not see who the patient is; the clinical agent may not see channels.
    assert not {"patient_name", "patient_contact", "patient_identity"} & scopes["network_delivery"]
    assert "attempts" not in scopes["lab_workflow"]
    assert "transport_ledger" not in scopes["escalation_coordinator"]
    assert "assessments" in scopes["audit_governance"]


def test_information_available_records_what_each_agent_actually_received(first_step):
    """The record is of real inputs, so it can be checked for leakage rather than trusted."""
    result, first_rt = first_step
    available = result["information_available"]
    assert set(available) == {"lab_workflow", "policy_applicability", "network_delivery", "escalation_coordinator"}

    # The transport-facing agent is never handed patient identity or clinical interpretation.
    network_keys = set(available["network_delivery"])
    assert not {"patient_name", "patient_contact", "patient_identity", "interpretation"} & network_keys

    # The clinical agent is never handed the transport ledger or channel state.
    lab_keys = set(available["lab_workflow"])
    assert not {"attempts", "channels", "transport_ledger"} & lab_keys

    # Every agent's recorded inputs are JSON-serialisable values, so the record is auditable.
    import json

    json.dumps(available)


def test_citations_resolve_to_indexed_chunks(first_step):
    _, rt = first_step
    known = {(c["source_id"], c["section_id"]): c for c in all_chunks()}
    checked = 0
    for step in rt.steps:
        for agent in step["agents"]:
            for src in agent["applicable_sources"]:
                assert (src["source_id"], src["section"]) in known, f"invented citation {src}"
                assert src["page"] >= 1
                checked += 1
    assert checked > 0, "the policy agent should have cited something on step 1"


def test_a_citation_must_name_a_section_not_just_a_document():
    with pytest.raises(ValueError):
        from app.models.schemas import ClaimClassification, SourceCitation

        SourceCitation(
            source_id="S1", section="", page=40, claim_type=ClaimClassification.BINDING_REQUIREMENT
        )


def test_policy_agent_marks_a_genetic_case_as_scope_excluded(run):
    rt = run("S4-genetic-scope-exclusion", "resultrelay")
    policies = [
        a
        for step in rt.steps
        for a in step["agents"]
        if a["agent_id"] == "policy_applicability"
    ]
    assert policies
    assert all(a["data"].get("scope_permitted") is False for a in policies)


def test_a_configuration_without_a_knowledge_base_has_no_policy_or_audit_agent(run):
    """The baselines are honest about what they lack, rather than pretending to the same checks."""
    rt = run("S1-ambiguous-delivery", "policy_blind")
    ran = {a["agent_id"] for step in rt.steps for a in step["agents"]}
    assert ran == {"lab_workflow", "network_delivery", "escalation_coordinator"}
    assert "policy_applicability" not in ran
    assert "audit_governance" not in ran

    full = run("S1-ambiguous-delivery", "resultrelay")
    full_ran = {a["agent_id"] for step in full.steps for a in step["agents"]}
    assert full_ran == {
        "lab_workflow", "policy_applicability", "network_delivery",
        "escalation_coordinator", "audit_governance",
    }


def test_agents_never_consume_their_own_output(first_step):
    """An agent's own prior assessment must not appear in its input context."""
    result, _ = first_step
    for a in result["agents"]:
        assert a["agent_id"] not in a["context_scope"]
