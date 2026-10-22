"""Knowledge-base ingestion with verbatim quote verification.

Every excerpt in ``knowledge_base/excerpts/*.yaml`` claims that a document says a specific thing
on a specific printed page. This module checks that claim against the document's own text layer
before the excerpt is allowed into the index.

The check is deliberately mechanical and unforgiving:

* the quote is normalised (case, curly punctuation, all whitespace removed) and must appear as a
  contiguous substring of the declared page(s). Removing whitespace rather than collapsing it is
  what lets a quote survive a PDF extractor that breaks words mid-token ("identif ying");
* a quote that spans a page break must declare the range that contains it, so a wrong page number
  cannot be hidden by matching against the whole document;
* the check runs against ``pdf_page_start`` when the excerpt gives one (Y.3172's printed page N is
  PDF page N+6), because that is the numbering the text layer actually uses.

An excerpt whose source is not in the local cache is indexed but marked ``UNVERIFIED_NO_CACHE``
and counted separately; it is never reported as verified. An excerpt that fails the check is
excluded from the index outright, so a misquoted or mispaged clause cannot be cited.

Source documents are downloaded, not redistributed: see ``scripts/fetch_sources.py``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[3]
KB_DIR = ROOT / "knowledge_base"
REGISTER_CSV = KB_DIR / "source_register.csv"
EXCERPT_DIR = KB_DIR / "excerpts"
INDEX_PATH = KB_DIR / "index" / "chunks.json"
def _source_cache() -> Path:
    """Explicit override, then repo-local cache, then the user cache. See scripts/fetch_sources.py."""
    override = os.environ.get("RESULTRELAY_SOURCE_CACHE")
    if override:
        return Path(override)
    local = Path(__file__).resolve().parents[3] / "knowledge_base" / ".sources"
    if local.exists():
        return local
    return Path.home() / ".cache" / "resultrelay" / "sources"


SOURCE_CACHE = _source_cache()

PAGE_MARKER = re.compile(r"===== PAGE (\d+) =====")

REQUIRED_REGISTER_FIELDS = (
    "source_id", "title", "issuing_authority", "jurisdiction", "document_type",
    "version_or_issue", "publication_date", "official_url", "retrieved_at",
    "applicability", "legal_or_guidance_status", "license_or_reuse_notes",
    "verification_status",
)

# Register column -> chunk field. The chunk schema is what the agents and the UI read, so the
# mapping stays explicit rather than relying on identical names.
REGISTER_TO_CHUNK = {
    "title": "title",
    "issuing_authority": "issuer",
    "jurisdiction": "jurisdiction",
    "version_or_issue": "document_version",
    "publication_date": "publication_date",
    "effective_date": "effective_date",
    "document_type": "source_type",
    "official_url": "source_url",
}

_TRANSLATE = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2010": "-", "\u2011": "-",
    "\u00a0": " ", "\u2007": " ", "\u202f": " ", "\u00ad": "",
    "\ufb01": "fi", "\ufb02": "fl", "\u00b7": " ",
}


def _declared_flag(excerpt: dict[str, Any], *, chunk_id: str) -> bool:
    """Read a boolean authorisation declared on an excerpt, refusing anything ambiguous."""
    if "authorises_fallback" not in excerpt:
        return False
    value = excerpt["authorises_fallback"]
    if not isinstance(value, bool):
        raise ValueError(
            f"{chunk_id}: authorises_fallback must be a boolean, got {type(value).__name__}. "
            "An authorisation is declared, never inferred."
        )
    if value and excerpt.get("claim_classification") not in {"BINDING_REQUIREMENT", "INSTITUTIONAL_PROCEDURE"}:
        raise ValueError(
            f"{chunk_id}: authorises_fallback is claimed by a {excerpt.get('claim_classification')} "
            "excerpt. Guidance and comparators may shape a design; they cannot authorise an action."
        )
    return value


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _TRANSLATE.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", "", text.lower())


def load_pages(source_id: str) -> dict[int, str] | None:
    path = SOURCE_CACHE / f"{source_id}.txt"
    if not path.exists():
        return None
    body = path.read_text(encoding="utf-8", errors="replace")
    pages: dict[int, str] = {}
    current: int | None = None
    buf: list[str] = []
    for line in body.splitlines():
        m = PAGE_MARKER.match(line.strip())
        if m:
            if current is not None:
                pages[current] = "\n".join(buf)
            current = int(m.group(1))
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        pages[current] = "\n".join(buf)
    return pages or None


def load_register() -> dict[str, dict[str, str]]:
    if not REGISTER_CSV.exists():
        raise FileNotFoundError(f"source register not found at {REGISTER_CSV}")
    with REGISTER_CSV.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [f for f in REQUIRED_REGISTER_FIELDS if f not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"source register is missing columns: {missing}")
        rows = {r["source_id"].strip(): r for r in reader}
    for sid, row in rows.items():
        for field in REQUIRED_REGISTER_FIELDS:
            if not str(row.get(field, "")).strip():
                raise ValueError(f"source {sid}: register field {field!r} is empty")
    return rows


def load_excerpts() -> list[dict[str, Any]]:
    """Read every excerpt file into a flat list of (source, excerpt) pairs."""
    out: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for path in sorted(EXCERPT_DIR.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict) or "source_id" not in payload or "excerpts" not in payload:
            raise ValueError(f"{path.name}: expected a mapping with source_id and excerpts")
        source_id = payload["source_id"]
        for item in payload["excerpts"]:
            item["source_id"] = source_id
            item["_file"] = f"knowledge_base/excerpts/{path.name}"
            cid = item["chunk_id"]
            if cid in seen:
                raise ValueError(f"duplicate chunk_id {cid} in {path.name} and {seen[cid]}")
            seen[cid] = path.name
            for field in ("chunk_id", "section_id", "page_start", "claim_classification", "text"):
                if field not in item:
                    raise ValueError(f"{path.name}/{cid}: missing {field}")
            out.append(item)
    return out


def verify_excerpt(excerpt: dict[str, Any], pages: dict[int, str] | None) -> tuple[str, str]:
    if pages is None:
        return "UNVERIFIED_NO_CACHE", "source text not in local cache; quote not checked this run"

    start = int(excerpt.get("pdf_page_start", excerpt["page_start"]))
    end = int(excerpt.get("pdf_page_end", excerpt.get("page_end", start)))
    needle = normalise(excerpt["text"])
    if not needle:
        return "QUOTE_NOT_FOUND_IN_SOURCE", "excerpt text is empty"

    span = "".join(normalise(pages.get(p, "")) for p in range(start, end + 1))
    if span and needle in span:
        return "VERIFIED_AGAINST_SOURCE", f"matched contiguous text on PDF page(s) {start}-{end}"

    whole = "".join(normalise(p) for p in pages.values())
    if needle in whole:
        found = [p for p in sorted(pages) if needle in normalise(pages[p])]
        return (
            "QUOTE_NOT_FOUND_ON_DECLARED_PAGE",
            f"quote is present but on PDF page(s) {found}; excerpt declares {start}-{end}",
        )
    return "QUOTE_NOT_FOUND_IN_SOURCE", "quote does not appear anywhere in the extracted text"


def build_chunks(strict: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    register = load_register()
    excerpts = load_excerpts()
    page_cache: dict[str, dict[int, str] | None] = {}
    chunks: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    for excerpt in excerpts:
        sid = excerpt["source_id"]
        if sid not in register:
            raise ValueError(f"{excerpt['chunk_id']}: source {sid} is not in the register")
        if sid not in page_cache:
            page_cache[sid] = load_pages(sid)
        status, detail = verify_excerpt(excerpt, page_cache[sid])
        details.append({"chunk_id": excerpt["chunk_id"], "source_id": sid, "status": status, "detail": detail})

        if status in {"QUOTE_NOT_FOUND_ON_DECLARED_PAGE", "QUOTE_NOT_FOUND_IN_SOURCE"}:
            # Never index a clause that the source does not support, even in lenient mode.
            continue

        src = register[sid]
        page_start = int(excerpt["page_start"])
        page_end = int(excerpt.get("page_end", page_start))
        text = " ".join(str(excerpt["text"]).split())
        chunk: dict[str, Any] = {
            "chunk_id": excerpt["chunk_id"],
            "source_id": sid,
            "title": src["title"],
            "issuer": src["issuing_authority"],
            "jurisdiction": src["jurisdiction"],
            "document_version": src["version_or_issue"],
            "section_id": str(excerpt["section_id"]),
            "page_start": page_start,
            "page_end": page_end,
            "pdf_page_start": int(excerpt.get("pdf_page_start", page_start)),
            "pdf_page_end": int(excerpt.get("pdf_page_end", page_end)),
            "publication_date": src["publication_date"],
            "effective_date": src.get("effective_date", ""),
            "source_type": src["document_type"],
            "applicability": excerpt.get("applicability") or src["applicability"],
            "claim_classification": excerpt["claim_classification"],
            "text": text,
            "source_url": src["official_url"],
            "verification_status": f"(not committed) {excerpt['_file']}",
            "excerpt_status": status,
            "topics": excerpt.get("topics", []),
            # Explicit, author-declared authorisation. Deliberately not derived from the text: a
            # keyword test cannot tell "an alternative channel shall be used" from "under no
            # circumstances shall an alternative channel be used" (audit finding H-1).
            "authorises_fallback": _declared_flag(excerpt, chunk_id=excerpt["chunk_id"]),
            "support_note": " ".join(str(excerpt.get("support_note", "")).split()),
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        }
        chunks.append(chunk)

    counts: dict[str, int] = {}
    for d in details:
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    summary = {
        "verified": counts.get("VERIFIED_AGAINST_SOURCE", 0),
        "unverified": counts.get("UNVERIFIED_NO_CACHE", 0),
        "mismatch": counts.get("QUOTE_NOT_FOUND_ON_DECLARED_PAGE", 0)
        + counts.get("QUOTE_NOT_FOUND_IN_SOURCE", 0),
        "counts_by_status": counts,
        "details": details,
        "cache_path": str(SOURCE_CACHE),
        "cache_present": SOURCE_CACHE.exists(),
    }
    return chunks, summary


def write_index(chunks: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "chunk_count": len(chunks),
        "sources": sorted({c["source_id"] for c in chunks}),
        "verification": summary,
        "index_sha256": hashlib.sha256(json.dumps(chunks, sort_keys=True).encode("utf-8")).hexdigest(),
        "chunks": chunks,
    }
    INDEX_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main(argv: Iterable[str] | None = None) -> int:
    chunks, summary = build_chunks()
    payload = write_index(chunks, summary)
    print(f"index: {INDEX_PATH}")
    print(f"  chunks {payload['chunk_count']} across {len(payload['sources'])} sources")
    print(f"  verified against source text: {summary['verified']}")
    print(f"  unverified (no local cache) : {summary['unverified']}")
    print(f"  rejected (quote/page wrong) : {summary['mismatch']}")
    for d in summary["details"]:
        if d["status"] not in ("VERIFIED_AGAINST_SOURCE",):
            print(f"    [{d['status']}] {d['chunk_id']}: {d['detail']}")
    if not summary["cache_present"]:
        print("\nNo source cache found; quotes were not checked this run.")
        print("  python scripts/fetch_sources.py --insecure")
    return 1 if summary["mismatch"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
