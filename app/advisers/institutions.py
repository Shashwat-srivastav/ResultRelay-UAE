"""Institutional participants: a DHA agent and a TDRA agent, each reading the case through its own mandate.

The policy & legal reviewer (``app.advisers.jev``) asks "is this step lawful?". These agents ask what
each regulator would conclude about the same case, from the clauses that regulator issued:

  DHA   (health regulator: ST-28, the AI policy PP-09, NABIDH, the ICT Health Law it administers)
        - has the result been *communicated* to the right person, in the sense of ST-28 §11.1.3?
        - which shown clause governs that conclusion?
        - is the way AI is used in this case within PP-09 (advise only, human override, traceable)?
  TDRA  (telecom regulator: the Mobile Spam policy, the only TDRA instrument retrieved)
        - does the network evidence show *delivery* to the subscriber, as opposed to acceptance?
        - which shown clause governs that conclusion?

A deterministic coordinator then compares the two. Its job is the one thing neither regulator's text
does: notice when the network side and the health side reach different conclusions about the same
message (gap GR-15), and put that in front of the supervisor. Nothing here can change a case: the
review runs after the gate has decided, is written to the hash-chained audit log, and is shown to a
person. Every judgment is a typed TypeSafe Jev answer with a probability, over clauses retrieved from
the verified corpus and filtered to the agent's own issuing authority.

Residency: the request goes through ``authorise`` first. A synthetic case (every reference SYN-*) may
use the hosted endpoint; a real case on the same endpoint is refused before any request is made.
Responses are recorded under evaluation/agent_runs/ and replayed offline; a replay is refused if the
case view or the evidence changed.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any

from app.advisers.jev import ENDPOINT, RUNS, _post
from app.advisers.residency import authorise

COMMUNICATED_STATES = {"COMMUNICATION_DOCUMENTED", "CLINICAL_ACKNOWLEDGMENT_CONFIRMED", "CORRECTED_RESULT_ACKNOWLEDGED"}

MANDATES = {
    "DHA": {
        "role": "Dubai Health Authority, the health regulator that licenses the laboratory",
        "sources": ["S1", "U1"],
        "query": "critical result communication record acknowledgment",
    },
    "DHA_AI": {
        "role": "Dubai Health Authority, as issuer of the AI in healthcare policy",
        "sources": ["U6"],
        "query": "AI override traceable failures accountability graceful degradation",
    },
    "TDRA": {
        "role": "Telecommunications and Digital Government Regulatory Authority, the telecom regulator",
        "sources": ["U8"],
        "query": "delivery text message licensee mobile customer network scope",
    },
}


@dataclass
class InstitutionalReview:
    status: str  # REVIEWED | REFUSED_RESIDENCY | UNAVAILABLE
    residency: str
    dha: dict[str, Any] = field(default_factory=dict)
    tdra: dict[str, Any] = field(default_factory=dict)
    conflicts: list[dict[str, str]] = field(default_factory=list)
    agrees_with_gate: bool | None = None
    evidence: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def case_view(rt) -> dict[str, Any]:
    """What a regulator would be shown: facts, never the gate's conclusion."""
    current = rt.current_revision_id
    return {
        "case_scope": rt.case_scope,
        "jurisdiction": rt.jurisdiction,
        "current_result_revision": current,
        "revisions": [r.get("revision_id") for r in rt.revisions] if isinstance(rt.revisions, list) else list(rt.revisions or []),
        "attempts": [{"channel": a.channel, "recipient": a.recipient, "revision": a.result_revision_id,
                      "provider_accepted": a.accepted, "delivery_receipt": bool(a.receipt_recorded),
                      "failed": a.failed, "outcome": a.outcome} for a in rt.network.attempts],
        "acknowledgments": [{"revision": k.get("result_revision_id"), "role": k.get("role"),
                             "channel": k.get("channel"), "identity_verified": k.get("identity_verified")}
                            for k in rt.acknowledgments],
        "events_seen": [s.get("event", {}).get("type") if isinstance(s.get("event"), dict) else s.get("type")
                        for s in rt.steps][:40],
        "ai_use": ("A policy & legal reviewer model proposes actions over retrieved clauses; a deterministic gate "
                   "decides every transition; a named supervisor can override; every proposal, probability and "
                   "cited clause is written to a hash-chained audit log."),
    }


def _evidence(mandate: str, jurisdiction: str, case_scope: str = "", top_k: int = 5) -> list[dict[str, Any]]:
    from app.kb import retriever

    m = MANDATES[mandate]
    # The case scope steers retrieval (a genetic case needs §13.4, a walk-in case §11.1); the agent is
    # then asked which of what it was shown governs.
    scope_terms = {"GENETIC": "genetic physician referring", "WALK_IN": "walk-in patient"}.get(case_scope, "")
    res = retriever.search(f"{m['query']} {scope_terms}".strip(), jurisdiction=jurisdiction, source_ids=m["sources"], top_k=top_k)
    return [c.model_dump() for c in res.chunks]


def _clause_choices(chunks: list[dict[str, Any]]) -> dict[str, str]:
    out = {c["chunk_id"]: f"{c.get('section_id')}: {(c.get('text') or '')[:220]}" for c in chunks}
    out["NONE"] = "None of the shown clauses bears on this case."
    return out


def _questions(dha_chunks: list[dict], tdra_chunks: list[dict]) -> dict[str, Any]:
    return {
        "dha_communication_established": {"type": "noul", "instructions":
            "You are the Dubai Health Authority agent. Using only `evidence.DHA` and the case facts in `case`: has "
            "this critical result been communicated to the right person, in the sense of a communication record under "
            "DHA ST-28 §11.1.3? A provider acceptance or a delivery receipt shows a message reached a network or a "
            "handset, not that a person received it; an acknowledgment must be for `case.current_result_revision`.",
            "criteria": {"true": "Communication to the right person is established", "false": "Not established"}},
        "dha_governing_clause": {"type": "choice", "criteria": _clause_choices(dha_chunks), "instructions":
            "Which DHA-side clause most directly governs your conclusion?"},
        "dha_ai_use_conforms": {"type": "noul", "instructions":
            "As the DHA agent: does `case.ai_use` conform to the DHA AI policy clauses shown in `evidence.DHA_AI` "
            "(human override, traceable failures, accountability)? Judge only what is described.",
            "criteria": {"true": "Conforms to the shown clauses", "false": "Does not, or cannot be judged"}},
        "tdra_network_delivery_evidenced": {"type": "noul", "instructions":
            "You are the TDRA (telecom regulator) agent. Using only `evidence.TDRA` and `case.attempts`: is there "
            "evidence that a message was delivered to the subscriber across the network (a delivery receipt), as "
            "opposed to only accepted by the provider? A voice call or an in-person contact is not a text message.",
            "criteria": {"true": "Network delivery of a text message is evidenced", "false": "Not evidenced"}},
        "tdra_governing_clause": {"type": "choice", "criteria": _clause_choices(tdra_chunks), "instructions":
            "Which TDRA clause did you apply to decide what counts as delivery of a text message? Choose NONE only "
            "if no shown clause concerns delivery or the scope of text messages."},
    }


def _ask(state: dict, questions: dict) -> dict:
    digest = hashlib.sha256(json.dumps([state, questions], sort_keys=True).encode()).hexdigest()[:20]
    path = RUNS / f"inst-{digest}.json"
    if os.environ.get("TYPESAFE_API_KEY") and os.environ.get("RESULTRELAY_ADVISE_REPLAY") != "1":
        resp = _post({"model": os.environ.get("RESULTRELAY_JEV_MODEL", "jev-latest"), "state": state, "questions": questions})
        RUNS.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"state": state, "questions": questions, "response": resp}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        return resp
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    raise LookupError("no TYPESAFE_API_KEY and no recorded response for this exact case view")


def coordinate(dha: dict[str, Any], tdra: dict[str, Any], final_state: str) -> tuple[list[dict[str, str]], bool]:
    """Deterministic: compare the two mandates and the gate. No model is involved here."""
    conflicts = []
    communicated = dha["communication_established"] >= 0.5
    delivered = tdra["network_delivery_evidenced"] >= 0.5
    if delivered and not communicated:
        conflicts.append({"type": "DELIVERY_WITHOUT_COMMUNICATION",
                          "detail": "TDRA side: the network delivered the message. DHA side: no communication to the right "
                                    "person is established. A delivery receipt is not a communication record (GR-15)."})
    if communicated and not delivered:
        conflicts.append({"type": "COMMUNICATION_WITHOUT_NETWORK_RECORD",
                          "detail": "DHA side: communication is established, but no text-message delivery is evidenced; "
                                    "the record rests on a non-SMS route (for example a call to the physician), which "
                                    "TDRA's instruments do not cover."})
    if dha["ai_use_conforms"] < 0.5:
        conflicts.append({"type": "AI_USE_QUESTIONED",
                          "detail": f"DHA agent doubts the AI use conforms to PP-09 (p={dha['ai_use_conforms']:.2f})."})
    return conflicts, communicated == (final_state in COMMUNICATED_STATES)


def review(rt) -> InstitutionalReview:
    """Run both institutional agents over a finished case and coordinate their conclusions."""
    data_class = "SYNTHETIC" if all(str(x or "").startswith("SYN-") for x in (rt.case_id, rt.patient_ref, rt.contact_ref)) else "HEALTH"
    decision = authorise(ENDPOINT, data_class=data_class)
    if not decision.permitted:
        return InstitutionalReview(status="REFUSED_RESIDENCY", residency=decision.reason)
    dha_chunks = _evidence("DHA", rt.jurisdiction, rt.case_scope)
    ai_chunks = _evidence("DHA_AI", rt.jurisdiction, top_k=4)
    tdra_chunks = _evidence("TDRA", rt.jurisdiction)

    def brief(chunks):
        return [{"chunk_id": c["chunk_id"], "section": c.get("section_id"), "text": (c.get("text") or "")[:480]} for c in chunks]

    state = {"case": case_view(rt),
             "evidence": {"DHA": brief(dha_chunks), "DHA_AI": brief(ai_chunks), "TDRA": brief(tdra_chunks)},
             "note": "Synthetic laboratory exercise. Each agent speaks for one regulator's mandate; a deterministic gate decided."}
    try:
        a = _ask(state, _questions(dha_chunks, tdra_chunks))["answers"]
    except (LookupError, OSError) as exc:
        return InstitutionalReview(status="UNAVAILABLE", residency=decision.asserted_by, evidence={"error": [str(exc)]})
    dha = {"communication_established": a["dha_communication_established"]["noul"],
           "governing_clause": a["dha_governing_clause"]["choice"],
           "clause_confidence": a["dha_governing_clause"]["confidence"],
           "ai_use_conforms": a["dha_ai_use_conforms"]["noul"]}
    tdra = {"network_delivery_evidenced": a["tdra_network_delivery_evidenced"]["noul"],
            "governing_clause": a["tdra_governing_clause"]["choice"],
            "clause_confidence": a["tdra_governing_clause"]["confidence"]}
    conflicts, agrees = coordinate(dha, tdra, rt.state.value)
    return InstitutionalReview(status="REVIEWED", residency=decision.asserted_by, dha=dha, tdra=tdra,
                               conflicts=conflicts, agrees_with_gate=agrees,
                               evidence={"DHA": [c["chunk_id"] for c in dha_chunks],
                                         "DHA_AI": [c["chunk_id"] for c in ai_chunks],
                                         "TDRA": [c["chunk_id"] for c in tdra_chunks]})
