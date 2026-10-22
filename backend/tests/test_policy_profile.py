"""Profile values are institutional decisions, and the code must not dress them up as law.

This file exists because the easiest way to make a prototype look compliant is to quietly turn a
design choice into a "requirement". Every assertion below is about that boundary.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from app.policies.profile import DEFAULT_PROFILE, load_profile


def test_every_operational_value_is_labelled_as_a_control_not_a_rule():
    assert DEFAULT_PROFILE["classification"] == "INSTITUTIONAL_PROCEDURE"
    assert "PRODUCT_DESIGN_CONTROL" in DEFAULT_PROFILE["acknowledgment_clock_basis"]
    assert "PRODUCT_DESIGN_CONTROL" in DEFAULT_PROFILE["escalation_basis"]


def test_the_profile_does_not_claim_statutory_status():
    """Where the profile mentions "statutory", it must be to deny having one."""
    blob = " ".join(str(v) for v in DEFAULT_PROFILE.values()).lower()
    assert "required by law" not in blob
    assert "is a statutory" not in blob
    assert "statutory requirement" not in blob
    for occurrence in re.finditer(r"statutory", blob):
        window = blob[max(0, occurrence.start() - 24): occurrence.start()]
        assert "not a" in window or "no " in window, blob[occurrence.start() - 40: occurrence.start() + 20]


def test_clocks_are_declared_without_a_legal_basis():
    assert DEFAULT_PROFILE["acknowledgment_clock_minutes"] > 0
    assert DEFAULT_PROFILE["retry_after_minutes"] > 0
    assert DEFAULT_PROFILE["max_retries"] >= 1
    assert "no retrieved source" in DEFAULT_PROFILE["acknowledgment_clock_basis"]


def test_fallback_is_not_authorised_by_default():
    assert DEFAULT_PROFILE["fallback_channel_approved"] is False
    assert DEFAULT_PROFILE["fallback_procedure_ref"] is None
    # The channel may be named as a *candidate*, which is different from being authorised.
    assert DEFAULT_PROFILE["fallback_channel_id"]


def test_prohibited_content_covers_interpretation_and_advice():
    prohibited = set(DEFAULT_PROFILE["prohibited_content"])
    assert {"diagnosis", "treatment_advice", "result_interpretation"}.issubset(prohibited)


def test_overrides_do_not_mutate_the_default():
    before = dict(DEFAULT_PROFILE)
    altered = load_profile({"jurisdiction": "AE-AZ"})
    assert altered["jurisdiction"] == "AE-AZ"
    assert DEFAULT_PROFILE == before


def test_the_gap_register_records_that_no_clock_was_found(repo_root: Path):
    rows = list(csv.DictReader((repo_root / "knowledge_base" / "gap_register.csv").open(encoding="utf-8")))
    assert rows
    clock_gaps = [
        r for r in rows
        if "clock" in (r.get("question", "") + r.get("description", "") + r.get("gap", "")).lower()
        or "timeframe" in (r.get("question", "") + r.get("description", "")).lower()
    ]
    assert clock_gaps, "the absence of a statutory clock must be recorded as a gap"


def test_profile_channels_match_the_declared_institutional_channels():
    ids = {c["channel_id"] for c in DEFAULT_PROFILE["channels"]}
    assert {"SMS-PATIENT", "PORTAL-PATIENT", "PHONE-CALL"} == ids
    assert sum(1 for c in DEFAULT_PROFILE["channels"] if c["primary"]) == 1


@pytest.mark.parametrize("key", ["acknowledgment_clock_minutes", "retry_after_minutes", "escalation_after_minutes"])
def test_timers_are_integers_within_a_sane_range(key):
    value = DEFAULT_PROFILE[key]
    assert isinstance(value, int)
    assert 1 <= value <= 24 * 60
