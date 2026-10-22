"""Where may the health data be processed?

Federal Law No. (2) of 2019 (Use of ICT in Health Fields), Article 13:

    "It is not permissible to store, process, generate or transform the health data and information
     outside State -which are related to the health services provided inside State- except in the
     case where a resolution is issued from the Health Authority in coordination with the Ministry."

"Process" is enumerated, so inference itself is covered: an offshore model endpoint processes the
data even when nothing is retained. Article 24 sets the penalty at AED 500,000-700,000.

This module answers a narrower question than it appears to: **is this endpoint's name inside the
State** and refuses to guess beyond that. A DNS name is not a location. ``model.health.ae`` can
resolve to an address outside the State, or to a third-party edge that stores nothing in the UAE
while processing everything; the suffix is a declaration by the registrant, not an observation.

Two signals are therefore distinguished and reported separately:

* ``nominal`` - the decision rests on the name alone (``.ae`` suffix, or a hostname that cannot
  leave the machine). This is what the shipped configuration can establish offline.
* ``address_checked`` - the operator supplied the resolved addresses *and* the in-country ranges,
  and the address fell inside them. Only this is evidence about where processing happens.

An endpoint with no signal at all is treated as outside. Nothing here is a security control: the
control is network egress, which this code cannot see.
"""

from __future__ import annotations

import ipaddress
import os
import urllib.parse
from dataclasses import dataclass
from enum import Enum

#: Country-code suffixes that place a host inside the United Arab Emirates.
IN_COUNTRY_SUFFIXES = (".ae",)

#: Hosts that are unambiguously local: no packet leaves the machine, so no transfer occurs.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}

#: Optional operator-supplied address evidence. Both must be present for an address check to run;
#: neither is set in the shipped configuration, which is why the default decision is nominal.
RESOLVED_IPS_ENV = "RESULTRELAY_RESIDENCY_RESOLVED_IPS"
IN_COUNTRY_CIDRS_ENV = "RESULTRELAY_RESIDENCY_AE_CIDRS"

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
    #: True when the decision rests on the endpoint's *name* rather than on a resolved address.
    nominal: bool = False
    #: How the decision was reached: "local-host", "name-suffix", "address-in-country",
    #: "address-out-of-country", "no-signal", "resolution".
    asserted_by: str = "no-signal"

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
        # A name under .ae. See the module docstring: this says where the name is registered, not
        # where the bytes are processed.
        return Residency.IN_COUNTRY
    # An IP literal is treated as out of country: there is no way to tell from the address alone,
    # and the consequence of guessing "in country" is the penalty in Art. 24.
    return Residency.OUT_OF_COUNTRY if host else Residency.UNKNOWN


def _address_check() -> tuple[bool | None, str]:
    """Return (in_country, detail) from operator-supplied addresses, or (None, reason)."""
    ips = os.environ.get(RESOLVED_IPS_ENV, "")
    cidrs = os.environ.get(IN_COUNTRY_CIDRS_ENV, "")
    if not ips or not cidrs:
        return None, (
            f"no address evidence supplied ({RESOLVED_IPS_ENV} and {IN_COUNTRY_CIDRS_ENV} are unset), "
            "so no check was made of where the endpoint actually resolves"
        )
    try:
        ranges = [ipaddress.ip_network(c.strip(), strict=False) for c in cidrs.split(",") if c.strip()]
        addresses = [ipaddress.ip_address(i.strip()) for i in ips.split(",") if i.strip()]
    except ValueError as exc:
        return None, f"address evidence could not be parsed ({exc}), so it was not used"
    if not ranges or not addresses:
        return None, "address evidence was empty, so no check was made"
    outside = [str(a) for a in addresses if not any(a in r for r in ranges)]
    if outside:
        return False, f"resolved address(es) {outside} fall outside the supplied in-country ranges"
    return True, f"all resolved addresses {[str(a) for a in addresses]} fall inside the supplied in-country ranges"


def authorise(endpoint: str | None, resolution_ref: str | None = None) -> ResidencyDecision:
    """Decide whether this endpoint may process health data for a case inside the State.

    A Health Authority resolution is the only route to an out-of-country endpoint (Art. 13), so an
    out-of-country or unknown endpoint is refused unless a resolution reference is supplied *and*
    recorded, which is a deliberate friction: someone has to name the instrument.
    """
    residency = classify(endpoint)
    address_in_country, address_detail = _address_check()

    if residency is Residency.IN_COUNTRY and address_in_country is False:
        # The name says one thing and the address another. The address wins.
        return ResidencyDecision(
            residency=Residency.OUT_OF_COUNTRY,
            permitted=False,
            reason=(
                f"the endpoint name is in country but {address_detail}; Article 13 concerns where the data "
                "is processed, not what the host is called. Refused."
            ),
            policy_refs=(ART13, ART24),
            asserted_by="address-out-of-country",
        )

    if residency is Residency.IN_COUNTRY:
        host = (urllib.parse.urlparse(endpoint or "").hostname or "").lower().strip(".") or (endpoint or "").lower().strip(".")
        local = host in LOCAL_HOSTS
        nominal = not (address_in_country is True)
        if local:
            reason = (
                "endpoint is a loopback/host-local address, so no transfer off the machine is implied by "
                "the endpoint itself (the model runtime may still have its own network access)"
            )
        else:
            reason = (
                f"endpoint name {host!r} is registered in country, which is a naming signal only: the same "
                "name can resolve to a server outside the State. Article 13 is not satisfied by a domain "
                "suffix; the control is network egress, which this system does not observe"
            )
        if address_in_country is True:
            reason = f"endpoint name is in country and {address_detail}"
            nominal = False
        elif not local:
            reason = f"{reason}; {address_detail}"
        return ResidencyDecision(
            residency=residency,
            permitted=True,
            reason=reason,
            policy_refs=(ART13,),
            nominal=nominal,
            asserted_by=("local-host" if local else ("address-in-country" if address_in_country else "name-suffix")),
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
            asserted_by="resolution",
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
        asserted_by="no-signal",
    )
