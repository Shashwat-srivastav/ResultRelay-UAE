# Report length

Computed by `paper/measure_length.py` from `paper/ResultRelay_ITU_paper.docx`. **This is an estimate, not a render**: the workspace has no LibreOffice/Word/LaTeX, so the page count the official ITU template will produce cannot be measured here. The estimator wraps every paragraph with real font metrics at the document's own page geometry, measures each table with its declared column widths and adds the figure at its placed height. Honest band: +/-0.5 page.

```json
{
  "docx_bytes": 176214,
  "words": 2140,
  "tables": 3,
  "figures": 1,
  "usable_page_pt": 684.3,
  "content_height_pt": 2864.4,
  "estimated_pages": 4.19,
  "estimated_pages_band": [
    3.69,
    4.69
  ],
  "method": "DejaVu Serif metrics, document section geometry, no renderer",
  "status": "ESTIMATE"
}
```

Body text is 2140 words with 3 tables and 1 figure. Estimated length 4.19 pages (band 3.69-4.69). Against the event's 5-page target this is **within budget on the estimate and on its band**; the official template is not in this repository, so the real render remains NOT_VERIFIED.
