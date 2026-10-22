"""Deterministic retrieval over the verified excerpt index.

A small BM25 implementation, on purpose:

* no embedding service means no network dependency, no key handling and no non-determinism in an
  evaluation that claims replayability;
* the corpus is ~44 verified excerpts, where the ranking is dominated by the applicability
  filter, not by semantic similarity.

The applicability filter is the load-bearing part and is deliberately separate from scoring:
``scope="applicable"`` is how an agent says "give me only evidence that governs this case";
``scope="comparator"`` returns out-of-jurisdiction material that a caller may discuss but must
never apply; ``scope="all"`` returns both, and the caller owns the distinction.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from app.models.schemas import EvidenceChunk, RetrievalResult

ROOT = Path(__file__).resolve().parents[3]
INDEX_PATH = ROOT / "knowledge_base" / "index" / "chunks.json"

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


@lru_cache(maxsize=1)
def _load_index(index_path: str | None = None) -> BM25:
    path = Path(index_path) if index_path else INDEX_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"knowledge-base index not found at {path}. Run `python -m app.kb.ingest` "
            "(or `make kb`) to build it."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return BM25(payload["chunks"])


def reload_index() -> None:
    _load_index.cache_clear()
    _index_sha256_cached.cache_clear()


@lru_cache(maxsize=1)
def _index_sha256_cached(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        return ""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload.get("index_sha256") or "")


def index_sha256() -> str:
    """Hash of the policy index in force.

    Recorded on every audit entry so that a decision can be tied to the corpus that produced it.
    Before this, the index was a single mutable file with no version pin: rebuilding it silently
    changed what past decisions would be made from (audit item A8).
    """
    return _index_sha256_cached(str(INDEX_PATH))


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
            "engine": "bm25",
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
