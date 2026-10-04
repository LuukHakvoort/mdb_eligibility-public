"""Page text lines that survive two text-layer quirks seen in CDB's annual reports:

- **Rotated pages** (a landscape table on a portrait page: matrix (0, s, -s, 0)):
  pdfplumber's extract_text() emits each word on its own reversed line. The chars are
  rotated into the reading frame here and re-clustered into rows.
- **Doubled text** ("CCAARRIIBBBBEEAANN": every glyph drawn twice, offset a hair):
  removed with `dedupe_chars()` before extraction.

Upright pages pass straight through to extract_text().
"""

from __future__ import annotations

import logging

logging.disable(logging.CRITICAL)


def _orientation(char: dict) -> int:
    a, b, c, d = char["matrix"][:4]
    if abs(b) > abs(a):
        return 90 if b > 0 else 270  # text runs up / down the page
    return 180 if a < 0 else 0


def _doubled(text: str) -> bool:
    letters = [(a, b) for a, b in zip(text, text[1:]) if a.isalpha()]
    return len(letters) > 60 and sum(a == b for a, b in letters) / len(letters) > 0.4


def _mostly_single_letters(text: str) -> bool:
    tokens = text.split()
    return len(tokens) > 60 and sum(len(t) == 1 for t in tokens) / len(tokens) > 0.4


def _word_rows(page, tolerance: float = 3.0) -> list[str]:
    """Rows rebuilt from word positions -- for tables whose extract_text() comes out one
    column at a time and letter-spaced (CAF's 2023-2025 rotated capital tables)."""

    rows: list[list[dict]] = []
    for word in sorted(page.extract_words(x_tolerance=7, y_tolerance=3), key=lambda w: (round(w["top"]), w["x0"])):
        if rows and abs(word["top"] - rows[-1][0]["top"]) <= tolerance:
            rows[-1].append(word)
        else:
            rows.append([word])
    return [" ".join(w["text"] for w in sorted(row, key=lambda w: w["x0"])) for row in rows]


def page_lines(page, row_tolerance: float = 3.0) -> list[str]:
    chars = [c for c in page.chars if c["text"].strip() != "" or c["text"] == " "]
    if not chars:
        return []
    orientations = [_orientation(c) for c in chars]
    dominant = max(set(orientations), key=orientations.count)
    if dominant == 0:
        text = page.extract_text() or ""
        if _mostly_single_letters(text):
            return _word_rows(page)
        if not _doubled(text):
            return text.splitlines()
    try:
        page = page.dedupe_chars()
        chars = [c for c in page.chars if c["text"].strip() != "" or c["text"] == " "]
        orientations = [_orientation(c) for c in chars]
    except Exception:
        pass
    if dominant == 0:
        return (page.extract_text() or "").splitlines()

    placed = []
    for c, o in zip(chars, orientations):
        if o != dominant:
            continue
        if dominant == 90:
            x, y, adv = -c["bottom"], c["x0"], abs(c["bottom"] - c["top"])
            x = -c["bottom"]
        elif dominant == 270:
            x, y, adv = c["top"], -c["x1"], abs(c["bottom"] - c["top"])
        elif dominant == 180:
            x, y, adv = -c["x1"], -c["bottom"], abs(c["x1"] - c["x0"])
        else:
            x, y, adv = c["x0"], c["top"], abs(c["x1"] - c["x0"])
        placed.append((y, x, adv, c["text"]))

    placed.sort()
    rows: list[list[tuple[float, float, str]]] = []
    row_y = None
    for y, x, adv, text in placed:
        if row_y is None or y - row_y > row_tolerance:
            rows.append([])
            row_y = y
        rows[-1].append((x, adv, text))

    lines = []
    for row in rows:
        row.sort()
        out, prev_end = "", None
        for x, adv, text in row:
            if prev_end is not None and x - prev_end > 0.3 * max(adv, 1) and not out.endswith(" "):
                out += " "
            out += text
            prev_end = x + adv
        lines.append(out.strip())
    return lines
