"""Policy & legal adviser backed by TypeSafe Jev (typed judgments, not generated text).

Jev does not write a proposal; it *selects*. One request asks, over the same bounded case view:

  objection           whether the evidence or case facts give a concrete reason not to take the step (Noul)
  basis_chunk         which retrieved chunk governs the step (Choice over chunk ids, or NONE)
  alternative         which action the evidence supports if the step is not taken (Choice over the action set)

so every citation is, by construction, a chunk the retriever returned, and the rationale is the
probability distribution itself rather than prose that could be confabulated. The guard
(`app.advisers.guard.advise`) still applies residency, grounding and jurisdiction checks, and the
gate decides without reading the proposal.

Responses are recorded under evaluation/agent_runs/ and replayed when no TYPESAFE_API_KEY is set.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.advisers.base import AdvisoryProposal
from app.models.schemas import RecommendedAction

ENDPOINT = os.environ.get("TYPESAFE_URL", "https://api.typesafe.ai/v1/systemone")
RUNS = Path(__file__).resolve().parents[2] / "evaluation" / "agent_runs"

ACTIONS = {
    "SEND_PRIMARY": "Send the result notification on the approved primary channel.",
    "AWAIT_EVIDENCE": "Wait: a receipt or other required evidence has not arrived yet.",
    "RECONCILE_ATTEMPT": "Ask the provider what happened to an attempt whose outcome is unknown before doing anything else.",
    "RETRY_SAME_CHANNEL": "Retry on the same channel (only after the earlier attempt is reconciled).",
    "PROPOSE_FALLBACK": "Propose an alternative channel, which needs an approved fallback procedure.",
    "AWAIT_ACKNOWLEDGMENT": "Delivery is evidenced; wait for the patient's acknowledgment of the current result version.",
    "RECORD_DOCUMENTATION": "The communication is evidenced end to end; record it as required.",
    "OPEN_CORRECTION_TASK": "The result was corrected; cancel stale messages and open a reviewed correction task.",
    "ESCALATE_HUMAN": "Identity, scope, wording or next step is uncertain; hand to the named supervisor.",
    "VERIFY_RECIPIENT": "The recipient or contact is not verified; verify before sending.",
    "NO_ACTION": "Nothing should be done at this step.",
}


def _post(body: dict) -> dict:
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


@dataclass
class JevAdviser:
    model: str = os.environ.get("RESULTRELAY_JEV_MODEL", "jev-latest")
    endpoint: str = ENDPOINT
    name: str = "typesafe-jev"

    def propose(self, *, jurisdiction: str, situation: str, evidence: list[dict]) -> AdvisoryProposal:
        chunks = {c["chunk_id"]: c for c in evidence[:8] if isinstance(c, dict) and c.get("chunk_id")}
        basis = {cid: f"[{c.get('jurisdiction')}] {c.get('section_id')}: {(c.get('text') or '')[:260]}" for cid, c in chunks.items()}
        basis["NONE"] = "None of the retrieved passages supports a specific action."
        state = {"jurisdiction": jurisdiction, "situation": situation,
                 "retrieved_evidence": [{"chunk_id": cid, "jurisdiction": c.get("jurisdiction"),
                                         "class": c.get("claim_classification"), "section": c.get("section_id"),
                                         "text": (c.get("text") or "")[:500]} for cid, c in chunks.items()],
                 "note": "Synthetic laboratory exercise. You advise; a deterministic gate decides."}
        under_review = (json.loads(situation).get("action_under_review") if situation.strip().startswith("{") else None)
        questions = {
            "objection": {"type": "noul", "instructions":
                "As policy and legal reviewer for a walk-in laboratory: do the `retrieved_evidence` or the case facts in "
                "`situation` give a concrete reason NOT to take `situation.action_under_review` now? Concrete reasons "
                "include: treating a transport acceptance as delivery, an acknowledgment for an older result revision, "
                "a result scope the shown clauses route elsewhere, an unverified recipient, an unapproved channel, or a "
                "retry before the earlier attempt is reconciled. The absence of a clause that names this exact step is "
                "not by itself a reason.",
                "criteria": {"true": "A concrete objection exists", "false": "No concrete objection"}},
            "basis_chunk": {"type": "choice", "criteria": basis, "instructions":
                "Which retrieved passage most directly governs `situation.action_under_review`?"},
            "alternative": {"type": "choice", "criteria": ACTIONS, "instructions":
                "If the action under review were not taken, which action would the evidence support instead?"},
        }
        resp = self._ask(state, questions)
        a = resp["answers"]
        # Verify-for-objection: the earlier form asked whether the evidence positively *supports* each step,
        # and endorsed 0 of 23 gate actions, because routine steps (wait for a receipt) have no clause naming
        # them. A legal reviewer looks for a reason not to act; that is what is asked now.
        p_ok = 1 - a["objection"]["noul"]
        pick = a["basis_chunk"]["choice"]
        if under_review in ACTIONS and p_ok >= 0.5:
            action, conf = under_review, p_ok
        elif p_ok < 0.5 and a["alternative"]["choice"] != under_review:
            action, conf = a["alternative"]["choice"], 1 - p_ok
        else:
            action, conf = "ESCALATE_HUMAN", 1 - p_ok
        rationale = (f"reviewed {under_review}: objection p={1 - p_ok:.2f}; basis {pick} "
                     f"(p={a['basis_chunk']['confidence']:.2f}); alternative {a['alternative']['choice']} "
                     f"(p={a['alternative']['confidence']:.2f})")
        return AdvisoryProposal(
            candidate_action=RecommendedAction(action),
            rationale=rationale[:400],
            citation_chunk_ids=() if pick == "NONE" else (pick,),
            confidence=float(conf),
            is_model_generated=True,
        )

    def _ask(self, state: dict, questions: dict) -> dict:
        digest = hashlib.sha256(json.dumps([state, questions], sort_keys=True).encode()).hexdigest()[:20]
        path = RUNS / f"jev-{digest}.json"
        if os.environ.get("TYPESAFE_API_KEY") and os.environ.get("RESULTRELAY_ADVISE_REPLAY") != "1":
            resp = _post({"model": self.model, "state": state, "questions": questions})
            RUNS.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"state": state, "questions": questions, "response": resp}, ensure_ascii=False, indent=1),
                            encoding="utf-8")
            return resp
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["response"]
        raise RuntimeError("no TYPESAFE_API_KEY and no recorded response for this exact case view")
