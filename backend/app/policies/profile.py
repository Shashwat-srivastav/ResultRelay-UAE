"""Facility-level configuration.

Everything in this module is an INSTITUTIONAL_PROCEDURE or PRODUCT_DESIGN_CONTROL.
None of it is presented as a statutory obligation. The gap register records which
values no retrieved source fixes (for example the acknowledgment clock).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PROFILE: dict[str, Any] = {
    "profile_id": "P1-WALKIN-DEMO",
    "profile_label": "Synthetic walk-in laboratory profile (demonstration only)",
    "jurisdiction": "AE-DU",
    "facility_type": "DHA-licensed walk-in clinical laboratory (simulated)",
    "classification": "INSTITUTIONAL_PROCEDURE",
    "status": "SYNTHETIC_PENDING_FACILITY_REVIEW",
    # --- operational controls (none of these are asserted to be statutory) ---
    "direct_patient_communication_enabled": True,
    "requires_acknowledgment": True,
    "acknowledgment_clock_minutes": 60,
    "acknowledgment_clock_basis": (
        "PRODUCT_DESIGN_CONTROL: no retrieved source fixes a numeric acknowledgment clock for "
        "walk-in critical results; see gap GR-04."
    ),
    "retry_enabled": True,
    "max_retries": 1,
    "retry_after_minutes": 15,
    "fallback_channel_approved": False,
    "fallback_procedure_ref": None,
    "fallback_channel_id": "PORTAL-PATIENT",
    "escalation_role": "SUPERVISOR",
    "escalation_after_minutes": 60,
    "escalation_basis": (
        "PRODUCT_DESIGN_CONTROL: routed to a named supervisor role; not a statutory deadline."
    ),
    "documentation_required": True,
    "patient_wording_source": "S1 §11.1.2",
    "prohibited_content": [
        "diagnosis",
        "severity_explanation",
        "treatment_advice",
        "result_interpretation",
    ],
    "channels": [
        {"channel_id": "SMS-PATIENT", "kind": "SMS", "endpoint_class": "patient_mobile", "primary": True},
        {"channel_id": "PORTAL-PATIENT", "kind": "PORTAL", "endpoint_class": "patient_portal", "primary": False},
        {"channel_id": "PHONE-CALL", "kind": "VOICE", "endpoint_class": "patient_mobile", "primary": False},
    ],
}


def load_profile(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = copy.deepcopy(DEFAULT_PROFILE)
    if overrides:
        profile.update(overrides)
    return profile


def load_profile_file(path: str | Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return load_profile(data)


#: Patient-facing wording. Derived from S1 §11.1.2 ("direct the patient to seek further
#: medical advice"). The template deliberately contains no interpretation of the result.
PATIENT_MESSAGE_TEMPLATE = (
    "Your laboratory result ({test_name}, report {revision_label}) has been reviewed by the "
    "laboratory. Please seek further medical advice from a licensed physician as soon as possible. "
    "This message does not tell you what the result means and is not a diagnosis."
)

#: Wording used when no verified source supports an alternative channel.
FALLBACK_HOLD_MESSAGE = (
    "Alternative channel withheld: no verified policy evidence or approved institutional procedure "
    "authorises an alternative channel for this case."
)
