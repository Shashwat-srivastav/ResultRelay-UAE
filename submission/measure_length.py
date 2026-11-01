"""Estimate the printed length of the built technical report.

There is no page-layout engine in this workspace (no LibreOffice, no Word, no LaTeX), so this
script cannot report the page count the official ITU template will produce. What it does instead is
a reproducible layout *estimate*: it walks the document body in order, wraps every paragraph with
real font metrics (DejaVu Serif standing in for Times New Roman), measures tables row by row, adds
the figure at its placed size, and divides the total by the usable page height taken from the
document's own section properties.

The number is an estimate and is labelled as one everywhere it appears. Its error is dominated by
font substitution and by Word's own table/keep-with-next behaviour, so treat ±0.5 page as the honest
band. The value of the script is not the absolute number: it is that the number is computed from the
document rather than typed into a caption, so a paragraph added tomorrow moves it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import ImageFont
from docx import Document
from docx.shared import Emu

HERE = Path(__file__).resolve().parent
DOCX = HERE / "ResultRelay_ITU_paper.docx"
OUT = HERE / "LENGTH.md"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
EMU_PER_PT = 12700.0  # 914400 EMU per inch / 72 pt per inch
LINE_FACTOR = 1.18  # single spacing for a serif face at 10-11 pt


def _font(size_pt: float, bold: bool = False) -> ImageFont.FreeTypeFont:
    # Rasterise at 4x the requested size for kerning-independent width measurement, then scale back.
    return ImageFont.truetype(FONT_BOLD if bold else FONT, int(size_pt * 4))


def _text_width_pt(text: str, size_pt: float, bold: bool = False) -> float:
    return _font(size_pt, bold).getlength(text) / 4.0


def _wrap_lines(text: str, size_pt: float, width_pt: float, bold: bool = False) -> int:
    if not text.strip():
        return 1
    lines, current = 1, 0.0
    for word in text.split():
        w = _text_width_pt(word + " ", size_pt, bold)
        if current + w > width_pt and current > 0:
            lines += 1
            current = w
        else:
            current += w
    return lines


def _para_height_pt(para, width_pt: float) -> float:
    size = max((r.font.size.pt for r in para.runs if r.font.size), default=10.5)
    bold = any(r.bold for r in para.runs)
    lines = _wrap_lines(para.text, size, width_pt, bold)
    before = para.paragraph_format.space_before.pt if para.paragraph_format.space_before else 0.0
    after = para.paragraph_format.space_after.pt if para.paragraph_format.space_after else 0.0
    return lines * size * LINE_FACTOR + before + after


def _column_widths_pt(table, usable_w: float) -> list[float]:
    """Declared column widths, falling back to equal division where none are set."""
    widths: list[float] = []
    if table.rows:
        # python-docx sets cell widths, not grid widths, when the builder passes `widths=`.
        widths = [c.width.pt if c.width else 0.0 for c in table.rows[0].cells]
    if not any(widths):
        widths = [col.width.pt if col.width else 0.0 for col in table.columns]
    if not any(widths):
        return [usable_w / max(len(table.columns), 1)] * max(len(table.columns), 1)
    scale = usable_w / sum(widths) if sum(widths) > usable_w else 1.0
    return [w * scale for w in widths]


def _table_height_pt(table, usable_w: float) -> float:
    total = 0.0
    widths = _column_widths_pt(table, usable_w)
    for row in table.rows:
        row_lines = 1
        size = 10.5
        for i, cell in enumerate(row.cells):
            width = widths[i] if i < len(widths) else usable_w / max(len(row.cells), 1)
            for para in cell.paragraphs:
                size = max((r.font.size.pt for r in para.runs if r.font.size), default=size)
                row_lines = max(row_lines, _wrap_lines(para.text, size, max(width - 6, 12)))
        total += row_lines * size * LINE_FACTOR + 4  # 4 pt cell padding
    return total


def measure() -> dict:
    doc = Document(DOCX)
    section = doc.sections[0]
    usable_w = (section.page_width - section.left_margin - section.right_margin) / EMU_PER_PT
    usable_h = (section.page_height - section.top_margin - section.bottom_margin) / EMU_PER_PT

    body = doc.element.body
    para_by_id = {p._element: p for p in doc.paragraphs}
    table_by_id = {t._element: t for t in doc.tables}

    total = 0.0
    words = 0
    tables = figures = 0
    for child in body.iterchildren():
        if child in para_by_id:
            para = para_by_id[child]
            words += len(para.text.split())
            shapes = para._element.findall(
                ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent"
            )
            if shapes:
                figures += 1
                total += shapes[0].get("cy") and Emu(int(shapes[0].get("cy"))) / EMU_PER_PT
                total += 8
                continue
            total += _para_height_pt(para, usable_w)
        elif child in table_by_id:
            tables += 1
            total += _table_height_pt(table_by_id[child], usable_w) + 8

    pages = total / usable_h
    return {
        "docx_bytes": DOCX.stat().st_size,
        "words": words,
        "tables": tables,
        "figures": figures,
        "usable_page_pt": round(usable_h, 1),
        "content_height_pt": round(total, 1),
        "estimated_pages": round(pages, 2),
        "estimated_pages_band": [round(pages - 0.5, 2), round(pages + 0.5, 2)],
        "method": "DejaVu Serif metrics, document section geometry, no renderer",
        "status": "ESTIMATE",
    }


def main() -> int:
    m = measure()
    OUT.write_text(
        "# Report length\n\n"
        "Computed by `submission/measure_length.py` from `submission/ResultRelay_ITU_paper.docx`. **This is an "
        "estimate, not a render**: the workspace has no LibreOffice/Word/LaTeX, so the page count the "
        "official ITU template will produce cannot be measured here. The estimator wraps every "
        "paragraph with real font metrics at the document's own page geometry, measures tables row by "
        "row and adds the figure at its placed height. Honest band: ±0.5 page.\n\n"
        "```json\n" + json.dumps(m, indent=2) + "\n```\n\n"
        f"Body text is {m['words']} words with {m['tables']} tables and {m['figures']} figure. Against "
        "the event's 5-page target the estimate is "
        + ("**within budget**" if m["estimated_pages"] <= 4.5 else "**at risk**")
        + "; re-check after pasting into the official template, which is not in this repository.\n"
    )
    print(json.dumps(m, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
