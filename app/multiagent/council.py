"""Multi-agent orchestration, per step: mandate agents, tool use, a coordinator agent, a rule cross-check.

At every decision point the orchestrator (the Y.3172 MLFO role) runs this protocol:

  1. Post the step to three mandate agents, each with only its own authority's clauses:
       network   - telecom lens (TDRA Mobile Spam policy): what does the transport evidence show?
       health    - DHA lens (ST-28, AI policy PP-09, NABIDH, ICT Health Law): is the result communicated,
                   awaiting acknowledgment, or routed away from the patient?
       reviewer  - policy & legal: is there a concrete objection to the action under review?
  2. An agent may ask for one read-only tool: ``transport_ledger`` (the provider ledger for this case)
     or ``kb_search`` (a further search inside its own sources). The orchestrator runs it and the agent
     answers again with the result in view. No tool can change the case.
  3. Critique, in two layers. A deterministic fact check compares every claim with the case record
     (a "delivery receipt" no attempt has, a "communicated" result nobody acknowledged); code cannot
     hallucinate, so this layer is authoritative. A critic agent then judges whether each answer is
     supported by the case facts and the clause it cited, and names the issue. The critic can be wrong
     too, so its flags only ever trigger a revision; they never overrule the fact check.
  4. Feedback loop: each flagged agent sees the critique and answers once more (CORRECTED or UPHELD).
     An answer that still fails the fact check is DISPUTED: kept in the trace, excluded from the
     conflict check, and a reason for the supervisor to look.
  5. A coordinator agent reads the surviving messages and the critic's verdicts and chooses PROCEED
     (let the gate decide), GATHER_EVIDENCE or ESCALATE_HUMAN, naming the conflict it sees.
  6. A deterministic rule recomputes the conflicts from the trusted answers, so a coordinator that
     misses or invents a conflict is visible in the trace.

Every message, tool call and resolution is appended to the hash-chained audit log: that is the step's
reasoning trace. The deterministic gate decides the transition without reading any of it. The only
effect an agent can have on the case is to *add* a human review request when the coordinator escalates:
agents can make the workflow more cautious, never less.
"""

from __future__ import annotations

import json
import os
from typing import Any

from app.advisers.jev import ACTIONS
from app.multiagent.providers import Provider, ProviderError

MANDATES: dict[str, dict[str, Any]] = {
    "network": {
        "speaks_for": "the telecom side (TDRA, the Telecommunications and Digital Government Regulatory Authority)",
        "sources": ["U8"], "query": "delivery text message licensee mobile customer network",
        "tools": {"NONE": "No tool needed.", "transport_ledger": "Read the provider ledger entries for this case."},
    },
    "health": {
        "speaks_for": "the health regulator (DHA, the Dubai Health Authority) that licenses the laboratory",
        "sources": ["S1", "U1", "U6", "U7"], "query": "critical result communication record acknowledgment patient physician",
        "tools": {"NONE": "No tool needed.", "kb_search": "Search the DHA and federal health clauses again for this step."},
    },
    "reviewer": {
        "speaks_for": "policy and legal review of the action proposed at this step",
        "sources": None, "query": "critical result communication patient delivery acknowledgment",
        "tools": {"NONE": "No tool needed.", "kb_search": "Search all applicable clauses again for this step."},
    },
}

DELIVERY = {
    "DELIVERED_RECEIPT": "The network returned a delivery receipt for the current result revision.",
    "ACCEPTED_ONLY": "The provider accepted a message but no delivery receipt exists.",
    "OUTCOME_UNKNOWN": "An attempt timed out or its outcome is unknown and not yet reconciled.",
    "FAILED": "The provider reported that delivery failed.",
    "NOT_SENT": "No message has been sent for the current result revision.",
}
OBLIGATION = {
    "COMMUNICATED": "A person acknowledged the current revision; the communication record can be written.",
    "AWAITING_ACK": "The result was sent or delivered but no one has acknowledged the current revision.",
    "DIRECT_NOT_PERMITTED": "The shown clauses route this result to a physician, not directly to the patient.",
    "NOT_YET_SENT": "Nothing has been communicated yet and nothing prevents a first send.",
    "INSUFFICIENT_EVIDENCE": "The case facts and clauses shown do not settle it.",
}
RESOLUTION = {
    "PROCEED": "No unresolved conflict: let the deterministic gate decide this step.",
    "GATHER_EVIDENCE": "An agent needs evidence that a later event or a reconciliation can supply.",
    "ESCALATE_HUMAN": "The agents conflict or an objection stands: a named supervisor should look now.",
}
ISSUES = {
    "NONE": "Nothing wrong: the answer follows from the case facts and the cited clause.",
    "CONTRADICTS_CASE_FACTS": "The answer asserts something the case record does not show (a receipt, an acknowledgment, an attempt).",
    "CLAUSE_DOES_NOT_SUPPORT": "The cited clause does not say what the answer relies on.",
    "WRONG_REVISION": "The answer relies on an acknowledgment or receipt for an older result revision.",
    "ACCEPTANCE_AS_DELIVERY": "The answer treats provider acceptance as delivery or as communication.",
    "OUT_OF_MANDATE": "The answer speaks for an authority other than the one the agent represents.",
}
CONFLICTS = {
    "NONE": "The agents' conclusions are consistent.",
    "DELIVERY_WITHOUT_COMMUNICATION": "Network side says delivered; health side says not communicated.",
    "COMMUNICATION_WITHOUT_NETWORK_RECORD": "Health side says communicated; no network delivery is evidenced.",
    "SCOPE_CONFLICT": "Health side routes the result away from the patient while the action sends to the patient.",
    "REVIEWER_OBJECTS": "The policy and legal reviewer has a concrete objection to the action under review.",
}


def _clauses(chunks: list[dict]) -> dict[str, str]:
    out = {c["chunk_id"]: f"{c.get('section_id')}: {(c.get('text') or '')[:200]}" for c in chunks}
    out["NONE"] = "None of the shown clauses bears on this step."
    return out


def _questions(role: str, chunks: list[dict], with_tools: bool) -> dict[str, Any]:
    m = MANDATES[role]
    q: dict[str, Any] = {}
    if role == "network":
        q["delivery_status"] = {"type": "choice", "criteria": DELIVERY, "instructions":
            "From `case.attempts` and any tool result: what does the transport evidence show for the current revision? "
            "Provider acceptance is not delivery."}
    elif role == "health":
        q["obligation"] = {"type": "choice", "criteria": OBLIGATION, "instructions":
            "Under the DHA clauses in `evidence`, where does the duty to communicate this result stand now? An "
            "acknowledgment counts only for `case.current_result_revision`; a delivery receipt is not an acknowledgment."}
    else:
        q["objection"] = {"type": "noul", "criteria": {"true": "A concrete objection exists", "false": "No concrete objection"},
                          "instructions":
            "Is there a concrete reason NOT to take `step.action_under_review` now: acceptance treated as delivery, an "
            "acknowledgment for an older revision, a scope the clauses route elsewhere, an unapproved channel, or a retry "
            "before reconciliation? The absence of a clause naming this exact step is not a reason."}
        q["alternative"] = {"type": "choice", "criteria": ACTIONS, "instructions":
            "If the action under review were not taken, which action would the evidence support instead?"}
    q["clause"] = {"type": "choice", "criteria": _clauses(chunks), "instructions":
        "Which shown clause did you rely on? Choose NONE only if no shown clause bears on this step."}
    if with_tools:
        hint = {"network": " If any attempt in `case.attempts` has no delivery receipt, or its outcome is not DELIVERED, "
                           "read the transport ledger before your answer is final.",
                "health": " If no shown clause addresses this step's situation, search again.",
                "reviewer": " If no shown clause addresses the action under review, search again."}[role]
        q["tool_request"] = {"type": "choice", "criteria": m["tools"], "instructions":
            "Do you need one read-only tool before your answer is final?" + hint}
    return q


def _brief(chunks: list[dict]) -> list[dict]:
    return [{"chunk_id": c["chunk_id"], "section": c.get("section_id"), "text": (c.get("text") or "")[:320]} for c in chunks]


def rule_conflicts(msgs: dict[str, dict], action: str) -> list[str]:
    """Deterministic cross-check over the agents' answers."""
    out = []
    d = msgs.get("network", {}).get("answers", {}).get("delivery_status", {}).get("choice")
    o = msgs.get("health", {}).get("answers", {}).get("obligation", {}).get("choice")
    obj = msgs.get("reviewer", {}).get("answers", {}).get("objection", {}).get("noul")
    if d == "DELIVERED_RECEIPT" and o in ("AWAITING_ACK", "INSUFFICIENT_EVIDENCE"):
        out.append("DELIVERY_WITHOUT_COMMUNICATION")
    if o == "COMMUNICATED" and d in ("NOT_SENT", "ACCEPTED_ONLY", "OUTCOME_UNKNOWN", "FAILED"):
        out.append("COMMUNICATION_WITHOUT_NETWORK_RECORD")
    if o == "DIRECT_NOT_PERMITTED" and action in ("SEND_PRIMARY", "RETRY_SAME_CHANNEL", "PROPOSE_FALLBACK"):
        out.append("SCOPE_CONFLICT")
    if obj is not None and obj >= 0.5:
        out.append("REVIEWER_OBJECTS")
    return out


class Council:
    def __init__(self, provider: Provider | dict[str, Provider]):
        # One provider for every role, or a role -> provider map (e.g. agents on Mistral, critic on Jev).
        self.providers = provider if isinstance(provider, dict) else {r: provider for r in
                                                                       ("network", "health", "reviewer", "critic", "coordinator")}

    def _p(self, role: str) -> Provider:
        return self.providers[role]

    # -- tools (read-only) ------------------------------------------------------------------------
    def _search(self, role: str, query: str, jurisdiction: str, top_k: int = 4) -> list[dict]:
        from app.kb import retriever

        m = MANDATES[role]
        kw: dict[str, Any] = {"jurisdiction": jurisdiction, "top_k": top_k}
        if m["sources"]:
            kw["source_ids"] = m["sources"]
        else:
            kw["scope"] = "applicable"
        return [c.model_dump() for c in retriever.search(query, **kw).chunks]

    def _tool(self, name: str, role: str, rt, query: str) -> dict[str, Any]:
        if name == "transport_ledger":
            return {"tool": name, "result": rt.network.ledger[-8:]}
        if name == "kb_search":
            hits = self._search(role, query + " " + MANDATES[role]["query"], rt.jurisdiction, top_k=3)
            return {"tool": name, "result": _brief(hits), "chunks": hits}
        return {"tool": name, "result": "unknown tool"}

    # -- protocol ---------------------------------------------------------------------------------
    def _ask_agent(self, role: str, rt, case: dict, action: str, data_class: str,
                   tool_calls: list[dict], feedback: dict | None = None, prior: dict | None = None) -> dict:
        """One mandate agent: retrieve its own clauses, answer, optionally use one tool, answer again.

        With ``feedback`` this is a revision round: the agent sees its previous answer and the critique,
        and may keep or change it. No tool is offered in a revision.
        """
        chunks = self._search(role, f"{case.get('this_step_event', '')} {MANDATES[role]['query']}", rt.jurisdiction)
        if prior:
            known = {c["chunk_id"] for c in chunks}
            chunks += [c for c in prior.get("_chunks", []) if c["chunk_id"] not in known]
        state = {"you_speak_for": MANDATES[role]["speaks_for"], "case": case,
                 "step": {"action_under_review": action}, "evidence": _brief(chunks)}
        if feedback:
            state["your_previous_answer"] = prior.get("answers") if prior else None
            state["critic_feedback"] = feedback
            state["instruction"] = ("A critic reviewed your previous answer. Where the feedback is right, correct your "
                                    "answer; where it is wrong, keep your answer. Judge only from `case` and `evidence`.")
        try:
            ans, bad = self._p(role).ask(state, _questions(role, chunks, feedback is None), data_class=data_class)
            tool = ans.get("tool_request", {}).get("choice", "NONE") if feedback is None else "NONE"
            if tool != "NONE" and tool in MANDATES[role]["tools"]:
                tr = self._tool(tool, role, rt, str(case.get("this_step_event", "")))
                tool_calls.append({"agent": role, "tool": tool,
                                   "result_size": len(tr["result"]) if isinstance(tr["result"], list) else 1})
                chunks = chunks + [c for c in tr.pop("chunks", []) if c["chunk_id"] not in {x["chunk_id"] for x in chunks}]
                state = {**state, "evidence": _brief(chunks), "tool_result": tr}
                ans, bad = self._p(role).ask(state, _questions(role, chunks, False), data_class=data_class)
            return {"status": "ANSWERED" if not bad else "PARTIAL", "answers": ans, "invalid": bad,
                    "evidence": [c["chunk_id"] for c in chunks], "tool": tool, "_chunks": chunks}
        except PermissionError as exc:
            return {"status": "REFUSED_RESIDENCY", "reason": str(exc)[:200]}
        except (ProviderError, OSError, ValueError, KeyError) as exc:
            return {"status": "UNAVAILABLE", "reason": str(exc)[:200]}

    def _critic(self, msgs: dict[str, dict], case: dict, action: str, data_class: str) -> dict:
        """Critic agent: is each answer supported by the case facts and by the clause it cited?"""
        answered = {r: m for r, m in msgs.items() if m.get("status") in ("ANSWERED", "PARTIAL")}
        if not answered:
            return {"status": "SKIPPED"}
        board = {}
        for r, m in answered.items():
            cited = m["answers"].get("clause", {}).get("choice")
            text = next((c.get("text", "")[:320] for c in m.get("_chunks", []) if c["chunk_id"] == cited), None)
            board[r] = {"mandate": MANDATES[r]["speaks_for"],
                        "answers": {k: v for k, v in m["answers"].items() if k != "tool_request"},
                        "cited_clause": cited, "cited_text": text}
        q = {}
        for r in answered:
            q[f"{r}_supported"] = {"type": "noul", "criteria": {"true": "Supported", "false": "Not supported"},
                                   "instructions":
                f"You are the critic. Is agent `{r}`'s answer in `agent_answers.{r}` supported by the facts in `case` "
                "and by its `cited_text`? Any claim that contradicts the case facts (for example a receipt or an "
                "acknowledgment that `case` does not show) is unsupported."}
            q[f"{r}_issue"] = {"type": "choice", "criteria": ISSUES, "instructions":
                f"What, if anything, is wrong with agent `{r}`'s answer?"}
        state = {"case": case, "step": {"action_under_review": action}, "agent_answers": board}
        try:
            ans, bad = self._p("critic").ask(state, q, data_class=data_class)
            return {"status": "ANSWERED" if not bad else "PARTIAL", "answers": ans, "invalid": bad}
        except PermissionError as exc:
            return {"status": "REFUSED_RESIDENCY", "reason": str(exc)[:200]}
        except (ProviderError, OSError, ValueError, KeyError) as exc:
            return {"status": "UNAVAILABLE", "reason": str(exc)[:200]}

    def deliberate(self, rt, event: dict[str, Any], action: str, step_view: dict[str, Any]) -> dict[str, Any]:
        data_class = "SYNTHETIC" if all(str(v).startswith("SYN-") for v in (rt.case_id, rt.patient_ref, rt.contact_ref)) else "HEALTH"
        case = step_view
        tool_calls: list[dict] = []

        # 1-2. Mandate agents answer, with optional tool use.
        msgs = {role: self._ask_agent(role, rt, case, action, data_class, tool_calls)
                for role in ("network", "health", "reviewer")}

        # 3. Critique: deterministic fact check (authoritative) + critic agent (second opinion).
        facts = {r: fact_check(r, m.get("answers", {}), case, action) for r, m in msgs.items()}
        critic = self._critic(msgs, case, action, data_class)
        reviews: dict[str, dict] = {}
        for r, m in msgs.items():
            if m.get("status") not in ("ANSWERED", "PARTIAL"):
                continue
            ca = critic.get("answers", {})
            p_sup = ca.get(f"{r}_supported", {}).get("noul")
            issue = ca.get(f"{r}_issue", {}).get("choice")
            # A revision is triggered by a failed fact check or by the critic judging the answer unsupported.
            # The issue label explains a flag; on its own it is not one (the critic labels liberally).
            flagged = bool(facts[r]) or (p_sup is not None and p_sup < 0.5)
            reviews[r] = {"fact_check": facts[r], "critic_supported": p_sup, "critic_issue": issue, "flagged": flagged}

        # 4. Feedback loop: one revision for each flagged agent, then re-check the facts.
        revisions = 0
        for r, rv in reviews.items():
            if not rv["flagged"]:
                rv["outcome"] = "ACCEPTED"
                continue
            revisions += 1
            feedback = {"fact_check_findings": rv["fact_check"], "critic_issue": rv["critic_issue"],
                        "critic_issue_meaning": ISSUES.get(rv["critic_issue"] or "NONE"),
                        "critic_probability_supported": rv["critic_supported"]}
            revised = self._ask_agent(r, rt, case, action, data_class, tool_calls, feedback=feedback, prior=msgs[r])
            if revised.get("status") in ("ANSWERED", "PARTIAL"):
                rv["before"] = {k: v for k, v in msgs[r]["answers"].items() if k != "tool_request"}
                msgs[r] = {**revised, "tool": msgs[r].get("tool")}
                after = fact_check(r, revised["answers"], case, action)
                rv["fact_check_after"] = after
                changed = _conclusion(rv["before"]) != _conclusion(revised["answers"])
                rv["outcome"] = ("DISPUTED" if after else ("CORRECTED" if changed else "UPHELD"))
            else:
                rv["outcome"] = "DISPUTED" if rv["fact_check"] else "UPHELD"
            if rv["outcome"] == "DISPUTED":
                msgs[r]["status"] = "DISPUTED"

        # 5. Rule cross-check uses only answers that survived the critique.
        trusted = {r: m for r, m in msgs.items() if m.get("status") in ("ANSWERED", "PARTIAL")}
        rules = rule_conflicts(trusted, action)

        # 6. Coordinator sees the answers and the critic's verdicts.
        coord: dict[str, Any] = {"status": "SKIPPED"}
        if trusted or any(m.get("status") == "DISPUTED" for m in msgs.values()):
            board = {r: {"status": m.get("status"),
                         "answers": {k: v for k, v in m.get("answers", {}).items() if k != "tool_request"},
                         "critic": {k: reviews.get(r, {}).get(k) for k in ("outcome", "critic_issue", "fact_check_after", "fact_check")}}
                     for r, m in msgs.items() if m.get("answers")}
            state = {"case": case, "step": {"action_under_review": action}, "agent_messages": board,
                     "note": "You coordinate the agents. DISPUTED answers failed a fact check after revision: do not rely "
                             "on them. A deterministic gate decides the transition."}
            q = {"resolution": {"type": "choice", "criteria": RESOLUTION, "instructions":
                     "Given `agent_messages` and the critic's verdicts, what should happen at this step?"},
                 "conflict": {"type": "choice", "criteria": CONFLICTS, "instructions":
                     "Which conflict between the agents' trusted answers, if any, do you see?"}}
            try:
                ans, bad = self._p("coordinator").ask(state, q, data_class=data_class)
                coord = {"status": "ANSWERED" if not bad else "PARTIAL", "answers": ans, "invalid": bad}
            except PermissionError as exc:
                coord = {"status": "REFUSED_RESIDENCY", "reason": str(exc)[:200]}
            except (ProviderError, OSError, ValueError, KeyError) as exc:
                coord = {"status": "UNAVAILABLE", "reason": str(exc)[:200]}
        named = coord.get("answers", {}).get("conflict", {}).get("choice")
        disputed = [r for r, rv in reviews.items() if rv.get("outcome") == "DISPUTED"]
        for m in msgs.values():
            m.pop("_chunks", None)
        return {
            "provider": {r: p.label for r, p in self.providers.items()}, "action_under_review": action,
            "messages": msgs, "tool_calls": tool_calls, "critic": critic, "reviews": reviews,
            "critique_summary": {"flagged": sum(rv["flagged"] for rv in reviews.values()), "revisions": revisions,
                                 "corrected": sum(rv.get("outcome") == "CORRECTED" for rv in reviews.values()),
                                 "disputed": disputed},
            "coordinator": coord, "rule_conflicts": rules,
            "coordinator_matches_rules": ((named == "NONE" and not rules) or (named in rules)) if named else None,
            # A disputed answer is itself a reason for a person to look.
            "escalate": coord.get("answers", {}).get("resolution", {}).get("choice") == "ESCALATE_HUMAN" or bool(disputed),
        }


def _conclusion(answers: dict[str, Any]) -> dict[str, Any]:
    """What an answer concludes: its choices, and which side of 0.5 each probability is on."""
    out = {}
    for k, v in answers.items():
        if k == "tool_request" or not isinstance(v, dict):
            continue
        out[k] = v.get("choice") if "choice" in v else (v["noul"] >= 0.5 if "noul" in v else v.get("score"))
    return out


def fact_check(role: str, answers: dict[str, Any], case: dict[str, Any], action: str) -> list[str]:
    """Deterministic check of an agent's claims against the case record. Code cannot hallucinate."""
    out: list[str] = []
    cur = case.get("current_result_revision")
    atts = [a for a in case.get("attempts", []) if a.get("revision") == cur]
    acks = [k for k in case.get("acknowledgments", []) if k.get("revision") == cur]
    if role == "network":
        d = answers.get("delivery_status", {}).get("choice")
        if d == "DELIVERED_RECEIPT" and not any(a.get("delivery_receipt") for a in atts):
            out.append("claims a delivery receipt, but no attempt for the current revision has one")
        if d == "NOT_SENT" and atts:
            out.append(f"claims nothing was sent, but {len(atts)} attempt(s) exist for the current revision")
        if d == "ACCEPTED_ONLY" and not any(a.get("provider_accepted") for a in atts):
            out.append("claims provider acceptance, but no attempt for the current revision was accepted")
        if d == "ACCEPTED_ONLY" and any(a.get("delivery_receipt") for a in atts):
            out.append("claims acceptance only, but a delivery receipt exists")
        if d == "FAILED" and not any(a.get("failed") for a in atts):
            out.append("claims delivery failed, but no attempt for the current revision failed")
        if d == "OUTCOME_UNKNOWN" and not any(a.get("outcome") in ("TIMEOUT", "UNKNOWN") for a in atts):
            out.append("claims an unknown outcome, but no attempt timed out or is unknown")
    elif role == "health":
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
        obj = answers.get("objection", {}).get("noul")
        alt = answers.get("alternative", {}).get("choice")
        if obj is not None and obj >= 0.5 and alt == action:
            out.append("objects to the action but proposes the same action as the alternative")
    return out


def configured_council() -> Council | None:
    from app.multiagent.providers import ROLES, configured

    providers = {r: configured(r) for r in ROLES}
    if not all(providers.values()):
        return None
    return Council(providers)


def enabled_for(spec: dict[str, Any]) -> bool:
    """Deliberate at decision points by default (RESULTRELAY_AGENT_STEPS=all for every step)."""
    return os.environ.get("RESULTRELAY_AGENT_STEPS", "actions") == "all" or spec.get("kind") == "action"


def as_audit_payload(d: dict[str, Any]) -> str:
    return json.dumps(d, default=str)[:20000]
