# Sources that cannot be downloaded by script: where to get them by hand

`scripts/fetch_sources.py` downloads most of the corpus. The documents below either refuse scripted
clients (HTTP 403, TLS failure, signed links), are only available as a third-party copy, or have
not been located at all. Each entry says what the document is, why ResultRelay needs it, where
the official text is, what the knowledge base holds now, and how to add or upgrade it.

**How URLs are marked.** *register* = taken from `kb/source_register.csv` (`official_url`) or
`scripts/fetch_sources.py`. *search-confirmed* = the URL appeared in web search results on
2 November 2026; the file itself was not downloaded or read for this note. *(not verified)* = a
plausible location that was not confirmed. No URL here should be read as checked unless it is
marked.

## How to add a source by hand (all entries)

1. **Download** the document in a browser from the official URL.
2. **Save the text** as `kb/.sources/<ID>.txt` (git-ignored; the full text is not redistributed).
   Put a `===== PAGE n =====` line before each page's text, where `n` is the page number the
   excerpts will cite (`page_start`, or `pdf_page_start` when the printed and PDF numbers differ).
   An HTML page with no pagination goes under a single `===== PAGE 1 =====`.
3. **Register it**: add or update the row in `kb/source_register.csv`. `app/kb/ingest.py` refuses
   a row with any required field empty (`source_id`, `title`, `issuing_authority`, `jurisdiction`,
   `document_type`, `version_or_issue`, `publication_date`, `official_url`, `retrieved_at`,
   `applicability`, `legal_or_guidance_status`, `license_or_reuse_notes`, `verification_status`).
   Set `verification_status` honestly: `VERIFIED_OFFICIAL` only when the text came from the
   issuer's own file; `VERIFIED_TRANSCRIPTION` when you typed or copied it from a rendered page.
4. **Add excerpts** in `kb/records/<ID>_<short_name>.yaml` (`source_id`, then `excerpts:` with
   `chunk_id`, `section_id`, `page_start`, `claim_classification`, `text`, and usually `topics`
   and `support_note`). Quote verbatim and minimally.
5. **Re-ingest**: `python -m app.kb.ingest`. It verifies every quotation against the declared page,
   rewrites `kb/index/chunks.json` and `kb/index/pinned.sha256`, and exits non-zero if any quote is
   not found where it claims to be.
6. Optionally record the source in `scripts/fetch_sources.py` as `"kind": "manual"` so the fetch
   script explains the step instead of failing, and rebuild the vector store with
   `python scripts/export_itu_kb.py --ingest PATH/TO/ITUAIReadiness` if you use hybrid retrieval.

Arabic text: `normalise()` in `app/kb/ingest.py` handles Unicode, but the BM25 tokenizer in
`app/kb/retriever.py` only indexes Latin letters and digits. An Arabic excerpt would therefore be
verified but not found by BM25 unless the tokenizer is extended; Arabic questions currently reach
English excerpts through `ARABIC_GLOSSARY`.

## Summary

| ID | document | KB status now | blocker |
|---|---|---|---|
| U1 | Federal Law No. 2 of 2019 (ICT in health fields) | in KB, transcription | portal returns 403 to scripts |
| U5 | UAE Charter for the Development and Use of AI | in KB, transcription | portal returns 403 to scripts |
| AD2 | ADHICS V2 (DoH Abu Dhabi) | in KB, transcription | TLS failure for scripted clients; not in `fetch_sources.py` |
| U8 | TDRA Regulatory Policy: Mobile Spam | in KB, third-party copy | not served by tdra.gov.ae to scripts |
| U10 | Telecom Law, Federal Decree-Law No. 3 of 2003 (Arabic text) | English in KB (WIPO Lex); Arabic not in KB | signed links; Arabic text layer broken |
| G8 | EU AI Act, Regulation (EU) 2024/1689 | in KB, third-party copy | EUR-Lex refuses scripts |
| — | UAE National Strategy for AI 2031 (EN and AR) | not in KB | not retrieved |
| — | Ministerial Resolution No. 51 of 2021 | not in KB | no official text located |
| — | MOHAP national health-AI instrument | not in KB | none identified as published |

## U1 — Federal Law No. (2) of 2019 on the Use of ICT in Health Fields

- **What it is.** The federal statute on health information: confidentiality (Art. 4), storage
  inside the State (Art. 12), the ban on storing, processing, generating or transferring health data
  outside the State without a Health Authority resolution (Art. 13), patient confidentiality and its
  exceptions (Art. 16), 25-year retention (Art. 20), penalties (Arts. 24–25). The Executive
  Regulation is Cabinet Resolution No. 32 of 2020 (per the register).
- **Why it matters.** It is the legal basis of the residency guard (`app/advisers/residency.py`,
  Art. 13 and Art. 24), of retention gap GR-11 and of residency gap GR-19. It is the federal layer
  that binds every Dubai and Abu Dhabi case (`JURISDICTION_LAYERS`).
- **Official URL.** https://uaelegislation.gov.ae/en/legislations/1209/download (*register*).
- **KB status.** In KB as a **transcription** (`VERIFIED_TRANSCRIPTION`, 6 chunks). The portal
  serves the law as HTML to a browser and 403 to scripts; `kb/.sources/U1.txt` was captured by
  rendering the page and holds only the articles relied on, under a single page marker.
- **To upgrade.** Download the official file in a browser, save its full text as
  `kb/.sources/U1.txt` with real page markers, update `page_start` in
  `kb/records/U1_ict_health_law.yaml` if printed pages become available, set the register class to
  `VERIFIED_OFFICIAL`, re-ingest. Use the portal's article numbering; secondary commentary sometimes
  numbers the localisation article differently.

## U5 — The UAE Charter for the Development and Use of Artificial Intelligence

- **What it is.** National AI policy issued 10 June 2024 (per the register): objectives and
  principles including safety, data privacy, transparency, human oversight, governance and
  accountability. Non-binding (`OFFICIAL_GUIDANCE`).
- **Why it matters.** It grounds the human-oversight design (the agents can only escalate to a
  person) and readiness row R07 (Strategy Alignment); it is cited in AI-governance gap GR-17.
- **Official URL.** https://uaelegislation.gov.ae/en/policy/details/the-uae-charter-for-the-development-and-use-of-artificial-intelligence
  (*register*).
- **KB status.** In KB as a **transcription** (5 chunks, located by principle number under a
  page-1 marker). Not listed in `scripts/fetch_sources.py`.
- **To upgrade.** Save the page or its PDF (if the portal offers one) from a browser, keep the
  principle headings, re-ingest, and change the class only if the text came from an issuer file.

## AD2 — Abu Dhabi Healthcare Information and Cyber Security Standard (ADHICS V2)

- **What it is.** DoH Abu Dhabi's information and cyber security standard, code
  `DOH/SD/ICSO/ADHICS/V2/2024` (per the register). Binding in Abu Dhabi; a comparator for a Dubai
  case.
- **Why it matters.** It is the only cyber-security instrument in the KB; it grounds the
  tamper-evidence of the audit chain (§2.30 data integrity) and is the binding cyber instrument
  for an Abu Dhabi (AE-AZ) case.
- **Official URL.** https://www.doh.gov.ae/-/media/Feature/Resources/Standards/ADHICS-v2-standard.ashx
  (*register*; doh.gov.ae fails at TLS for scripted clients from some networks).
- **KB status.** In KB as a **transcription** (2 chunks: §1 scope, §2.30). Not listed in
  `scripts/fetch_sources.py`.
- **To upgrade.** Download the PDF in a browser, extract it page by page into `kb/.sources/AD2.txt`
  (the same layout `fetch_sources.py` writes for PDFs), cite PDF pages in
  `kb/records/AD2_adhics_v2.yaml`, set `VERIFIED_OFFICIAL`, re-ingest. Add an `AD2` entry to
  `SOURCES` in `scripts/fetch_sources.py` (`"kind": "pdf"` with `--insecure`, or `"manual"`).

## U8 — TDRA Regulatory Policy: Mobile Spam

- **What it is.** The telecom regulator's policy on mobile spam (Version 9.0, 31 August 2022, per
  the register). It defines delivery of marketing messages and makes the licensee responsible for
  it.
- **Why it matters.** It is the only TDRA policy in the KB that defines delivery. It backs the
  institutional analyst (TDRA lens; sources U8, U10, G6) and the health-telecom gap GR-15
  (telecom delivery ends at the handset, the health record needs a person), and gap GR-18.
- **Official URL.** The official text has not been obtained from a TDRA domain. Start from
  https://tdra.gov.ae *(not verified for this document)*. The copy used is
  https://www.unifonic.com/hubfs/Technical%20Writing/ESP%20(Du)%20Portal%20and%20Sender%20form.pdf
  (*register*; a third-party SMS provider's onboarding pack).
- **KB status.** In KB as a **third-party copy** (`VERIFIED_THIRD_PARTY_COPY`, 4 chunks). The
  register notes that a newer marketing-SMS policy, reported in October 2025, may supersede parts of
  it and was not retrieved.
- **To add / upgrade.** Obtain the policy (and any successor) from TDRA, save it as
  `kb/.sources/U8.txt` with PDF page markers, check the four quotations still match, set
  `VERIFIED_OFFICIAL` and update `official_url`. A successor policy should get its own source id.

## U10 — Telecom Law (Federal Decree-Law No. 3 of 2003, as amended): Arabic text

- **What it is.** The law that establishes the telecom regulator and its mandate (Art. 13: service
  sufficiency, subscribers' interests, licensee quality standards). The Arabic text prevails.
- **Why it matters.** It is TDRA's statutory mandate, which the institutional analyst speaks for,
  and it is cited in GR-15. An Arabic quotation would also address the "no Arabic text" limit.
- **Official URLs.**
  - WIPO Lex record (English): https://www.wipo.int/wipolex/en/legislation/details/13914
    (*register*; the PDF is served only through a signed link from this page).
  - WIPO Lex record (Arabic interface): https://www.wipo.int/wipolex/ar/legislation/details/13914
    (*search-confirmed*).
  - TDRA consolidated English text on the UAE government portal:
    https://u.ae/-/media/Resources/TDRA-telecom-law_Final_english_o.pdf (*search-confirmed*; may be
    a later consolidation than the WIPO edition, which predates the 2020 renaming to TDRA).
- **KB status.** **English** text in KB (`VERIFIED_OFFICIAL_REPOSITORY`, 2 chunks, Art. 13).
  **Arabic not in KB**: the register records that the Arabic PDF was retrieved but its text layer
  extracts with reversed and broken glyphs.
- **To add the Arabic text.** Obtain an Arabic text with a clean text layer (or a careful
  transcription, classed `VERIFIED_TRANSCRIPTION`), save it as a separate source id (for example
  `U10A`), add Art. 13 excerpts, and extend the retriever tokenizer before relying on lexical search
  (see the note above). If the u.ae consolidated English text is newer, consider re-verifying the
  English excerpts against it and recording the amendment status.

## G8 — EU AI Act, Regulation (EU) 2024/1689

- **What it is.** The EU regulation on AI; Articles 14(1) (human oversight), 26(2) (deployer
  oversight) and 73(2) (serious-incident reporting) are excerpted. A `GLOBAL_COMPARATOR`: it can
  never bind a UAE case.
- **Why it matters.** It is the comparator for AI-governance gap GR-17 and answers the critic's
  request for verified global examples (finding N-10).
- **Official URL.** https://eur-lex.europa.eu/eli/reg/2024/1689/oj (*register*). EUR-Lex refuses
  scripted clients.
- **KB status.** In KB as a **third-party copy** (3 chunks), verified against the
  artificialintelligenceact.eu article pages (`kind: manual` in `fetch_sources.py`). That copy inserts
  glossary pop-ups into sentences, so only clean spans are quoted.
- **To upgrade.** Download the Official Journal PDF from EUR-Lex in a browser, save as
  `kb/.sources/G8.txt` with PDF page markers, set `pdf_page_start` for each article in
  `kb/records/G8_eu_ai_act.yaml`, set `VERIFIED_OFFICIAL`, re-ingest.

## UAE National Strategy for Artificial Intelligence 2031 (English and Arabic)

- **What it is.** The federal AI strategy. The UAE Cabinet's announcement of its adoption is dated
  2019 per search results (not checked against the document).
- **Why it matters.** It is the national-strategy document class the event asks for (critic finding
  RJ-11), and readiness row R07 (Strategy Alignment) is `PARTIAL` because it is missing. The Charter
  (U5) is a different document.
- **Official URLs** (*search-confirmed*, not downloaded):
  - English: https://u.ae/-/media/AI-publications/UAE-National-Strategy-for-Artificial-Intelligence-2031.pdf
  - Arabic: https://u.ae/-/media/AI-publications/Ar-UAE-National-Strategy-for-Artificial-Intelligence-2031-AR-(1).pdf
- **KB status.** **Not in KB.**
- **To add.** Download both PDFs, extract per page into `kb/.sources/<ID>.txt` (a new id, e.g.
  `U11`; keep the Arabic as a separate id), register as `OFFICIAL_GUIDANCE` (a strategy, not a
  binding instrument), excerpt only the objectives that bear on government AI use and health, then
  update R07 in `kb/framework/ai_readiness_mapping.csv`.

## Ministerial Resolution No. 51 of 2021 (exceptions to Art. 13 of Federal Law 2/2019)

- **What it is.** According to law-firm commentary, a Ministry of Health and Prevention resolution
  listing the cases in which health data may be stored or processed outside the State (for example
  treatment abroad, samples sent to overseas laboratories), some with consent, anonymisation or
  in-country-copy conditions.
- **Why it matters.** It implements the Art. 13 exception that the residency guard depends on.
  Because its text is not in the KB, `app/advisers/residency.py` (`MR51`) never decides whether an
  exception applies and sends the question to a person; it is also cited in gap GR-19.
- **Official URL.** **No official URL was found.** Search the UAE Legislation Portal,
  https://uaelegislation.gov.ae, and the Ministry of Health and Prevention site, https://mohap.gov.ae
  (*not verified for this document*).
- **Secondary commentary only (not authoritative, not to be quoted as the resolution):**
  - Al Tamimi & Co., "Health data transfers outside the UAE":
    https://www.tamimi.com/news/health-data-transfers-outside-the-uae/ (*search-confirmed*)
  - Baker McKenzie, "United Arab Emirates: Health Data Law - Permitted Transfers of Health Data":
    https://insightplus.bakermckenzie.com/bm/data-technology/united-arab-emirates-health-data-law-permitted-transfers-of-health-data
    (*search-confirmed*)
- **KB status.** **Not in KB.**
- **To add.** Only from an official text. Register it as `BINDING_REQUIREMENT`, AE-FED; excerpt the
  exception list; then the residency guard could cite specific exceptions instead of "human
  determination" (the decision itself should stay with a person).

## MOHAP / national health-AI instrument

- **What it is.** A federal (MOHAP) policy on AI in health, covering the emirates whose facilities
  MOHAP licenses.
- **Why it matters.** Critic finding RT-13 asked for the national health-AI layer. The KB has the
  Dubai instrument (U6, DHA policy PP-09) and NABIDH's audit policy (U7), but nothing federal.
- **Official URL.** **No published MOHAP AI-in-health instrument was identified.** Search results
  on 2 November 2026 point only to a MOHAP news item about a workshop on a "National Policy for the
  Promotion of Smart Health Services and Artificial Intelligence in the Health Sector", which
  suggests the policy is in development:
  https://mohap.gov.ae/en/w/mohap-organizes-workshop-on-development-of-national-policy-for-the-promotion-of-smart-health-services-and-artificial-intelligence-in-the-health-sector
  *(not verified: the page did not load when checked)*.
- **KB status.** **Not in KB.**
- **To add.** If and when MOHAP publishes the policy, add it as a new AE-FED source and re-check
  gap GR-17 (AI governance) against it.

---

## U11 — Dubai Law No. (6) of 2018 Concerning the Dubai Health Authority, as amended by Law No. (14) of 2021

- **What it is:** DHA's statutory mandate: Article 6(a) makes DHA the competent entity regulating the health
  sector throughout Dubai, free zones included; Article 5(4) adds promoting smart-health technologies; Article
  6 item 21 the health information system (the basis of NABIDH).
- **Why it matters:** the institutional basis for the Policy Evidence Analyst's DHA lens, for DHA's AI policy
  PP-09 and for NABIDH (gap GR-11).
- **Status in the KB:** **in the KB** as U11 (3 excerpts, verified against the Dubai Legal Portal's English
  text of Law No. 14 of 2021, which restates the amended articles).
- **Official URLs:**
  - Law No. (14) of 2021 (amending law, used for the KB):
    https://dlp.dubai.gov.ae/Legislation%20Reference/2021/Law%20No.%20(14)%20of%202021%20Amending%20Law%20No.%20(6)%20of%202018.html
  - Law No. (6) of 2018 (original law): https://dlp.dubai.gov.ae/Legislation%20Reference/2018/Law%20No.%20(6)%20of%202018%20Concerning%20the%20Dubai%20Health%20Authority.html
    (downloaded on 2026-11-02; not yet excerpted)
- **How to refresh:** `python scripts/fetch_sources.py` fetches U11 (kind `html`); then `python -m app.kb.ingest`.

## UAE National Cybersecurity Strategy (2019)

- **What it is:** the national cybersecurity strategy launched by the TRA (now TDRA) in June 2019: five
  pillars and 60 initiatives, set for three years.
- **Why it matters:** the "cyber strategy" document class the event asks for; context for the security of a
  laboratory's messaging channel and audit log. Its three-year term has passed: check for a successor first.
- **Status in the KB:** **not in the KB.** No official full-text PDF was found on tdra.gov.ae or csc.gov.ae
  (the UAE Cyber Security Council) by script.
- **Official / reference URLs:**
  - UAE Government portal summary (official):
    https://u.ae/en/about-the-uae/strategies-initiatives-and-awards/strategies-plans-and-visions/strategies-plans-and-visions-untill-2021/national-cybersecurity-strategy-2019
  - WAM (state news agency) launch announcement: https://www.wam.ae/en/article/hszr8rij-uae-national-cybersecurity-strategy-launched
  - UNODC SHERLOC strategies database entry (hosts a TRA presentation of the strategy, not the strategy text):
    https://sherloc.unodc.org/cld/en/treaties/strategies/united_arab_emirates/are0003s.html
  - TDRA: https://tdra.gov.ae (search "National Cybersecurity Strategy"); UAE Cyber Security Council: https://csc.gov.ae (not verified)
- **How to add:** download the strategy text from TDRA or the Cyber Security Council, save it as
  `kb/.sources/U12.txt` with `===== PAGE n =====` markers, add excerpts in `kb/records/U12_cyber_strategy.yaml`,
  add a register row, then `python -m app.kb.ingest`.
