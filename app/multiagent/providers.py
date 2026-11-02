"""Model providers for the agents: one typed-question interface, any backend.

Every agent asks *typed questions* - a choice among named options, a noul (a probability that a
statement is true) or a score on a named scale - over a JSON case view. The same question set runs on:

  ollama     local, e.g. qwen2.5:14b as in the ITU reference stack (OpenAI-compatible /v1)
  mistral    https://api.mistral.ai/v1 (MISTRAL_API_KEY)
  openai     any OpenAI-compatible endpoint: vLLM, LM Studio, Azure, Groq ... (RESULTRELAY_AGENT_URL)
  jev        TypeSafe Jev, which answers typed questions natively with calibrated probabilities
  replay     recorded answers only (the default offline mode)

Chat models are asked to return the answers as one JSON object; every answer is validated against its
question (a choice must be one of the named options, a probability must be in [0, 1]). An answer that
fails validation is not repaired or guessed: the question is marked invalid and the agent reports it,
which the coordinator treats as missing evidence.

Before any request, the endpoint goes through the residency guard (Federal Law 2/2019 Art. 13): a
synthetic case may use a hosted model; a real case is refused unless the endpoint is in the State or a
resolution is recorded. Every request and response is recorded under evaluation/agent_runs/ and can be
replayed offline; a replay is refused if the question set or the case view changed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.advisers.residency import authorise

RUNS = Path(__file__).resolve().parents[2] / "evaluation" / "agent_runs"

PRESETS = {
    "ollama": {"url": "http://localhost:11434/v1", "model": "qwen2.5:14b", "key_env": None},
    "mistral": {"url": "https://api.mistral.ai/v1", "model": "mistral-small-latest", "key_env": "MISTRAL_API_KEY"},
    "openai": {"url": None, "model": None, "key_env": "OPENAI_API_KEY"},
    "jev": {"url": "https://api.typesafe.ai/v1/systemone", "model": "jev-latest", "key_env": "TYPESAFE_API_KEY"},
}

SYSTEM = (
    "You are one agent in a multi-agent review of a synthetic laboratory result-communication case in "
    "the UAE. You speak only for the mandate you are given and only from the evidence you are shown. "
    "Answer every question. Return ONE JSON object and nothing else, shaped as "
    '{"answers": {"<question id>": {"choice": "<one option id>", "confidence": <0..1>}  for choice questions, '
    '"<question id>": {"noul": <probability 0..1 that the statement is true>}  for noul questions, '
    '"<question id>": {"score": <number on the given scale>}  for score questions}}. '
    "Use the exact option ids given. Do not add commentary."
)


class ProviderError(RuntimeError):
    pass


@dataclass
class Provider:
    kind: str
    url: str
    model: str
    key_env: str | None = None

    @property
    def label(self) -> str:
        return f"{self.kind}:{self.model}"

    # -- transport ---------------------------------------------------------------------------------
    def _post(self, url: str, body: dict, timeout: float = 180.0) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.key_env:
            key = os.environ.get(self.key_env)
            if not key:
                raise ProviderError(f"{self.key_env} is not set")
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - endpoint vetted by residency
            return json.loads(r.read())

    def _ask_live(self, state: dict, questions: dict) -> dict:
        if self.kind == "jev":
            return self._post(self.url, {"model": self.model, "state": state, "questions": questions})
        body = {
            "model": self.model, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": json.dumps({"state": state, "questions": questions},
                                                                ensure_ascii=False)}],
        }
        resp = self._post(self.url.rstrip("/") + "/chat/completions", body)
        text = resp["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ProviderError("model returned no JSON object")
        parsed = json.loads(m.group(0))
        return {"answers": parsed.get("answers", parsed)}

    # -- public ------------------------------------------------------------------------------------
    def ask(self, state: dict, questions: dict, *, data_class: str) -> tuple[dict, list[str]]:
        """Answer typed questions. Returns (validated answers, list of invalid question ids)."""
        # Keyed on what was asked, not who answered, so a replay can serve any provider's recording; the
        # file name and the stored "provider" field say which model produced it.
        digest = hashlib.sha256(json.dumps([state, questions], sort_keys=True).encode()).hexdigest()[:20]
        path = RUNS / f"agent-{self.kind}-{digest}.json"
        live = self.kind != "replay" and os.environ.get("RESULTRELAY_AGENT_REPLAY") != "1"
        if live:
            decision = authorise(self.url, os.environ.get("RESULTRELAY_RESIDENCY_RESOLUTION") or None,
                                 data_class=data_class)
            if not decision.permitted:
                raise PermissionError(decision.reason)
            raw = self._ask_live(state, questions)
            RUNS.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"provider": self.label, "state": state, "questions": questions,
                                        "response": raw}, ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            source = os.environ.get("RESULTRELAY_AGENT_REPLAY_FROM", "*")  # e.g. jev, mistral, ollama
            hits = sorted(RUNS.glob(f"agent-{source}-{digest}.json")) if self.kind == "replay" else [path]
            hits = [h for h in hits if h.exists()]
            if not hits:
                raise ProviderError("no recorded answer for this exact case view (replay is refused, not guessed)")
            raw = json.loads(hits[0].read_text(encoding="utf-8"))["response"]
        return validate(raw.get("answers", {}), questions)


def validate(answers: dict, questions: dict) -> tuple[dict, list[str]]:
    out, invalid = {}, []
    for qid, q in questions.items():
        a = answers.get(qid)
        try:
            if q["type"] == "choice":
                # Small local models often answer a bare option id, or use "answer"/"value": accept those
                # shapes, but the option itself must still be one of the named ids.
                choice = a if isinstance(a, str) else (a.get("choice") or a.get("answer") or a.get("value"))
                a = a if isinstance(a, dict) else {}
                if choice not in q["criteria"]:
                    raise ValueError(choice)
                out[qid] = {"choice": choice, "confidence": float(min(1, max(0, a.get("confidence", 0.5))))}
            elif q["type"] == "noul":
                p = float(next(a[k] for k in ("noul", "probability", "value", "answer") if k in a) if isinstance(a, dict) else a)
                if not 0 <= p <= 1:
                    raise ValueError(p)
                out[qid] = {"noul": p}
            else:  # score
                levels = q["criteria"]
                s = float(a["score"] if isinstance(a, dict) else a)
                out[qid] = {"score": max(0.0, min(float(len(levels) - 1), s))}
        except (KeyError, TypeError, ValueError):
            invalid.append(qid)
    return out, invalid


def load_dotenv(path: Path | None = None) -> None:
    """Read KEY=VALUE lines from the repo's .env (git-ignored) without overriding the real environment."""
    path = path or Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def configured() -> Provider | None:
    """Provider from the environment (and .env), or None when agents are off."""
    load_dotenv()
    kind = os.environ.get("RESULTRELAY_AGENT_PROVIDER", "").lower()
    if not kind:
        return None
    if kind == "replay":
        return Provider("replay", "", os.environ.get("RESULTRELAY_AGENT_MODEL", "recorded"))
    if kind not in PRESETS:
        raise ProviderError(f"unknown RESULTRELAY_AGENT_PROVIDER {kind!r}; use one of {sorted(PRESETS)} or replay")
    p = PRESETS[kind]
    url = os.environ.get("RESULTRELAY_AGENT_URL") or p["url"]
    model = os.environ.get("RESULTRELAY_AGENT_MODEL") or p["model"]
    if not url or not model:
        raise ProviderError("set RESULTRELAY_AGENT_URL and RESULTRELAY_AGENT_MODEL for the openai provider")
    return Provider(kind, url, model, p["key_env"])
