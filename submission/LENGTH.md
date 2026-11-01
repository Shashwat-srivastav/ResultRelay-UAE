# Report length

Computed by `submission/measure_length.py` from `submission/ResultRelay_ITU_paper.docx`. **This is an estimate, not a render**: the workspace has no LibreOffice/Word/LaTeX, so the page count the official ITU template will produce cannot be measured here. The estimator wraps every paragraph with real font metrics at the document's own page geometry, measures each table with its declared column widths and adds the figure at its placed height. Honest band: +/-0.5 page.

```json
{
  "docx_bytes": 176280,
  "words": 2160,
  "tables": 3,
  "figures": 1,
  "usable_page_pt": 684.3,
  "content_height_pt": 2875.7,
  "estimated_pages": 4.2,
  "estimated_pages_band": [
    3.7,
    4.7
  ],
  "method": "DejaVu Serif metrics, document section geometry, no renderer",
  "status": "ESTIMATE"
}
```

Body text is 2160 words with 3 tables and 1 figure. Estimated length 4.2 pages (band 3.7-4.7). Against the event's 5-page target this is **within budget on the estimate and on its band**; the official template is not in this repository, so the real render remains NOT_VERIFIED.
