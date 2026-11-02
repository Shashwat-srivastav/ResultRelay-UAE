# ResultRelay — design brief for ITU AI for Good Lab resources

Prepared by Shashwat Srivastava (team leader), shashwat1322001@gmail.com · ITU AI for Good Sandbox Hackathon — UAE

## What it does

A policy-governed agent for communicating critical walk-in laboratory results (Dubai Health Authority standard ST-28). It keeps transport acceptance, delivery, acknowledgment and documentation distinct, binds acknowledgments to the current result revision, routes genetic results to the referring physician, and refuses another jurisdiction's clause as binding. A deterministic gate (Y.3172 P) decides every transition.

## How it works today

FastAPI + React console, 18-state machine, 96 quotations from 24 documents machine-checked against their source pages, hybrid retrieval (BM25 + ChromaDB built with the ITU reference ingest and nomic-embed-text), 10 scenarios × 12 configurations, hash-chained audit re-verified on read. At every decision point a council runs: a Policy Evidence Analyst (DHA lens), a conditional TDRA-lens analyst, and an adversarial reviewer on a different model family, checked by deterministic assurance; a deterministic orchestrator escalates to a person on a verified objection. Recorded runs use Mistral ministral-14b and TypeSafe Jev, synthetic cases only: the residency guard (Federal Law 2/2019 Art. 13) refuses a real case on an offshore endpoint.

## What we will run in the Lab

1. Run the whole council on the ITU reference model, Ollama qwen2.5:14b, on the Lab machine (RESULTRELAY_AGENT_PROVIDER=ollama): the residency guard accepts loopback endpoints, so no case view leaves the host. Our 6 GB laptop cannot hold a 14B model; this is the run we cannot do without the Lab.
2. Rebuild the vector knowledge base on the Lab's ChromaDB with the ITU ingest (scripts/export_itu_kb.py --ingest), keeping page, section, jurisdiction and claim class as metadata.
3. Re-run the 120-run evaluation with the council on the local model, repeated over several runs, and report corrections, disputes, verified objections and escalations with ranges.
4. Accept organiser-released free-text error events into the same staged pipeline for the live exercise.

## Boundaries

The agents cannot send, close or change a case; their only possible effect is an escalation to a person. The gate computes its decision without reading the council. No diagnosis or interpretation of results. No real patient data, ever.

## Resources requested

- Model serving: Ollama with qwen2.5:14b (the ITU reference default; llama3.1:8b as fallback) — 1 GPU with 16–24 GB VRAM, or 8 vCPU / 32 GB RAM CPU-only.
- Knowledge base: ChromaDB + nomic-embed-text via the ITU reference ingest.py; < 1 GB storage.
- Disk: ~20 GB (model weights, embeddings, run logs). Period: from approval to 10 December 2026.
- Network: no egress needed beyond pulling models and the public GitHub repository. No inbound access required.
- Data: 100% synthetic. No personal, patient, worker or operator data is used, stored or generated.
