# Primary sources

The documents behind the corpus are **downloaded, not redistributed**. Only the minimum quotation
needed for each excerpt is committed, in `knowledge_base/excerpts/`. The full texts live in a cache:

| order | location | notes |
|---|---|---|
| 1 | `$RESULTRELAY_SOURCE_CACHE` | explicit override |
| 2 | `knowledge_base/.sources/` | repo-local, git-ignored; survives a build that keeps the tree and drops `$HOME` |
| 3 | `~/.cache/resultrelay/sources/` | default |

`python3 scripts/fetch_sources.py` repopulates the cache. Ingestion then verifies every excerpt
against the page it claims, and refuses to index a quote it cannot find.

## The national layer

The two federal instruments are the reason the corpus is worth anything for a health-data workflow,
and both are awkward to obtain programmatically.

### U1 — Federal Law No. (2) of 2019 on the Use of ICT in Health Fields

`https://uaelegislation.gov.ae/en/legislations/1209/download`

**The portal returns HTTP 403 to scripted clients.** `curl` and `urllib` both get an HTML error
page; only a rendering fetch returns the text. The extract in the cache was captured that way and
reduced to the articles relied on (1, 2, 4, 12, 13, 16, 20, 24, 25), which is why it is marked
`kind: manual` in `scripts/fetch_sources.py` — the fetch script refuses to pretend it can download
it. If the cache is empty, place `U1.txt` (page-marked, `===== PAGE n =====` markers) there by hand.

Article numbering is authoritative from the portal. Secondary summaries disagree with each other
(national-law commentary commonly cites Art. 12 for what the portal numbers Art. 13); where they
conflict, the portal wins and the excerpt cites the portal's number.

### U2 — Federal Decree-Law No. (45) of 2021 (PDPL)

Official text is **Arabic**. No official English full text is published on a government domain.
The extract used is a Lexis Middle East translation published on a third-party mirror:
`https://privacyarabia.com/wp-content/uploads/2022/08/Decree-Law-45-2021-Data-Protection-Law-English.pdf`

It is registered as `VERIFIED_MIRROR`, and it is used for **one** purpose: establishing Article 3(e),
which excludes health personal data subject to other legislation from the PDPL's scope. The PDPL is
therefore **not** cited as the law governing a patient message. Presenting it that way would be a
substantive error, and the register's `applicability` field says so.

## The Dubai layer

* U3 — Policy for Health Information Assets Management, HISHD/PP-12 (69 pp, DHA, 2022).
* U4 — Health Data Quality Policy, HISHD/PP-08, Issue 02 (26 pp, DHA, 2023).

Both are fetched over plain HTTPS from `dha.gov.ae` without special handling. Page numbers cited in
excerpts are the **printed** page numbers, not PDF indices.

## What is missing on purpose

DoH Abu Dhabi's ADHICS v2/2024 and the UAE AI Charter / National AI Strategy 2031 could not be
retrieved: `doh.gov.ae` and `mohap.gov.ae` fail at TLS from this environment, and `ai.gov.ae`
returns 403 to scripted clients. They are named here so that their absence is visible rather than
silently indistinguishable from a decision not to cite them.
