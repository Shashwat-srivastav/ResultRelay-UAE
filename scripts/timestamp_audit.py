"""Anchor an audit checkpoint in time with an RFC 3161 trusted timestamp.

    python scripts/timestamp_audit.py S8-accepted-never-delivered            # run, sign, timestamp
    python scripts/timestamp_audit.py S8-accepted-never-delivered --tsa URL  # another authority

A hash chain shows the entries are consistent; an HMAC checkpoint (app.audit.log.sign_checkpoint) shows the
chain head was produced by whoever holds RESULTRELAY_AUDIT_KEY. Neither proves *when*. An RFC 3161 token
from an independent Time-Stamping Authority signs the checkpoint's SHA-256 together with the TSA's clock, so
a chain rebuilt later cannot carry an earlier timestamp. Uses the openssl CLI to build the request; the
default authority is FreeTSA (https://freetsa.org), a free public TSA - for production, use a qualified or
contracted TSA. Only the checkpoint hash leaves the machine: no case data is sent.

Writes evaluation/timestamps/<run_id>.checkpoint.json, .tsq and .tsr. Verify later with:
    openssl ts -verify -data <checkpoint.json> -in <.tsr> -CAfile cacert.pem -untrusted tsa.crt
(cacert.pem and tsa.crt from the TSA's website).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.audit.log import sign_checkpoint  # noqa: E402
from app.orchestration.engine import load_scenario, run_scenario  # noqa: E402

OUT = ROOT / "evaluation" / "timestamps"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--tsa", default="https://freetsa.org/tsr")
    a = ap.parse_args()
    rt = run_scenario(load_scenario(a.scenario), "resultrelay")
    cp = sign_checkpoint(rt.audit)
    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / f"{a.scenario}.{rt.run_id}"
    data = base.with_suffix(".checkpoint.json")
    data.write_text(json.dumps(cp, indent=1, sort_keys=True), encoding="utf-8")
    tsq, tsr = base.with_suffix(".tsq"), base.with_suffix(".tsr")
    subprocess.run(["openssl", "ts", "-query", "-data", str(data), "-sha256", "-cert", "-out", str(tsq)], check=True)
    req = urllib.request.Request(a.tsa, data=tsq.read_bytes(), headers={"Content-Type": "application/timestamp-query"})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - only a hash is sent
        tsr.write_bytes(r.read())
    text = subprocess.run(["openssl", "ts", "-reply", "-in", str(tsr), "-text"], check=True, capture_output=True, text=True).stdout
    status = next((l.strip() for l in text.splitlines() if l.strip().startswith("Status:")), "")
    when = next((l.strip() for l in text.splitlines() if l.strip().startswith("Time stamp:")), "")
    print(f"checkpoint {data.name}: {cp['entries']} entries, head {cp['head'][:16]}…, "
          f"{'HMAC-signed' if cp['signature'] else 'unsigned (set RESULTRELAY_AUDIT_KEY)'}")
    print(f"TSA {a.tsa}: {status} {when}")
    return 0 if "Granted" in status else 1


if __name__ == "__main__":
    sys.exit(main())
