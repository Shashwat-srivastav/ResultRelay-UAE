#!/usr/bin/env python3
"""Fetch the primary sources into a local cache and extract page-marked text.

Why a cache rather than committed text
--------------------------------------
Several of these documents are third-party standards whose terms do not permit
redistribution. They are therefore downloaded from the issuing body at build time and kept
outside the repository (default ``~/.cache/resultrelay/sources``). What *is* committed is the
minimum quotation needed for each excerpt, in ``kb/records/``.

The verifier in ``app/kb/ingest.py`` reads this cache and refuses to index any excerpt
whose text cannot be found on the page the register claims. When the cache is absent, ingestion
still runs but labels every excerpt ``UNVERIFIED_THIS_RUN`` and prints the list; the index is
then not reproducible as evidence.

Usage
-----
    python scripts/fetch_sources.py            # fetch anything missing
    python scripts/fetch_sources.py --force    # refetch everything
    python scripts/fetch_sources.py --list     # show the manifest and cache state
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cache_dir() -> Path:
    """Where downloaded sources live.

    Order: explicit override, then a repo-local cache, then the user cache. The repo-local
    directory is git-ignored (the documents are not redistributed) but it is inside the working
    tree, so a build in a sandbox that keeps the tree and drops ``$HOME`` can still verify.
    """
    override = os.environ.get("RESULTRELAY_SOURCE_CACHE")
    if override:
        return Path(override)
    local = ROOT / "kb" / ".sources"
    if local.exists():
        return local
    return Path.home() / ".cache" / "resultrelay" / "sources"


CACHE = _cache_dir()

# Some public-sector hosts serve incomplete TLS chains; verification is relaxed only for those
# hosts and only when --insecure is passed explicitly.
INSECURE_HOSTS = {"doh.gov.ae", "www.doh.gov.ae", "healthit.gov", "www.healthit.gov", "itu.int", "www.itu.int"}

SOURCES: dict[str, dict[str, str]] = {
    "S1": {
        "url": "https://dha.gov.ae/uploads/052023/Standards%20for%20Clinical%20Laboratory%20Services2023552664.pdf",
        "kind": "pdf",
        "file": "S1_dha_st28_laboratory_standards.pdf",
        "title": "Standards for Clinical Laboratory Services (DHA/HRS/HPSD/ST-28, Issue 2)",
    },
    "AD1": {
        "url": "https://www.doh.gov.ae/-/media/Feature/Resources/Standards/Clinical-Laboratory-Standards-Version-10.ashx",
        "kind": "pdf",
        "file": "AD1_haad_clinical_laboratory_standards_v1_0.pdf",
        "title": "Clinical Laboratory Standards, Version 1.0 (HAAD / DoH Abu Dhabi)",
    },
    "G1": {
        "url": "https://digitalassets.jointcommission.org/api/public/content/3c7a110c215943bc80d9ce87e9d9ee9d?v=aef80e14",
        "kind": "pdf",
        "file": "G1_tjc_npsg_laboratory_2026.pdf",
        "title": "National Patient Safety Goals, Laboratory Program, effective January 2026",
    },
    "G2": {
        "url": "https://healthit.gov/wp-content/uploads/2025/06/SAFER-Guide-8.-Test-Results-Reporting-Final.pdf",
        "kind": "pdf",
        "file": "G2_safer_guide_8_test_results.pdf",
        "title": "SAFER Guide 8: Test Results Reporting and Follow-Up (ONC)",
    },
    "G3": {
        "url": "https://hl7.org/fhir/R5/task.html",
        "kind": "html",
        "file": "G3_fhir_r5_task.html",
        "title": "HL7 FHIR Release 5: Task",
    },
    "G4": {
        "url": "https://profiles.ihe.net/ITI/TF/Volume1/ch-30.html",
        "kind": "html",
        "file": "G4_ihe_xdw_iti_tf_vol1.html",
        "title": "IHE IT Infrastructure Technical Framework, Vol. 1, ch. 30 (Cross-Enterprise Document Workflow)",
    },
    "F1": {
        "url": "https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-Y.3172-201906-I!!PDF-E&type=items",
        "kind": "pdf",
        "file": "F1_itu_y3172_2019.pdf",
        "title": "ITU-T Recommendation Y.3172 (06/2019), Architectural framework for machine learning",
    },
    "U1": {
        "url": "https://uaelegislation.gov.ae/en/legislations/1209/download",
        "kind": "manual",
        "file": "U1_ict_health_law.txt",
        "title": "Federal Law No. (2) of 2019 on the Use of ICT in Health Fields",
        "note": "The portal returns 403 to scripted clients. Retrieved by rendering the page and "
                "recording the articles relied on; see kb/sources/README.md.",
    },
    "U2": {
        "url": "https://privacyarabia.com/wp-content/uploads/2022/08/Decree-Law-45-2021-Data-Protection-Law-English.pdf",
        "kind": "pdf",
        "file": "U2_pdpl_en_translation.pdf",
        "title": "Federal Decree-Law No. 45 of 2021 (PDPL) - unofficial English translation",
        "note": "Official text is Arabic. This is a Lexis Middle East translation on a third-party "
                "mirror, used only to establish the health-data scope exclusion.",
    },
    "U3": {
        "url": "https://dha.gov.ae/uploads/012023/Policy%20for%20Health%20Information%20Assets%20management2023151842.pdf",
        "kind": "pdf",
        "file": "U3_dha_health_information_assets.pdf",
        "title": "Policy for Health Information Assets Management (HISHD/PP-12)",
    },
    "U4": {
        "url": "https://dha.gov.ae/uploads/082022/Health%20Data%20Quality%20Policy2022839141.pdf",
        "kind": "pdf",
        "file": "U4_dha_health_data_quality.pdf",
        "title": "Health Data Quality Policy (HISHD/PP-08)",
    },
    "F2": {
        "url": "https://www.itu.int/dms_pub/itu-t/opb/ai4g/T-AI4G-AI4GOOD-2025-6-PDF-E.pdf",
        "kind": "pdf",
        "file": "F2_itu_ai_readiness_report_2_0.pdf",
        "title": "AI Readiness Report 2.0 (ITU, January 2026)",
    },
    "U6": {
        "url": "https://www.dha.gov.ae/uploads/082022/Artificial%20Intelligence%20Policy20228457.pdf",
        "kind": "pdf",
        "file": "U6_dha_ai_in_healthcare_policy.pdf",
        "title": "Artificial Intelligence in the Healthcare (DHA/HISHD/PP-09)",
    },
    "U7": {
        "url": "https://www.dha.gov.ae/uploads/102022/NABIDH%20Policies%20%26%20Standards%20-%20Audit%20Policy20221021791.pdf",
        "kind": "pdf",
        "file": "U7_nabidh_audit_policy.pdf",
        "title": "NABIDH Policies and Standards, Section 4: Audit Policy (v1.0, September 2020)",
    },
    "U8": {
        "url": "https://www.unifonic.com/hubfs/Technical%20Writing/ESP%20(Du)%20Portal%20and%20Sender%20form.pdf",
        "kind": "pdf",
        "file": "U8_tdra_mobile_spam_policy_v9.pdf",
        "title": "TRA (now TDRA) Regulatory Policy: Mobile Spam, Version 9.0 (31 August 2022)",
        "note": "Third-party copy (an SMS provider's onboarding pack) of the regulator's policy; "
                "tdra.gov.ae does not serve it to scripted clients.",
    },
    "G5": {
        "url": "https://www.rcpath.org/asset/BB86B370-1545-4C5A-B5826A2C431934F5/",
        "kind": "pdf",
        "file": "G5_rcpath_g158_v2.pdf",
        "title": "RCPath G158: The communication of critical and unexpected pathology results (V2, May 2026)",
    },
}


def _ssl_context(url: str, insecure: bool) -> ssl.SSLContext | None:
    host = urllib.parse.urlparse(url).hostname or ""
    if insecure and host in {h.strip() for h in INSECURE_HOSTS}:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


def download(source_id: str, force: bool = False, insecure: bool = False) -> Path:
    spec = SOURCES[source_id]
    CACHE.mkdir(parents=True, exist_ok=True)
    raw = CACHE / spec["file"]
    if raw.exists() and not force:
        return raw
    if spec["kind"] == "manual":
        raise SystemExit(
            f"{source_id}: not scriptable ({spec.get('note', 'manual retrieval')}). "
            f"Place the page-marked extract at {CACHE / (source_id + '.txt')} and re-run."
        )
    req = urllib.request.Request(spec["url"], headers={"User-Agent": "ResultRelay-build/0.1"})
    ctx = _ssl_context(spec["url"], insecure)
    print(f"  fetching {source_id} <- {spec['url']}")
    with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:  # noqa: S310
        raw.write_bytes(resp.read())
    return raw


def _pdf_to_pages(path: Path) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - a single unreadable page must not abort the build
            pages.append("")
    return pages


def _html_to_text(path: Path) -> str:
    html = path.read_text(encoding="utf-8", errors="replace")
    html = re.sub(r"(?is)<(script|style|nav|footer)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
        .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    )
    return re.sub(r"[ \t\xa0]+", " ", text)


def extract(source_id: str, force: bool = False, insecure: bool = False) -> Path:
    """Download and write ``<source_id>.txt`` with page markers."""
    spec = SOURCES[source_id]
    out = CACHE / f"{source_id}.txt"
    if SOURCES[source_id]["kind"] == "manual":
        if not out.exists():
            download(source_id, force=force, insecure=insecure)  # raises with instructions
        print(f"  {source_id}: using manually captured extract {out}")
        return out
    raw = download(source_id, force=force, insecure=insecure)
    if spec["kind"] == "pdf":
        pages = _pdf_to_pages(raw)
        body = "\n".join(f"===== PAGE {i + 1} =====\n{p}" for i, p in enumerate(pages))
    else:
        body = f"===== PAGE 1 =====\n{_html_to_text(raw)}"
    out.write_text(body, encoding="utf-8")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    manifest = CACHE / "manifest.json"
    data = json.loads(manifest.read_text()) if manifest.exists() else {}
    data[source_id] = {
        "title": spec["title"], "url": spec["url"], "kind": spec["kind"],
        "extracted_sha256": digest, "characters": len(body),
        "pages": body.count("===== PAGE "),
    }
    manifest.write_text(json.dumps(data, indent=2, sort_keys=True))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="refetch even if cached")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification for known-deficient hosts")
    ap.add_argument("--list", action="store_true", help="print the manifest and exit")
    args = ap.parse_args()

    if args.list:
        manifest = CACHE / "manifest.json"
        data = json.loads(manifest.read_text()) if manifest.exists() else {}
        print(f"cache: {CACHE}")
        for sid, spec in SOURCES.items():
            state = "extracted" if sid in data else ("downloaded" if (CACHE / spec["file"]).exists() else "missing")
            print(f"  {sid:4s} {state:10s} {spec['title']}")
        return 0

    failures = []
    for sid in SOURCES:
        try:
            path = extract(sid, force=args.force, insecure=args.insecure)
            print(f"  {sid:4s} -> {path}")
        except Exception as exc:  # noqa: BLE001
            failures.append((sid, repr(exc)))
            print(f"  {sid:4s} FAILED: {exc!r}")
    if failures:
        print("\nSome sources could not be fetched. Ingestion will mark affected excerpts unverified.")
        return 1
    print("\nAll sources extracted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
