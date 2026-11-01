#!/usr/bin/env python3
"""Measure the palette the CSS actually uses, and fail on anything below AA.

This exists because the first colour pass was done by eye and shipped two failures (a 3.64:1 sidebar
label and a 4.31:1 muted ink). Contrast is arithmetic, so it belongs in CI next to the tests.

Tokens are parsed out of ``web/src/index.css`` rather than duplicated here: if someone changes a
variable and forgets a pair, the numbers below are read from the file, and the check still applies.

Usage::

    python3 scripts/check_contrast.py            # exit 1 on any failure
    python3 scripts/check_contrast.py --verbose  # print every measured pair
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "web" / "src" / "index.css"

#: WCAG 2.2: 4.5:1 for normal text, 3.0:1 for large text (>=24px, or >=18.66px bold),
#: 3.0:1 for the visual boundary of a control and for focus indicators (1.4.11, 2.4.11).
AA_TEXT = 4.5
AA_LARGE = 3.0
AA_UI = 3.0


def parse_tokens(css: str) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", css):
        tokens[name] = value
    return tokens


def _rgb(value: str) -> tuple[int, int, int]:
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lum(value: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = _rgb(value)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg: str, bg: str) -> float:
    a, b = _lum(fg), _lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not CSS.exists():
        print(f"missing {CSS}", file=sys.stderr)
        return 2
    t = parse_tokens(CSS.read_text())

    # Literal colours that are not tokens (sidebar chrome, banner ink, 3-D captions).
    lit = {
        "shell": "#0d1419",
        "shell-hover": "#16212a",
        "shell-active": "#17313a",
        "nav-idle": "#b9c4ce",

        "th-bg": "#fbfcfd",
        "field-bg": "#ffffff",
        "on-dark": "#ffffff",
        "pipeline-bg": "#0b1218",
    }

    def tok(name: str) -> str:
        key = name if name.startswith("--") else f"--{name}"
        if key in t:
            return t[key]
        if name in lit:
            return lit[name]
        raise KeyError(f"unknown colour {name!r} — add it to the token file or the literal map")

    # (label, foreground, background, threshold)
    checks: list[tuple[str, str, str, float]] = [
        # ---- body text
        ("ink on canvas", "ink", "bg", AA_TEXT),
        ("ink on panel", "ink", "panel", AA_TEXT),
        ("ink-2 on panel", "ink-2", "panel", AA_TEXT),
        ("ink-3 on panel (muted)", "ink-3", "panel", AA_TEXT),
        ("ink-3 on canvas", "ink-3", "bg", AA_TEXT),
        ("ink-3 on table header", "ink-3", "th-bg", AA_TEXT),
        ("link accent on panel", "accent", "panel", AA_TEXT),
        # ---- sidebar
        ("nav item idle", "nav-idle", "shell", AA_TEXT),
        ("nav item hover", "nav-idle", "shell-hover", AA_TEXT),
        ("nav item active", "on-dark", "shell-active", AA_TEXT),
        ("nav group label", "nav-label", "shell", AA_TEXT),
        ("sidebar footer", "sidebar-foot-ink", "shell", AA_TEXT),
        ("brand subtitle", "brand-sub-ink", "shell", AA_TEXT),
        # ---- chips: text is the signal, so text must clear AA on its own fill
        ("chip ok", "ok-ink", "accent-soft", AA_TEXT),
        ("chip warn", "warn-ink", "warn-soft", AA_TEXT),
        ("chip bad", "bad-ink", "bad-soft", AA_TEXT),
        ("chip info", "info-ink", "info-soft", AA_TEXT),
        ("chip neutral", "ink-2", "chip-neutral-bg", AA_TEXT),
        ("chip outline", "ink-3", "panel", AA_TEXT),
        # ---- banners
        ("banner info", "info-ink", "info-soft", AA_TEXT),
        ("banner warn", "warn-ink", "warn-soft", AA_TEXT),
        ("banner bad", "bad-ink", "bad-soft", AA_TEXT),
        ("banner ok", "ok-ink", "accent-soft", AA_TEXT),
        # ---- buttons
        ("primary button label", "on-dark", "accent", AA_TEXT),
        ("primary button hover label", "on-dark", "accent-hover", AA_TEXT),
        ("danger button label", "on-dark", "bad", AA_TEXT),
        ("button label on white", "ink", "panel", AA_TEXT),
        # ---- step rail + 3-D captions
        ("current step pip", "step-pip-ink", "accent-soft", AA_TEXT),
        ("scene caption", "scene-caption", "pipeline-bg", AA_TEXT),
        ("scene hint", "scene-hint", "pipeline-bg", AA_TEXT),
        # ---- non-text: control boundaries and focus indicators (1.4.11 / 2.4.11)
        ("input border on white", "line-control", "field-bg", AA_UI),
        ("input border on canvas", "line-control", "bg", AA_UI),
        ("focus ring on white", "focus-ring", "panel", AA_UI),
        ("focus ring on canvas", "focus-ring", "bg", AA_UI),
        ("focus ring on sidebar", "focus-ring-dark", "shell", AA_UI),
    ]

    failures: list[str] = []
    for label, fg, bg, floor in checks:
        try:
            f, b = tok(fg), tok(bg)
        except KeyError as exc:
            failures.append(f"{label}: {exc}")
            continue
        ratio = contrast(f, b)
        ok = ratio >= floor
        if args.verbose or not ok:
            print(f"{'PASS' if ok else 'FAIL'}  {ratio:5.2f}:1  (min {floor})  {label}")
        if not ok:
            failures.append(f"{label}: {ratio:.2f}:1 < {floor}:1 ({f} on {b})")

    if failures:
        print(f"\n{len(failures)} contrast failure(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"contrast: {len(checks)} pairs at or above AA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
