"""Semantic ranking over the ChromaDB store built by the ITU reference ingest.

``scripts/export_itu_kb.py --ingest PATH/TO/ITUAIReadiness`` writes every verified excerpt to
``kb/itu_inputdocs/`` and runs the ITU reference ``ingest.py`` (Ollama ``nomic-embed-text`` embeddings,
ChromaDB, cosine space) into ``kb/chroma``. This module only *ranks*: it returns clause ids in order of
semantic similarity. The retriever then takes the chunks themselves from the verified, SHA-pinned
index, so a vector hit that does not map to a verified excerpt is dropped and nothing the vector store
returns is ever quoted directly. Grounding is unchanged; recall on paraphrased questions improves.

Optional: if chromadb, the Ollama client, the store or the Ollama server is missing, ``rank`` returns
None and the retriever stays on BM25 alone.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORE = Path(os.environ.get("RESULTRELAY_CHROMA_DIR", ROOT / "kb" / "chroma"))
COLLECTION = os.environ.get("RESULTRELAY_CHROMA_COLLECTION", "policies")
OLLAMA = os.environ.get("RESULTRELAY_OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("RESULTRELAY_EMBED_MODEL", "nomic-embed-text")


@lru_cache(maxsize=1)
def _collection():
    if not STORE.exists():
        return None
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        return None
    client = chromadb.PersistentClient(path=str(STORE), settings=Settings(anonymized_telemetry=False))
    try:
        return client.get_collection(COLLECTION)
    except Exception:  # noqa: BLE001 - collection absent means "not built"
        return None


def available() -> bool:
    return _collection() is not None


def rank(query: str, n: int = 40) -> list[str] | None:
    """Clause ids ordered by semantic similarity, or None when the vector store cannot be used."""
    col = _collection()
    if col is None:
        return None
    try:
        import ollama

        emb = ollama.Client(host=OLLAMA).embed(model=EMBED_MODEL, input=[query])["embeddings"][0]
        res = col.query(query_embeddings=[emb], n_results=min(n, col.count() or 1), include=["metadatas"])
    except Exception:  # noqa: BLE001 - server down: fall back to lexical ranking
        return None
    seen: list[str] = []
    for meta in res.get("metadatas", [[]])[0]:
        cid = (meta or {}).get("clause_id")
        if cid and cid not in seen:
            seen.append(cid)
    return seen
