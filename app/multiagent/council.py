"""Multi-agent orchestration: two LLM specialists, a conditional institutional analyst, deterministic assurance.

LLMs are used only where the problem needs probabilistic reasoning: reading policy and what people said.
Everything that can be decided deterministically — transport status, revision binding, idempotency,
whether to escalate — is decided by code. At every decision point the deterministic orchestrator runs:

  1. POLICY EVIDENCE ANALYST (LLM, DHA lens). Over the binding DHA and federal clauses: where does the duty
     to communicate stand, which clause governs, do the binding clauses settle this step, and which policy
     gap (if any) it exposes. It may run one more knowledge-base search before answering.
  2. INSTITUTIONAL ANALYST (LLM, TDRA lens) — conditional. Invoked only when the transport side is
     unresolved (accepted without a receipt, unknown, failed): does any telecom clause define delivery or
     assign responsibility for this message? This is where the health-telecom gap shows up per case.
  3. ADVERSARIAL REVIEWER (LLM, independent; by default a different model family). It does not approve:
     it challenges each analyst claim (supported or not, and what is wrong), gives its own reading of the
     obligation, and raises a typed objection to the action under review that code can verify.
  4. INDEPENDENT ASSURANCE (deterministic). Fact check of every claim against the case record; policy-rules
     check (a comparator or out-of-jurisdiction clause can never be the governing clause); conflict detection
     (the reviewer's reading differs, an objection survives, the binding clauses do not settle a high-risk
     step). Every quotation shown was already verified against its source page at ingest.
  5. FEEDBACK. An analyst claim that fails a check, or that the reviewer judges unsupported, goes back once
     with the findings; a claim that still fails is DISPUTED (kept in the trace, never relied on).
  6. DETERMINISTIC ORCHESTRATOR DECISION — no LLM coordinator: PROCEED (the gate decides) or ESCALATE to a
     named owner with a deadline, on a verified objection, a disputed claim, or an unsettled high-risk step.

Every message, tool call, check and decision is appended to the hash-chained audit log. The gate decides the
transition without reading any of it; the only effect agents can have on a case is an escalation to a person.
"""

from __future__ import annotations

import json
import os
from typing import Any

from app.advisers.jev import ACTIONS
from app.multiagent.providers import Provider, ProviderError

ROLES = ("analyst", "institution", "reviewer")

MANDATES: dict[str, dict[str, Any]] = {
    "analyst": {
        "speaks_for": "the health regulator (DHA, the Dubai Health Authority) and federal health law, as Policy Evidence Analyst",
        "sources": ["S1", "U1", "U3", "U6", "U7", "U11"],
        "query": "critical result communication record acknowledgment patient physician walk-in",
        "tools": {"NONE": "No tool needed.", "kb_search": "Search the DHA and federal health clauses again for this step."},
    },
    "institution": {
        "speaks_for": "the telecom regulator (TDRA, the Telecommunications and Digital Government Regulatory Authority), as an institutional participant",
        "sources": ["U8", "U10", "G6"],
        "query": "delivery text message subscriber licensee status report received",
        "tools": {},
    },
    "reviewer": {
        "speaks_for": "independent adversarial review: challenge every claim; do not approve by default",
        "sources": None, "query": "critical result communication patient delivery acknowledgment",
        "tools": {},
    },
}

OBLIGATION = {
    "COMMUNICATED": "A person acknowledged the current revision; the communication record can be written.",
    "AWAITING_ACK": "The result was sent or delivered but no one has acknowledged the current revision.",
    "DIRECT_NOT_PERMITTED": "The shown clauses route this result to a physician, not directly to the patient.",
    "NOT_YET_SENT": "Nothing has been communicated yet and nothing prevents a first send.",
    "INSUFFICIENT_EVIDENCE": "The case facts and clauses shown do not settle it.",
}
GAPS = {
    "NONE": "No policy gap bears on this step.",
    "NO_ACK_CLOCK": "No binding clause sets a time limit for acknowledgment or escalation (GR-03).",
    "DELIVERY_EVIDENCE_UNDEFINED": "No instrument says what proves a clinical message reached a person (GR-01, GR-15).",
    "RECIPIENT_RESPONSIBILITY_UNCLEAR": "Who must receive, or act on, the result is not settled (GR-16).",
    "IDENTITY_OF_RESPONDER_UNVERIFIABLE": "Nothing defines how to verify who answered a message (GR-09).",
    "RETENTION_CLASS_UNCLEAR": "Whether the communication record is an audit log or health data is not settled (GR-11).",
    "FALLBACK_UNAUTHORISED": "No clause authorises an alternative channel or recipient (GR-04).",
}
ISSUES = {
    "NONE": "Nothing wrong: the claim follows from the case facts and the cited clause.",
    "CONTRADICTS_CASE_FACTS": "The claim asserts something the case record does not show (a receipt, an acknowledgment, an attempt).",
    "CLAUSE_DOES_NOT_SUPPORT": "The cited clause does not say what the claim relies on.",
    "WRONG_AUTHORITY": "The cited clause is a comparator or from another jurisdiction, so it cannot govern this case.",
    "WRONG_REVISION": "The claim relies on an acknowledgment or receipt for an older result revision.",
    "IGNORES_WHAT_WAS_SAID": "The claim ignores what a person said in `case.recent_events`.",
}
OBJECTIONS = {
    "NONE": "No concrete objection to the action under review.",
    "ACCEPTANCE_AS_DELIVERY": "The action treats a provider acceptance as delivery: no delivery receipt exists.",
    "STALE_REVISION_ACK": "The action relies on an acknowledgment of an older result revision.",
    "SCOPE_ROUTES_ELSEWHERE": "The clauses route this result to a physician, but the action sends it to the patient.",
    "UNAPPROVED_CHANNEL": "The action uses an alternative channel with no approved fallback procedure.",
    "RETRY_BEFORE_RECONCILE": "The action retries while an earlier attempt's outcome is still unknown.",
    "ACK_WINDOW_EXPIRED": "The action keeps waiting although the configured acknowledgment window has passed.",
    "UNVERIFIED_RECIPIENT": "The acknowledgment on record is not from a verified recipient.",
    "TEXT_CONTRADICTS_RECORD": "What a person said in `case.recent_events` contradicts the structured record "
                               "(for example the reply is from someone other than the patient).",
}
SENDS = ("SEND_PRIMARY", "RETRY_SAME_CHANNEL", "PROPOSE_FALLBACK")
HIGH_RISK = SENDS + ("RECORD_DOCUMENTATION",)
BINDING_JURISDICTIONS = {"AE-DU": {"AE-DU", "AE-FED"}, "AE-AZ": {"AE-AZ", "AE-FED"}}


def _clauses(chunks: list[dict]) -> dict[str, str]:
    out = {c["chunk_id"]: f"[{c.get('jurisdiction')} · {c.get('claim_classification')}] {c.get('section_id')}: "
                          f"{(c.get('text') or '')[:200]}" for c in chunks}
    out["NONE"] = "None of the shown clauses bears on this step."
    return out


def _brief(chunks: list[dict]) -> list[dict]:
    return [{"chunk_id": c["chunk_id"], "authority_class": c.get("claim_classification"), "jurisdiction": c.get("jurisdiction"),
             "section": c.get("section_id"), "text": (c.get("text") or "")[:320]} for c in chunks]


def _questions(role: str, chunks: list[dict], with_tools: bool, claims: dict | None = None) -> dict[str, Any]:
    q: dict[str, Any] = {}
    if role == "analyst":
        q["obligation"] = {"type": "choice", "criteria": OBLIGATION, "instructions":
            "Under the binding clauses in `evidence`, where does the duty to communicate this result stand now? An "
            "acknowledgment counts only for `case.current_result_revision`; a delivery receipt is not an "
            "acknowledgment; read `case.recent_events` for what people actually said."}
        q["clause"] = {"type": "choice", "criteria": _clauses(chunks), "instructions":
            "Which shown clause governs your conclusion? It must bind this case (not a comparator)."}
        q["settled"] = {"type": "noul", "criteria": {"true": "Settled", "false": "Not settled"}, "instructions":
            "Do the binding clauses shown settle what must happen at this step, with no gap left to a human?"}
        q["gap"] = {"type": "choice", "criteria": GAPS, "instructions":
            "Which policy gap, if any, does this step expose?"}
        if with_tools:
            q["tool_request"] = {"type": "choice", "criteria": MANDATES[role]["tools"], "instructions":
                "Do you need one more knowledge-base search before your answer is final? Search if no shown clause "
                "addresses this step's situation."}
    elif role == "institution":
        q["telecom_covers"] = {"type": "noul", "criteria": {"true": "Covered", "false": "Not covered"}, "instructions":
            "Does any shown telecom clause define what counts as delivery of THIS message to a person, or assign "
            "responsibility for it, in the situation in `case.attempts`? Marketing-only or handset-only definitions "
            "do not cover a person receiving a clinical result."}
        q["clause"] = {"type": "choice", "criteria": _clauses(chunks), "instructions":
            "Which shown telecom clause comes closest to governing this message?"}
    else:  # reviewer
        q["objection"] = {"type": "choice", "criteria": OBJECTIONS, "instructions":
            "Is there a concrete reason NOT to take `step.action_under_review` now? Read `case` and "
            "`case.recent_events`. Choose the one objection that applies, or NONE."}
        q["own_reading"] = {"type": "choice", "criteria": OBLIGATION, "instructions":
            "Independently of the analysts: where does the duty to communicate stand now?"}
        for role_ in (claims or {}):
            q[f"{role_}_supported"] = {"type": "noul", "criteria": {"true": "Supported", "false": "Not supported"},
                                       "instructions":
                f"Is the claim in `claims.{role_}` supported by the facts in `case` and by its `cited_text`? A claim "
                "that contradicts the case record, or relies on a comparator as if it were binding, is unsupported."}
            q[f"{role_}_issue"] = {"type": "choice", "criteria": ISSUES, "instructions":
                f"What, if anything, is wrong with the claim in `claims.{role_}`?"}
        q["alternative"] = {"type": "choice", "criteria": ACTIONS, "instructions":
            "If the action under review were not taken, which action would the evidence support instead?"}
    return q


class Council:
    def __init__(self, provider: Provider | dict[str, Provider]):
        self.providers = provider if isinstance(provider, dict) else {r: provider for r in ROLES}

    def _p(self, role: str) -> Provider:
        return self.providers[role]

    # -- read-only tools ------------------------------------------------------------------------
    def _search(self, role: str, query: str, jurisdiction: str, top_k: int = 4) -> list[dict]:
        from app.kb import retriever

        m = MANDATES[role]
        kw: dict[str, Any] = {"jurisdiction": jurisdiction, "top_k": top_k, "engine": "bm25"}
        if m["sources"]:
            kw["source_ids"] = m["sources"]
        else:
            kw["scope"] = "applicable"
        return [c.model_dump() for c in retriever.search(query, **kw).chunks]

    # -- one agent turn ---------------------------------------------------------------------------
    def _ask(self, role: str, rt, case: dict, action: str, data_class: str, tool_calls: list[dict],
             chunks: list[dict], claims: dict | None = None, feedback: dict | None = None, prior: dict | None = None) -> dict:
        state: dict[str, Any] = {"you_speak_for": MANDATES[role]["speaks_for"], "case": case,
                                 "step": {"action_under_review": action}, "evidence": _brief(chunks)}
        if claims:
            state["claims"] = claims
        if feedback:
            state["your_previous_answer"] = (prior or {}).get("answers")
            state["assurance_findings"] = feedback
            state["instruction"] = ("Independent checks reviewed your previous answer. Where a finding is right, correct "
                                    "your answer; where it is wrong, keep it. Judge only from `case` and `evidence`.")
        with_tools = role == "analyst" and feedback is None
        try:
            ans, bad = self._p(role).ask(state, _questions(role, chunks, with_tools, claims), data_class=data_class)
            tool = ans.get("tool_request", {}).get("choice", "NONE") if with_tools else "NONE"
            if tool == "kb_search":
                more = self._search(role, f"{case.get('this_step_event', '')} {MANDATES[role]['query']}", rt.jurisdiction, top_k=3)
                known = {c["chunk_id"] for c in chunks}
                chunks = chunks + [c for c in more if c["chunk_id"] not in known]
                tool_calls.append({"agent": role, "tool": tool, "result_size": len(more)})
                state = {**state, "evidence": _brief(chunks), "tool_result": {"tool": tool, "added": [c["chunk_id"] for c in more]}}
                ans, bad = self._p(role).ask(state, _questions(role, chunks, False, claims), data_class=data_class)
            return {"status": "ANSWERED" if not bad else "PARTIAL", "answers": ans, "invalid": bad,
                    "evidence": [c["chunk_id"] for c in chunks], "tool": tool, "_chunks": chunks}
        except PermissionError as exc:
            return {"status": "REFUSED_RESIDENCY", "reason": str(exc)[:200]}
        except (ProviderError, OSError, ValueError, KeyError) as exc:
            return {"status": "UNAVAILABLE", "reason": str(exc)[:200]}

    @staticmethod
    def _claim(msg: dict) -> dict:
        a = msg.get("answers", {})
        cited = a.get("clause", {}).get("choice")
        text = next((c.get("text", "")[:320] for c in msg.get("_chunks", []) if c["chunk_id"] == cited), None)
        return {"answers": {k: v for k, v in a.items() if k != "tool_request"}, "cited_clause": cited, "cited_text": text}

    # -- protocol -------------------------------------------------------------------------------
    def deliberate(self, rt, event: dict[str, Any], action: str, step_view: dict[str, Any]) -> dict[str, Any]:
        data_class = "SYNTHETIC" if all(str(v).startswith("SYN-") for v in (rt.case_id, rt.patient_ref, rt.contact_ref)) else "HEALTH"
        case, tool_calls = step_view, []
        msgs: dict[str, dict] = {}
        query = f"{case.get('this_step_event', '')} {MANDATES['analyst']['query']}"

        # 1. Policy Evidence Analyst.
        msgs["analyst"] = self._ask("analyst", rt, case, action, data_class, tool_calls,
                                    self._search("analyst", query, rt.jurisdiction))
        # 2. Institutional analyst, only when the transport side is unresolved.
        if transport_unresolved(case):
            msgs["institution"] = self._ask("institution", rt, case, action, data_class, tool_calls,
                                            self._search("institution", MANDATES["institution"]["query"], rt.jurisdiction))
        answered = {r: m for r, m in msgs.items() if m.get("status") in ("ANSWERED", "PARTIAL")}
        # 3. Adversarial reviewer: challenges the claims and reads the case independently.
        claims = {r: self._claim(m) for r, m in answered.items()}
        msgs["reviewer"] = self._ask("reviewer", rt, case, action, data_class, tool_calls,
                                     self._search("reviewer", query, rt.jurisdiction), claims=claims)

        # 4. Independent assurance (deterministic) and 5. one feedback round for failing analyst claims.
        assurance = {r: assure(r, m, case, action, rt.jurisdiction) for r, m in msgs.items() if m.get("answers")}
        rv = msgs["reviewer"].get("answers", {})
        reviews: dict[str, dict] = {}
        for r in answered:
            sup = rv.get(f"{r}_supported", {}).get("noul")
            issue = rv.get(f"{r}_issue", {}).get("choice")
            flagged = bool(assurance.get(r)) or (sup is not None and sup < 0.5)
            reviews[r] = {"checks": assurance.get(r, []), "reviewer_supported": sup, "reviewer_issue": issue,
                          "flagged": flagged, "outcome": "ACCEPTED"}
            if not flagged:
                continue
            feedback = {"deterministic_checks": assurance.get(r, []), "reviewer_issue": issue,
                        "reviewer_issue_meaning": ISSUES.get(issue or "NONE"), "reviewer_probability_supported": sup}
            revised = self._ask(r, rt, case, action, data_class, tool_calls, msgs[r]["_chunks"], feedback=feedback, prior=msgs[r])
            if revised.get("status") not in ("ANSWERED", "PARTIAL"):
                reviews[r]["outcome"] = "DISPUTED" if assurance.get(r) else "UPHELD"
            else:
                before = _conclusion(msgs[r]["answers"])
                msgs[r] = {**revised, "tool": msgs[r].get("tool")}
                after = assure(r, revised, case, action, rt.jurisdiction)
                reviews[r]["checks_after"] = after
                reviews[r]["outcome"] = "DISPUTED" if after else ("CORRECTED" if _conclusion(revised["answers"]) != before else "UPHELD")
            if reviews[r]["outcome"] == "DISPUTED":
                msgs[r]["status"] = "DISPUTED"
        # The reviewer's own objection is verified by code too; an objection that does not fit is rejected.
        reviews["reviewer"] = {"checks": assurance.get("reviewer", []), "flagged": bool(assurance.get("reviewer")),
                               "outcome": "OBJECTION_REJECTED" if assurance.get("reviewer") else "ACCEPTED"}

        # 6. Deterministic orchestrator decision.
        conflicts = detect_conflicts(msgs, reviews, case, action)
        decision, reason = orchestrate(msgs, reviews, conflicts, action)
        for m in msgs.values():
            m.pop("_chunks", None)
        return {
            "provider": {r: p.label for r, p in self.providers.items()}, "action_under_review": action,
            "messages": msgs, "tool_calls": tool_calls, "reviews": reviews, "conflicts": conflicts,
            "decision": decision, "escalation": reason,
            "summary": {"flagged": sum(v.get("flagged", False) for k, v in reviews.items() if k != "reviewer"),
                        "corrected": sum(v.get("outcome") == "CORRECTED" for v in reviews.values()),
                        "upheld": sum(v.get("outcome") == "UPHELD" for v in reviews.values()),
                        "disputed": [k for k, v in reviews.items() if v.get("outcome") == "DISPUTED"],
                        "objection_rejected": reviews["reviewer"]["outcome"] == "OBJECTION_REJECTED",
                        "institution_invoked": "institution" in msgs},
        }


# --- deterministic assurance ----------------------------------------------------------------------

def transport_unresolved(case: dict) -> bool:
    cur = case.get("current_result_revision")
    atts = [a for a in case.get("attempts", []) if a.get("revision") == cur]
    return bool(atts) and not any(a.get("delivery_receipt") for a in atts)


def _conclusion(answers: dict[str, Any]) -> dict[str, Any]:
    """What an answer concludes: its choices, and which side of 0.5 each probability is on."""
    out = {}
    for k, v in answers.items():
        if k in ("tool_request", "rationale") or not isinstance(v, dict):
            continue
        out[k] = v.get("choice") if "choice" in v else (v["noul"] >= 0.5 if "noul" in v else v.get("score"))
    return out


def assure(role: str, msg: dict, case: dict, action: str, jurisdiction: str) -> list[str]:
    """Fact check + policy-rules check for one agent's answer. Code cannot hallucinate."""
    out = fact_check(role, msg.get("answers", {}), case, action)
    cited = msg.get("answers", {}).get("clause", {}).get("choice")
    chunk = next((c for c in msg.get("_chunks", []) if c["chunk_id"] == cited), None)
    if role == "analyst" and chunk is not None:
        binding = BINDING_JURISDICTIONS.get(jurisdiction, {jurisdiction})
        if chunk.get("claim_classification") == "GLOBAL_COMPARATOR" or chunk.get("jurisdiction") not in binding:
            out.append(f"cites {cited} ({chunk.get('jurisdiction')}, {chunk.get('claim_classification')}) as governing; "
                       "a comparator or another jurisdiction's clause cannot govern this case")
    return out


def fact_check(role: str, answers: dict[str, Any], case: dict[str, Any], action: str) -> list[str]:
    out: list[str] = []
    cur = case.get("current_result_revision")
    atts = [a for a in case.get("attempts", []) if a.get("revision") == cur]
    acks = [k for k in case.get("acknowledgments", []) if k.get("revision") == cur]
    if role == "analyst":
        o = answers.get("obligation", {}).get("choice")
        if o == "COMMUNICATED" and not acks:
            out.append("claims the result was communicated, but no one acknowledged the current revision")
        if o == "AWAITING_ACK" and acks:
            out.append("claims an acknowledgment is awaited, but one exists for the current revision")
        if o == "NOT_YET_SENT" and atts:
            out.append(f"claims nothing was sent, but {len(atts)} attempt(s) exist for the current revision")
        if o == "DIRECT_NOT_PERMITTED" and case.get("case_scope") == "WALK_IN":
            out.append("claims the result must go to a physician, but this is a walk-in case reported to the patient")
    elif role == "reviewer":
        kind = answers.get("objection", {}).get("choice")
        if kind in (None, "NONE"):
            return out
        # Naming the same action as the "alternative" is an inconsistency worth recording, not a fact the
        # objection contradicts: in a recorded run it discarded a correct free-text objection (S9). Only
        # checks against the case record can reject an objection.
        older = [k for k in case.get("acknowledgments", []) if k.get("revision") != cur]
        unknown = [a for a in atts if a.get("outcome") in ("TIMEOUT", "UNKNOWN") and not a.get("reconciled")]
        window = case.get("configured_ack_window_minutes")
        checks = {
            "ACCEPTANCE_AS_DELIVERY": (action in ("AWAIT_ACKNOWLEDGMENT", "RECORD_DOCUMENTATION", "NO_ACTION")
                                       and any(a.get("provider_accepted") and not a.get("delivery_receipt") for a in atts),
                                       "no accepted-but-undelivered attempt, or the action does not rely on delivery"),
            "STALE_REVISION_ACK": (action == "RECORD_DOCUMENTATION" and bool(older) and not acks,
                                   "the action does not rely on an older-revision acknowledgment"),
            "SCOPE_ROUTES_ELSEWHERE": (action in SENDS and case.get("case_scope") == "GENETIC"
                                       and case.get("recipient_route") == "PATIENT",
                                       "the message is not addressed to the patient, or the scope is walk-in"),
            "UNAPPROVED_CHANNEL": (action == "PROPOSE_FALLBACK" and not case.get("approved_fallback_procedure"),
                                   "the action is not a fallback, or a fallback procedure is approved"),
            "RETRY_BEFORE_RECONCILE": (action == "RETRY_SAME_CHANNEL" and bool(unknown),
                                       "the action is not a retry, or no attempt is unreconciled"),
            "ACK_WINDOW_EXPIRED": (action in ("AWAIT_ACKNOWLEDGMENT", "AWAIT_EVIDENCE", "NO_ACTION") and window is not None
                                   and (case.get("minutes_elapsed") or 0) > window and not acks,
                                   "the window has not passed, an acknowledgment exists, or the action is not waiting"),
            "UNVERIFIED_RECIPIENT": (action == "RECORD_DOCUMENTATION" and any(k.get("identity_verified") is False for k in acks),
                                     "every acknowledgment on record is from a verified recipient"),
            # Free text cannot be checked by code: it needs a recorded human statement to rest on.
            "TEXT_CONTRADICTS_RECORD": (bool(case.get("recent_events")), "there is no recorded human statement to rely on"),
        }
        ok, why = checks.get(kind, (True, ""))
        if not ok:
            out.append(f"objection {kind} does not fit the case: {why}")
    return out


def detect_conflicts(msgs: dict[str, dict], reviews: dict[str, dict], case: dict, action: str) -> list[str]:
    """Deterministic conflict detection over trusted answers."""
    out = []
    a = msgs.get("analyst", {})
    r = msgs.get("reviewer", {})
    trusted_a = a.get("status") in ("ANSWERED", "PARTIAL")
    o = a.get("answers", {}).get("obligation", {}).get("choice") if trusted_a else None
    own = r.get("answers", {}).get("own_reading", {}).get("choice")
    if o and own and o != own:
        out.append(f"READINGS_DIFFER: analyst {o} vs reviewer {own}")
    obj = r.get("answers", {}).get("objection", {})
    if obj.get("choice") not in (None, "NONE") and reviews.get("reviewer", {}).get("outcome") != "OBJECTION_REJECTED":
        out.append(f"OBJECTION: {obj['choice']}")
    if trusted_a and action in HIGH_RISK and a.get("answers", {}).get("settled", {}).get("noul", 1.0) < 0.5:
        out.append("UNSETTLED_HIGH_RISK: the binding clauses do not settle a high-risk step")
    i = msgs.get("institution", {})
    if i.get("status") in ("ANSWERED", "PARTIAL") and i.get("answers", {}).get("telecom_covers", {}).get("noul", 1.0) < 0.5:
        out.append("TELECOM_GAP: no telecom clause covers delivery of this message to a person (GR-15)")
    if o == "DIRECT_NOT_PERMITTED" and action in SENDS and case.get("recipient_route", "PATIENT") == "PATIENT":
        out.append("SCOPE_CONFLICT: the result is routed away from the patient but the action sends to the patient")
    return out


def orchestrate(msgs: dict[str, dict], reviews: dict[str, dict], conflicts: list[str], action: str) -> tuple[str, str | None]:
    """The deterministic orchestrator: PROCEED (the gate decides) or ESCALATE to a person, with the reason.

    Escalates on (a) a reviewer objection that survived the code check, with confidence >= 0.5 — a free-text
    objection (TEXT_CONTRADICTS_RECORD) needs 0.7, because code cannot verify it; (b) a disputed analyst claim
    on a high-risk step. Gaps and differing readings are recorded, not escalated.
    """
    obj = msgs.get("reviewer", {}).get("answers", {}).get("objection", {})
    kind, conf = obj.get("choice"), obj.get("confidence", 0)
    if kind not in (None, "NONE") and reviews.get("reviewer", {}).get("outcome") != "OBJECTION_REJECTED":
        if conf >= (0.7 if kind == "TEXT_CONTRADICTS_RECORD" else 0.5):
            return "ESCALATE", f"verified reviewer objection {kind}: {OBJECTIONS[kind]}"
    if action in HIGH_RISK and reviews.get("analyst", {}).get("outcome") == "DISPUTED":
        return "ESCALATE", "the analyst's claim on a high-risk step still contradicts the case record after revision"
    # A policy gap, or the analyst and reviewer reading a step differently, is recorded in the trace and the
    # case's open questions, not escalated: in recorded runs that rule escalated correct paths (SC-01, SC-03).
    return "PROCEED", None


# --- configuration ---------------------------------------------------------------------------------

RECOMMENDED_REPLAY = {"RESULTRELAY_AGENT_PROVIDER": "replay", "RESULTRELAY_AGENT_REPLAY_FROM": "mistral",
                      "RESULTRELAY_REVIEWER_PROVIDER": "replay", "RESULTRELAY_REVIEWER_REPLAY_FROM": "jev"}


def configured_council(default_replay: bool = False) -> Council | None:
    """The council from the environment; with ``default_replay`` and nothing configured, the recorded run of
    the recommended allocation (Mistral analysts, Jev adversarial reviewer)."""
    from app.multiagent.providers import configured, load_dotenv

    load_dotenv()
    if default_replay and not os.environ.get("RESULTRELAY_AGENT_PROVIDER"):
        for k, v in RECOMMENDED_REPLAY.items():
            os.environ.setdefault(k, v)
    providers = {r: configured(r) for r in ROLES}
    if not all(providers.values()):
        return None
    return Council(providers)


def enabled_for(spec: dict[str, Any]) -> bool:
    """Deliberate at decision points by default (RESULTRELAY_AGENT_STEPS=all for every step)."""
    return os.environ.get("RESULTRELAY_AGENT_STEPS", "actions") == "all" or spec.get("kind") == "action"


def as_audit_payload(d: dict[str, Any]) -> str:
    return json.dumps(d, default=str)[:20000]
