"""Does the ITU-built vector store help on plain-language questions?

    python scripts/retrieval_check.py        # needs kb/chroma (export_itu_kb.py --ingest) and Ollama running

Seven paraphrased questions, written by the authors, each with the clause a reader would expect. Reports
whether that clause is in the top 5 for BM25 alone and for hybrid (BM25 fused with ChromaDB /
nomic-embed-text). Small and self-written: a smoke test of recall, not a benchmark.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.kb import retriever, vector  # noqa: E402

QUESTIONS = [
    ("send health data abroad cloud", "U1-art13"),
    ("can we use an LLM hosted overseas for patient messages", "U1-art13"),
    ("text message reached the phone but did anyone read it", "G5-6"),
    ("how long do we keep the message logs", "retention"),
    ("can the AI decision be overruled by staff", "U6-4.4.2"),
    ("should a dangerous lab value go to the patient or their doctor", "G5-8"),
    ("who checks the AI before it is used", "U6-4.3.3"),
]


def main() -> int:
    if not vector.available():
        print("vector store not built: run scripts/export_itu_kb.py --ingest PATH/TO/ITUAIReadiness first")
        return 1
    rows, hits = [], {"bm25": 0, "hybrid": 0}
    for q, want in QUESTIONS:
        got = {}
        for engine in hits:
            ids = [c.chunk_id for c in retriever.search(q, top_k=5, engine=engine).chunks]
            got[engine] = any(want in i for i in ids)
            hits[engine] += got[engine]
        rows.append(f"| {q} | `{want}` | {'hit' if got['bm25'] else 'miss'} | {'hit' if got['hybrid'] else 'miss'} |")
    out = ["# Retrieval check: BM25 vs hybrid (BM25 + ChromaDB, ITU reference ingest)", "",
           "| Question | Expected clause | BM25 top-5 | Hybrid top-5 |", "| :--- | :--- | :---: | :---: |", *rows, "",
           f"Top-5 hits: BM25 {hits['bm25']}/{len(QUESTIONS)}, hybrid {hits['hybrid']}/{len(QUESTIONS)}. "
           "Questions and expected clauses written by the authors."]
    (ROOT / "evaluation" / "retrieval_check.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
