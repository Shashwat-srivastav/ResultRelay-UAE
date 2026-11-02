# Retrieval check: BM25 vs hybrid (BM25 + ChromaDB, ITU reference ingest)

| Question | Expected clause | BM25 top-5 | Hybrid top-5 |
| :--- | :--- | :---: | :---: |
| send health data abroad cloud | `U1-art13` | miss | hit |
| can we use an LLM hosted overseas for patient messages | `U1-art13` | miss | miss |
| text message reached the phone but did anyone read it | `G5-6` | miss | miss |
| how long do we keep the message logs | `retention` | hit | hit |
| can the AI decision be overruled by staff | `U6-4.4.2` | miss | miss |
| should a dangerous lab value go to the patient or their doctor | `G5-8` | miss | hit |
| who checks the AI before it is used | `U6-4.3.3` | miss | hit |

Top-5 hits: BM25 1/7, hybrid 4/7. Questions and expected clauses written by the authors.
