# ResultRelay — design brief for ITU AI for Good Lab resources

Prepared by Shashwat Srivastava (team leader), shashwat1322001@gmail.com · ITU AI for Good Sandbox Hackathon — UAE

## What it does

A policy-governed agent for communicating critical walk-in laboratory results (Dubai Health Authority standard ST-28). It keeps transport acceptance, delivery, acknowledgment and documentation distinct, binds acknowledgments to the current result revision, routes genetic results to the referring physician, and refuses another jurisdiction's clause as binding. A deterministic gate (Y.3172 P) decides every transition.

## How it works today

FastAPI + React console, 18-state machine, 63 quotations from 14 documents machine-checked against their source pages, jurisdiction-filtered retrieval, 8 scenarios × 11 configurations, 229 tests, hash-chained audit re-verified on read. The policy & legal reviewer runs on TypeSafe Jev behind a containment guard (residency under Federal Law 2/2019 Art. 13, grounding, jurisdiction); a synthetic case may use an offshore model, a real case is refused.

## What we will run in the Lab

1. Ingest the 63 verified excerpts (scripts/export_itu_kb.py --ingest) into the Lab's vectorised knowledge base, keeping page, section, jurisdiction and claim class as metadata, and add hybrid (vector + BM25) retrieval behind the existing applicability filter.
2. Run the reviewer on a local model on the same Lab machine (RESULTRELAY_ADVISE_URL=http://localhost:11434/v1): the residency guard accepts loopback endpoints, so no case view leaves the host. Where the Lab machine sits is recorded as a declared fact, not inferred from a hostname.
3. Re-run the 88-run evaluation with the reviewer in the loop and report endorsement, dissent and containment rejections per scenario.
4. Accept organiser-released free-text error events into the same staged pipeline for the live exercise.

## Boundaries

The model cannot change a case state, choose an unapproved channel, diagnose or interpret a result. The gate computes its decision without reading the proposal. No real patient data, ever.

## Resources requested

- Model serving: Ollama with qwen2.5:14b (the ITU reference default; llama3.1:8b as fallback) — 1 GPU with 16–24 GB VRAM, or 8 vCPU / 32 GB RAM CPU-only.
- Knowledge base: ChromaDB + nomic-embed-text via the ITU reference ingest.py; < 1 GB storage.
- Disk: ~20 GB (model weights, embeddings, run logs). Period: from approval to 10 December 2026.
- Network: no egress needed beyond pulling models and the public GitHub repository. No inbound access required.
- Data: 100% synthetic. No personal, patient, worker or operator data is used, stored or generated.
