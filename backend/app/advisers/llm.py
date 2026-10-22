"""An OpenAI-compatible adviser client, local-first and offline by default.

Why a request/response adapter rather than an SDK: the only endpoint this system may legally use is
one inside the State (Federal Law 2/2019, Art. 13 — see :mod:`app.advisers.residency`), which in
practice means a self-hosted or in-country inference server speaking an OpenAI-compatible API. An
SDK would pull in a vendor default endpoint and a dependency the review flagged as absent; a narrow
adapter is small enough to audit and easy to point at a local server.

Nothing here makes a network call unless it is constructed with a transport. The default transport
refuses, so an unconfigured deployment cannot leak health data by accident.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

from app.advisers.base import AdvisoryProposal
from app.advisers.residency import authorise
from app.models.schemas import RecommendedAction

SYSTEM_PROMPT = """You are a policy adviser for a laboratory result-communication workflow in the \
United Arab Emirates. You do not decide anything: a deterministic gate decides.

Answer with ONE JSON object and nothing else:
{"candidate_action": "<one of %s>", "rationale": "<= 400 characters", "citation_chunk_ids": ["<chunk ids you used>"], "confidence": <0..1>}

Rules:
- Use only the evidence supplied. If it does not support an action, choose AWAIT_EVIDENCE.
- A clause that forbids something is not permission. If the evidence prohibits a channel, say so.
- Never propose an action because a channel failed; authorisation is separate from necessity.
""" % ", ".join(a.value for a in RecommendedAction)


class Transport(Protocol):
    def post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        ...


@dataclass
class RefusingTransport:
    """The default. No model endpoint is contacted unless one is supplied deliberately."""

    def post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        raise RuntimeError(
            "no model transport configured: this build does not contact a model endpoint. "
            "Supply a transport pointed at an in-country server to enable the adviser."
        )


@dataclass
class HttpTransport:
    """Minimal JSON-over-HTTP transport. Uses urllib so no client dependency is added."""

    timeout: float = 20.0

    def post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        import urllib.request

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))


@dataclass
class OpenAICompatibleAdviser:
    """An adviser over an OpenAI-compatible /chat/completions endpoint.

    The residency check is applied at construction: an endpoint outside the State is refused before
    any case data could be shaped into a request.
    """

    base_url: str
    model: str
    endpoint: str = "/chat/completions"
    transport: Transport = field(default_factory=RefusingTransport)
    resolution_ref: str | None = None
    name: str = "openai-compatible"

    def __post_init__(self) -> None:
        decision = authorise(self.base_url, self.resolution_ref)
        if not decision.permitted:
            raise PermissionError(decision.reason)
        host = urlparse(self.base_url).hostname or ""
        if host not in {"localhost", "127.0.0.1", "::1"} and not host.endswith(".ae"):
            raise PermissionError(f"endpoint host {host!r} is not inside the State")

    def _url(self) -> str:
        return self.base_url.rstrip("/") + self.endpoint

    def propose(self, *, jurisdiction: str, situation: str, evidence: list[dict]) -> AdvisoryProposal:
        snippet = [
            {
                "chunk_id": c.get("chunk_id"),
                "jurisdiction": c.get("jurisdiction"),
                "class": c.get("claim_classification"),
                "section": c.get("section_id"),
                "text": (c.get("text") or "")[:600],
            }
            for c in evidence[:8]
        ]
        user = json.dumps(
            {"jurisdiction": jurisdiction, "situation": situation, "evidence": snippet},
            ensure_ascii=False,
        )
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        }
        raw = self.transport.post(self._url(), body, {"Authorization": "Bearer not-required-locally"})
        text = _message_text(raw)
        data = json.loads(_first_json_object(text))
        action = data["candidate_action"]
        return AdvisoryProposal(
            candidate_action=RecommendedAction(action),
            rationale=str(data.get("rationale", ""))[:400],
            citation_chunk_ids=tuple(str(c) for c in data.get("citation_chunk_ids") or ()),
            confidence=float(data.get("confidence") or 0.0),
            is_model_generated=True,
        )


def _message_text(response: dict[str, Any]) -> str:
    try:
        return str(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"unexpected model response shape: {sorted(response)}") from exc


def _first_json_object(text: str) -> str:
    """Extract the first balanced JSON object, tolerating prose or a fenced block around it."""
    start = text.find("{")
    if start < 0:
        raise ValueError("model output contained no JSON object")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("model output contained an unterminated JSON object")
