"""Export the verified knowledge base in the ITU reference-code format, and optionally ingest it.

    python scripts/export_itu_kb.py                          # writes kb/itu_inputdocs/*.txt + manifest.json
    python scripts/export_itu_kb.py --ingest PATH/TO/ITUAIReadiness   # + ChromaDB via the ITU ingest.py

The ITU reference code (github.com/CrashingGuru/ITUAIReadiness, simulation/server/knowledge/ingest.py)
reads InputDocs/, chunks, embeds with Ollama nomic-embed-text and stores in ChromaDB with metadata.
Each verified clause becomes one InputDoc whose provenance travels as ChromaDB metadata (clause id,
authority, jurisdiction, version, URL, Y.3172 node), so a vector hit can always be traced back to the
exact quoted text. Files are named <COUNTRY>_<id>.txt because the reference infers `country` from the
filename. Only verified records are exported.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "kb" / "itu_inputdocs"


def _records() -> list[dict]:
    """Yield {id, country, text, meta} from whichever corpus format this repository carries."""
    heat = ROOT / "kb" / "records" / "sources.json"
    relay = ROOT / "kb" / "index" / "chunks.json"
    out = []
    if heat.exists():  # HeatShift: clause register
        reg = json.loads(heat.read_text(encoding="utf-8"))
        for s in reg["sources"]:
            if s.get("retrieval_status") == "not_retrieved":
                continue
            uae = "Emirates" in s.get("jurisdiction", "") or "Abu Dhabi" in s.get("jurisdiction", "")
            for c in s.get("clauses", []):
                out.append({"id": c["clause_id"], "country": "UAE" if uae else "GLOBAL",
                            "text": f"{s['title']}\n{c.get('heading', '')}\n\n{c['quote']}",
                            "meta": {"clause_id": c["clause_id"], "source_id": s["source_id"], "authority": s.get("publisher", ""),
                                     "jurisdiction": s.get("jurisdiction", ""), "version": s.get("version", ""),
                                     "url": s.get("url", ""), "authority_level": s.get("authority_level", ""),
                                     "project": "HeatShift"}})
    elif relay.exists():  # ResultRelay: verified excerpt index
        idx = json.loads(relay.read_text(encoding="utf-8"))
        for c in idx["chunks"]:
            if c.get("verification_result") not in (None, "VERIFIED_AGAINST_SOURCE"):
                continue
            uae = str(c.get("jurisdiction", "")).startswith("AE")
            out.append({"id": c["chunk_id"], "country": "UAE" if uae else "GLOBAL",
                        "text": f"{c['title']} — {c.get('section_id', '')} (p.{c.get('page_start', '')})\n\n{c['text']}",
                        "meta": {"clause_id": c["chunk_id"], "source_id": c["source_id"], "authority": c.get("issuer", ""),
                                 "jurisdiction": c.get("jurisdiction", ""), "claim_class": c.get("claim_classification", ""),
                                 "section": c.get("section_id", ""), "page": c.get("page_start", ""),
                                 "url": c.get("source_url", ""), "project": "ResultRelay"}})
    return out


def export() -> list[tuple[Path, dict]]:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.txt"):
        old.unlink()
    written = []
    for r in _records():
        name = f"{r['country']}_{re.sub(r'[^A-Za-z0-9.-]+', '-', r['id'])}.txt"
        p = OUT / name
        p.write_text(r["text"], encoding="utf-8")
        written.append((p, r["meta"]))
    (OUT / "manifest.json").write_text(json.dumps({"format": "ITUAIReadiness InputDocs (one verified clause per file)",
                                                   "count": len(written),
                                                   "files": {p.name: m for p, m in written}}, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    return written


def ingest(ref: Path, written: list[tuple[Path, dict]], collection: str) -> int:
    sys.path.insert(0, str(ref / "simulation"))
    from server.knowledge.ingest import ingest_file  # type: ignore  # ITU reference code
    from server.knowledge.kb import KnowledgeBase  # type: ignore

    store = ROOT / "kb" / "chroma"
    kb = KnowledgeBase(persist_dir=str(store))
    try:  # rebuild, never append: the ITU ingest gives every chunk a fresh uuid, so a re-run would duplicate
        kb.delete_collection(collection)
    except Exception:  # noqa: BLE001 - first build: nothing to delete
        pass
    return sum(ingest_file(p, kb, collection, extra_metadata=m) for p, m in written)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest", type=Path, help="path to a clone of CrashingGuru/ITUAIReadiness (needs chromadb + Ollama)")
    ap.add_argument("--collection", default="policies")
    a = ap.parse_args()
    w = export()
    print(f"exported {len(w)} verified clauses to {OUT.relative_to(ROOT)}")
    if a.ingest:
        print(f"ingested {ingest(a.ingest, w, a.collection)} chunks into ChromaDB at kb/chroma via the ITU reference ingest.py")
