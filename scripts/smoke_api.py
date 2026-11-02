"""API smoke test: start the server, run S9 with the agent council through the API, check the outcome.

    python scripts/smoke_api.py            # used by CI; exits non-zero on any failure

Offline: the council replays recorded answers, so no API key and no Ollama are needed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("SMOKE_PORT", "8765"))
BASE = f"http://127.0.0.1:{PORT}"


def check(cond: bool, msg: str) -> None:
    print(("ok   " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        raise SystemExit(1)


def main() -> int:
    env = {**os.environ, "RESULTRELAY_DB": str(ROOT / "evaluation" / "smoke.sqlite")}
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT)], cwd=ROOT, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{BASE}/api/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        h = httpx.get(f"{BASE}/api/health", timeout=10)
        check(h.status_code == 200, f"GET /api/health → {h.status_code}")
        sc = httpx.get(f"{BASE}/api/scenarios", timeout=10).json()
        check(len(sc if isinstance(sc, list) else sc.get("scenarios", [])) == 12, "12 scenarios listed")
        r = httpx.post(f"{BASE}/api/runs", json={"scenario_id": "S9-reply-from-someone-else",
                                                 "configuration": "resultrelay_council"}, timeout=30)
        check(r.status_code == 200, f"POST /api/runs → {r.status_code}")
        run_id = r.json()["run"]["run_id"]
        p = httpx.post(f"{BASE}/api/runs/{run_id}/play", timeout=120)
        check(p.status_code == 200, f"POST /api/runs/{{id}}/play → {p.status_code}")
        state = p.json()["run"]["state"]
        check(state == "ESCALATION_REQUIRED", f"S9 with the council ends in {state} (expected ESCALATION_REQUIRED)")
        t = httpx.get(f"{BASE}/api/runs/{run_id}/trace", timeout=30)
        check(t.status_code == 200 and "3b_council" in t.text, "decision trace includes the council step")
        k = httpx.get(f"{BASE}/api/kb/search", params={"q": "critical result acknowledgment", "jurisdiction": "AE-DU"}, timeout=30)
        check(k.status_code == 200, f"GET /api/kb/search → {k.status_code}")
        ui = httpx.get(f"{BASE}/", timeout=10)
        check(ui.status_code == 200 and "<div id=\"root\"" in ui.text, "console UI served at /")
    finally:
        srv.terminate()
        srv.wait(timeout=10)
        for _ in range(10):  # Windows can hold the file briefly after the server exits
            try:
                (ROOT / "evaluation" / "smoke.sqlite").unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.5)
    print("smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
