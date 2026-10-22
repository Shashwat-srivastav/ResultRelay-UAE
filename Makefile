# ResultRelay — developer entry points.
#
#   make setup     install backend and frontend dependencies
#   make kb        fetch sources (optional) and rebuild the verified index
#   make verify    re-check every quotation against the official source text
#   make test      run the backend test suite
#   make eval      run the 7 x 4 evaluation matrix and regenerate the report
#   make build     build the frontend into the backend's static directory
#   make dev       serve API + built UI on :8000
#   make manifest  export a static JSON manifest of evidence claims
#   make check     verify + test + eval (what CI would run)

PY := python3
BACKEND := backend
FRONTEND := frontend

.PHONY: help setup kb verify test eval manifest build dev check clean

help:
	@grep -E '^#   ' Makefile | sed 's/^#   //'

setup:
	$(PY) -m pip install --quiet pypdf fastapi "uvicorn[standard]" sqlalchemy httpx pyyaml pytest
	cd $(FRONTEND) && npm install

# Fetching is optional: without the cache the index still builds, but every excerpt is labelled
# UNVERIFIED for that run and `make verify` fails loudly instead of pretending.
kb:
	$(PY) scripts/fetch_sources.py --insecure || true
	cd $(BACKEND) && $(PY) -m app.kb.ingest

verify:
	cd $(BACKEND) && $(PY) -m app.kb.ingest
	cd $(BACKEND) && $(PY) -m pytest tests/test_kb.py -q

test:
	cd $(BACKEND) && $(PY) -m pytest -q

eval:
	$(PY) scripts/run_evaluation.py
	$(PY) scripts/export_manifest.py

manifest:
	$(PY) scripts/export_manifest.py

build: manifest
	cd $(FRONTEND) && npm run build

dev: build
	cd $(BACKEND) && $(PY) -m uvicorn app.main:app --host 0.0.0.0 --port $${PORT:-8000}

check: verify test eval

clean:
	rm -f backend/resultrelay.db
	rm -rf $(BACKEND)/app/static/app
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
