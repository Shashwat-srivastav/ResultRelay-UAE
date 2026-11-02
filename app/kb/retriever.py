"""Deterministic retrieval over the verified excerpt index.

A small BM25 implementation, on purpose:

* no embedding service means no network dependency, no key handling and no non-determinism in an
  evaluation that claims replayability;
* the corpus is 63 verified excerpts, where the ranking is dominated by the applicability
  filter, not by semantic similarity.

The applicability filter is the load-bearing part and is deliberately separate from scoring:
``scope="applicable"`` is how an agent says "give me only evidence that governs this case";
``scope="comparator"`` returns out-of-jurisdiction material that a caller may discuss but must
never apply; ``scope="all"`` returns both, and the caller owns the distinction.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from app.models.schemas import EvidenceChunk, RetrievalResult

ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "kb" / "index" / "chunks.json"

STOPWORDS = set(
    """a an and are as at be been but by for from had has have how in into is it its may must no
    not of on or our shall should so such that the their then there these they this to was were
    what when which who will with within would""".split()
)


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


class BM25:
    def __init__(self, chunks: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.docs = [tokenize(self._doc_text(c)) for c in chunks]
        self.lengths = [len(d) for d in self.docs]
        self.avgdl = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.tf = [Counter(d) for d in self.docs]
        self.df: Counter[str] = Counter()
        for doc in self.docs:
            for term in set(doc):
                self.df[term] += 1
        self.n = len(self.docs)

    @staticmethod
    def _doc_text(chunk: dict[str, Any]) -> str:
        # Section identifiers and topic tags are searchable: a reviewer looking for "11.1.3"
        # should get the clause, not a semantic neighbour of it.
        return " ".join([chunk["text"], chunk["section_id"], " ".join(chunk.get("topics", []))])

    def idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def score(self, query_tokens: list[str], idx: int) -> tuple[float, list[str]]:
        tf, dl = self.tf[idx], self.lengths[idx] or 1
        total = 0.0
        matched: list[str] = []
        for term in query_tokens:
            f = tf.get(term, 0)
            if not f:
                continue
            matched.append(term)
            denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
            total += self.idf(term) * (f * (self.k1 + 1)) / denom
        return total, matched


#: The committed pin for the served index. It lives beside the index but is *not* the index: a
#: hash stored inside the file it protects proves nothing, because editing the file edits the hash
#: with it (red-team finding H-3).
PIN_PATH = INDEX_PATH.parent / "pinned.sha256"


def compute_index_sha256(chunks: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(chunks, sort_keys=True).encode("utf-8")).hexdigest()


def _deep_quote_check(chunks: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    """Re-check every excerpt against the cached source text.

    This is the same check ``app.kb.ingest`` performs when it builds the index, run again against
    what is actually being served. Without it the health endpoint repeated a build-time summary
    from a mutable file and reported 63/63 verified for a corpus that had been tampered with.
    """
    from app.kb.ingest import load_pages, verify_excerpt  # local import: ingest imports this module

    pages_cache: dict[str, dict[int, str] | None] = {}
    mismatches: list[dict[str, Any]] = []
    not_reverifiable: list[str] = []
    verified = 0
    for chunk in chunks:
        source_id = chunk.get("source_id", "")
        if source_id not in pages_cache:
            pages_cache[source_id] = load_pages(source_id)
        if pages_cache[source_id] is None:
            # A fresh clone has no source cache (the texts are not redistributed). That is not
            # evidence of tampering: the pinned hash below still binds the served corpus to the
            # reviewed one. Report the excerpt as not re-verifiable here instead of as a mismatch.
            not_reverifiable.append(chunk.get("chunk_id"))
            continue
        status, detail = verify_excerpt(chunk, pages_cache[source_id])
        if status == "VERIFIED_AGAINST_SOURCE":
            verified += 1
        else:
            mismatches.append({"chunk_id": chunk.get("chunk_id"), "status": status, "detail": detail})
    _deep_quote_check.last_not_reverifiable = not_reverifiable
    return verified, mismatches


@lru_cache(maxsize=1)
def corpus_integrity(index_path: str | None = None) -> dict[str, Any]:
    """Live integrity state of the served corpus.

    Three independent checks, all recomputed here rather than read from the file's own claims:
    the chunk list hashes to the committed pin, every excerpt still matches the cached source text,
    and the count matches. ``ok`` is what callers gate on.
    """
    path = Path(index_path) if index_path else INDEX_PATH
    pin_path = path.parent / "pinned.sha256"
    report: dict[str, Any] = {
        "index_path": str(path),
        "pin_path": str(pin_path),
        "chunk_count": 0,
        "declared_sha256": "",
        "recomputed_sha256": "",
        "pinned_sha256": "",
        "hash_matches_pin": False,
        "declared_matches_recomputed": False,
        "quotes_checked": 0,
        "quotes_verified": 0,
        "quote_mismatches": [],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ok": False,
        "reason": "",
    }
    if not path.exists():
        report["reason"] = f"index not found at {path}"
        return report

    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks = payload.get("chunks", [])
    declared = str(payload.get("index_sha256") or "")
    recomputed = compute_index_sha256(chunks)
    pinned = pin_path.read_text(encoding="utf-8").strip() if pin_path.exists() else ""

    verified, mismatches = _deep_quote_check(chunks)

    report.update({
        "chunk_count": len(chunks),
        "declared_sha256": declared,
        "recomputed_sha256": recomputed,
        "pinned_sha256": pinned,
        "hash_matches_pin": bool(pinned) and recomputed == pinned,
        "declared_matches_recomputed": bool(declared) and declared == recomputed,
        "quotes_checked": len(chunks),
        "quotes_verified": verified,
        "quote_mismatches": mismatches,
        "quotes_not_reverifiable_here": len(getattr(_deep_quote_check, "last_not_reverifiable", [])),
        "reverify_hint": "run `python scripts/fetch_sources.py` to download the official texts and re-check every quote",
    })

    problems = []
    if not pinned:
        problems.append(
            "no pinned index hash: the served corpus cannot be shown to be the reviewed one "
            "(run `make kb` to write kb/index/pinned.sha256)"
        )
    elif recomputed != pinned:
        problems.append(
            f"served index hash {recomputed[:16]}… does not match the pinned hash {pinned[:16]}…"
        )
    if mismatches:
        problems.append(f"{len(mismatches)} excerpt(s) no longer match the cached source text")
    report["ok"] = not problems
    report["reason"] = "; ".join(problems)
    return report


def _load_index(index_path: str | None = None) -> BM25:
    """Load the index, refusing to serve a corpus that fails verification.

    The corpus is the authority in this system, so a corpus that silently changed under the code is
    a worse failure than an unavailable service. ``RESULTRELAY_ALLOW_UNVERIFIED_KB=1`` exists for
    demos of an unverified corpus and is reported as such by ``/api/health``.
    """
    if index_path is None:
        integrity = corpus_integrity()
        if not integrity["ok"] and not os.environ.get("RESULTRELAY_ALLOW_UNVERIFIED_KB"):
            raise RuntimeError(
                "the policy index failed verification and will not be served: "
                + integrity["reason"]
                + ". Rebuild with `make kb`, or set RESULTRELAY_ALLOW_UNVERIFIED_KB=1 to run an "
                "explicitly unverified corpus (the health endpoint will say so)."
            )
    return _load_index_uncached(index_path)


@lru_cache(maxsize=1)
def _load_index_uncached(index_path: str | None = None) -> BM25:
    path = Path(index_path) if index_path else INDEX_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"knowledge-base index not found at {path}. Run `python -m app.kb.ingest` "
            "(or `make kb`) to build it."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return BM25(payload["chunks"])


def reload_index() -> None:
    corpus_integrity.cache_clear()
    _load_index_uncached.cache_clear()


def index_sha256() -> str:
    """Hash of the policy corpus actually being served.

    Recomputed from the chunks in force, so it changes the moment the served content changes.
    Recorded on every audit entry so a decision can be tied to the corpus that produced it
    (audit item A8); the pinned file is what makes tampering visible (red-team finding H-3).
    """
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        return compute_index_sha256(payload.get("chunks", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


#: Jurisdictions that bind a case, layered rather than exclusive.
#:
#: A Dubai case is governed by Dubai instruments *and* by federal law: federal statutes (the ICT
#: Health Law, Federal Law 2/2019) apply in every emirate, including the free zones. Treating
#: jurisdiction as a single label would have silently excluded the national instrument, which is
#: the one that actually governs health data. The reverse is not true: a Dubai policy never binds
#: an Abu Dhabi case, so the map only ever widens upwards.
JURISDICTION_LAYERS: dict[str, frozenset[str]] = {
    "AE-DU": frozenset({"AE-DU", "AE-FED"}),
    "AE-AZ": frozenset({"AE-AZ", "AE-FED"}),
    "AE-FED": frozenset({"AE-FED"}),
}


def applicable_jurisdictions(case_jurisdiction: str | None) -> set[str] | None:
    """Expand a case jurisdiction into every jurisdiction that can bind it."""
    if not case_jurisdiction:
        return None
    out: set[str] = set()
    for jur in (j.strip() for j in case_jurisdiction.split(",")):
        if jur:
            out |= set(JURISDICTION_LAYERS.get(jur, {jur}))
    return out or None


def all_chunks() -> list[dict[str, Any]]:
    return _load_index().chunks


def search(
    query: str,
    *,
    jurisdiction: str | None = None,
    claim_classifications: Iterable[str] | None = None,
    source_ids: Iterable[str] | None = None,
    scope: str = "all",  # all | applicable | comparator
    top_k: int = 6,
    min_score: float = 0.0,
    engine: str | None = None,  # bm25 | hybrid (default from RESULTRELAY_RETRIEVAL, else bm25)
) -> RetrievalResult:
    """Rank the corpus, then apply filters.

    ``scope`` is the applicability axis and is deliberately independent of the score:

      * ``applicable``  - only sources whose jurisdiction can bind the case jurisdiction, which
                          includes the federal layer above it (see ``JURISDICTION_LAYERS``)
      * ``comparator``  - only sources that cannot bind it
      * ``all``         - everything, with each chunk's jurisdiction carried on the result
    """
    idx = _load_index()
    query_tokens = tokenize(query)
    filtered: list[int] = []
    excluded = 0
    notes: list[str] = []

    jurs = applicable_jurisdictions(jurisdiction)
    claims = {str(c) for c in claim_classifications} if claim_classifications else None
    sids = {s for s in source_ids} if source_ids else None

    for i, chunk in enumerate(idx.chunks):
        if sids is not None and chunk["source_id"] not in sids:
            excluded += 1
            continue
        if claims is not None and chunk["claim_classification"] not in claims:
            excluded += 1
            continue
        same_jurisdiction = jurs is not None and chunk["jurisdiction"] in jurs
        if scope == "applicable" and jurs is not None and not same_jurisdiction:
            excluded += 1
            continue
        if scope == "comparator" and jurs is not None and same_jurisdiction:
            excluded += 1
            continue
        filtered.append(i)

    scored: list[tuple[float, int, list[str]]] = []
    for i in filtered:
        s, matched = idx.score(query_tokens, i)
        if s > min_score:
            scored.append((s, i, matched))
    scored.sort(key=lambda x: (-x[0], idx.chunks[x[1]]["chunk_id"]))

    engine = (engine or os.environ.get("RESULTRELAY_RETRIEVAL", "bm25")).lower()
    used = "bm25"
    if engine == "hybrid":
        from app.kb import vector

        semantic = vector.rank(query)
        if semantic is None:
            notes.append("hybrid retrieval requested but the ChromaDB store or Ollama is unavailable; BM25 only.")
        else:
            # Reciprocal-rank fusion. Candidates are the filtered *verified* chunks only: a semantic hit
            # outside the pinned index, or outside the requested filters, cannot enter the result.
            pos = {cid: r for r, cid in enumerate(semantic)}
            lexical = {i: r for r, (_, i, _) in enumerate(scored)}
            matched_terms = {i: m for _, i, m in scored}
            fused = []
            for i in filtered:
                cid = idx.chunks[i]["chunk_id"]
                if i not in lexical and cid not in pos:
                    continue
                f = (1 / (60 + lexical[i]) if i in lexical else 0) + (1 / (60 + pos[cid]) if cid in pos else 0)
                fused.append((round(f * 1000, 4), i, matched_terms.get(i, [])))
            fused.sort(key=lambda x: (-x[0], idx.chunks[x[1]]["chunk_id"]))
            scored, used = fused, "hybrid(bm25+chromadb:nomic-embed-text)"

    out: list[EvidenceChunk] = []
    for s, i, matched in scored[:top_k]:
        raw = idx.chunks[i]
        payload = {k: raw[k] for k in EvidenceChunk.model_fields if k in raw}
        payload["score"] = round(s, 4)
        payload["matched_terms"] = sorted(set(matched))
        out.append(EvidenceChunk(**payload))

    if excluded:
        notes.append(f"{excluded} chunk(s) excluded by the requested filters before scoring.")
    if scope == "applicable" and jurs and not out:
        notes.append(
            "No chunk from the case jurisdiction matched. Absence of a retrieved clause is NOT "
            "evidence that no obligation exists; the gap register records this as "
            "INSUFFICIENT_EVIDENCE."
        )
    if scope == "comparator":
        notes.append(
            "Comparator-scope results are from a different jurisdiction and can never be applied "
            "as a binding rule for this case."
        )
    return RetrievalResult(
        query=query,
        filters={
            "jurisdiction": jurisdiction,
            "claim_classifications": sorted(claims) if claims else None,
            "source_ids": sorted(sids) if sids else None,
            "scope": scope,
            "top_k": top_k,
            "engine": used,
        },
        chunks=out,
        considered=len(filtered),
        excluded_by_filter=excluded,
        notes=notes,
    )


def retrieval_manifest() -> dict[str, Any]:
    payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {
        "built_at": payload["built_at"],
        "chunk_count": payload["chunk_count"],
        "sources": payload["sources"],
        "verification": {k: v for k, v in payload["verification"].items() if k != "details"},
        "engine": "bm25 (k1=1.5, b=0.75), deterministic, no external service",
    }
