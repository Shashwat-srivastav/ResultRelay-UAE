"""M-5: the residency check was a string test on the hostname, reported as a location finding.

The check itself is kept (it fails closed on everything it cannot name as local or .ae), but it is
no longer allowed to describe a DNS name as a location. Where operator-supplied address evidence
exists, it now outranks the name in both directions.
"""

from __future__ import annotations

import pytest

from app.advisers import residency
from app.advisers.residency import Residency, authorise, classify


@pytest.fixture(autouse=True)
def _no_env(monkeypatch):
    monkeypatch.delenv(residency.RESOLVED_IPS_ENV, raising=False)
    monkeypatch.delenv(residency.IN_COUNTRY_CIDRS_ENV, raising=False)


def test_name_suffix_is_permitted_but_labelled_nominal():
    decision = authorise("https://model.health.ae/v1")
    assert decision.permitted is True
    assert decision.nominal is True
    assert decision.asserted_by == "name-suffix"
    assert "naming signal only" in decision.reason
    assert "not satisfied by a domain suffix" in decision.reason.replace("\n", " ")


def test_loopback_is_nominal_too():
    decision = authorise("http://127.0.0.1:11434/api")
    assert decision.permitted is True
    assert decision.nominal is True
    assert decision.asserted_by == "local-host"


def test_a_foreign_address_behind_an_ae_name_is_refused(monkeypatch):
    monkeypatch.setenv(residency.RESOLVED_IPS_ENV, "203.0.113.9")
    monkeypatch.setenv(residency.IN_COUNTRY_CIDRS_ENV, "10.0.0.0/8,172.16.0.0/12")
    decision = authorise("https://model.health.ae/v1")
    assert decision.permitted is False
    assert decision.residency is Residency.OUT_OF_COUNTRY
    assert decision.asserted_by == "address-out-of-country"
    assert "203.0.113.9" in decision.reason


def test_an_in_country_address_upgrades_the_decision_from_nominal(monkeypatch):
    monkeypatch.setenv(residency.RESOLVED_IPS_ENV, "10.4.2.7")
    monkeypatch.setenv(residency.IN_COUNTRY_CIDRS_ENV, "10.0.0.0/8")
    decision = authorise("https://model.health.ae/v1")
    assert decision.permitted is True
    assert decision.nominal is False
    assert decision.asserted_by == "address-in-country"


def test_unparseable_address_evidence_is_not_treated_as_evidence(monkeypatch):
    monkeypatch.setenv(residency.RESOLVED_IPS_ENV, "not-an-ip")
    monkeypatch.setenv(residency.IN_COUNTRY_CIDRS_ENV, "10.0.0.0/8")
    decision = authorise("https://model.health.ae/v1")
    assert decision.nominal is True
    assert "could not be parsed" in decision.reason


def test_the_name_test_still_cannot_be_fooled_by_a_suffix_lookalike():
    assert classify("https://model.health.ae.evil.example/v1") is Residency.OUT_OF_COUNTRY
    assert classify("https://evil-ae.example/v1") is Residency.OUT_OF_COUNTRY
    assert authorise("https://model.health.ae.evil.example/v1").permitted is False
