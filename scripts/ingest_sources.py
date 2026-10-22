#!/usr/bin/env python3
"""Rebuild the knowledge-base index from the committed excerpts.

Thin wrapper: all verification logic lives in ``backend/app/kb/ingest.py`` so that the same code
path is exercised by the test suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.kb.ingest import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
