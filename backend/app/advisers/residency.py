"""Where may the health data be processed?

Federal Law No. (2) of 2019 (Use of ICT in Health Fields), Article 13:

    "It is not permissible to store, process, generate or transform the health data and information
     outside State -which are related to the health services provided inside State- except in the
     case where a resolution is issued from the Health Authority in coordination with the Ministry."

"Process" is enumerated, so inference itself is covered: an offshore model endpoint processes the
data even when nothing is retained. Article 24 sets the penalty at AED 500,000-700,000.

This module answers a narrow question - is this endpoint inside the State - and refuses to guess.
Anything it cannot classify is treated as outside.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from enum import Enum

#: Country-code suffixes that place a host inside the United Arab Emirates.
IN_COUNTRY_SUFFIXES = (".ae",)

#: Hosts that are unambiguously local: no packet leaves the machine, so no transfer occurs.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}

ART13 = "Federal Law 2/2019 Art. 13"
ART24 = "Federal Law 2/2019 Art. 24"


class Residency(str, Enum):
    IN_COUNTRY = "IN_COUNTRY"
    OUT_OF_COUNTRY = "OUT_OF_COUNTRY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ResidencyDecision:
    residency: Residency
    permitted: bool
    reason: str
    policy_refs: tuple[str, ...]

    @property
    def citation(self) -> str:
        return "; ".join(self.policy_refs)


def classify(endpoint: str | None) -> Residency:
    """Classify an endpoint. Unknown is not a synonym for safe."""
    if not endpoint:
        return Residency.UNKNOWN
    host = (urllib.parse.urlparse(endpoint).hostname or "").lower().strip(".")
    if not host:
        host = endpoint.lower().strip(".")
    if host in LOCAL_HOSTS:
        return Residency.IN_COUNTRY
    if host.endswith(IN_COUNTRY_SUFFIXES):
        return Residency.IN_COUNTRY
    # An IP literal is treated as out of country: there is no way to tell from the address alone,
    # and the consequence of guessing "in country" is the penalty in Art. 24.
    return Residency.OUT_OF_COUNTRY if host else Residency.UNKNOWN


def authorise(endpoint: str | None, resolution_ref: str | None = None) -> ResidencyDecision:
    """Decide whether this endpoint may process health data for a case inside the State.

    A Health Authority resolution is the only route to an out-of-country endpoint (Art. 13), so an
    out-of-country or unknown endpoint is refused unless a resolution reference is supplied *and*
    recorded, which is a deliberate friction: someone has to name the instrument.
    """
    residency = classify(endpoint)
    if residency is Residency.IN_COUNTRY:
        return ResidencyDecision(
            residency=residency,
            permitted=True,
            reason="endpoint resolves inside the State, so Article 13 is not engaged",
            policy_refs=(ART13,),
        )
    if resolution_ref:
        return ResidencyDecision(
            residency=residency,
            permitted=True,
            reason=(
                f"out-of-country processing (status {residency.value}) permitted only on the strength of "
                f"the recorded Health Authority resolution {resolution_ref!r}; the resolution itself is "
                "not verified by this system"
            ),
            policy_refs=(ART13, ART24),
        )
    return ResidencyDecision(
        residency=residency,
        permitted=False,
        reason=(
            f"endpoint status is {residency.value}: Article 13 prohibits storing, processing, generating "
            "or transforming health data outside the State without a Health Authority resolution, and "
            "Article 24 sets the penalty at AED 500,000-700,000. Refused. Note that a local or in-country "
            "endpoint is not thereby endorsed: this checks residency only."
        ),
        policy_refs=(ART13, ART24),
    )
