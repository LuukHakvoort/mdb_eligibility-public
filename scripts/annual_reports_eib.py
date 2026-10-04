"""Parse EIB's "H.1. Statement of Subscriptions to the Capital of the Bank"
table out of EIB's annual financial-statement PDFs.

Real and different from CDB's table, confirmed by inspection: raw EUR
amounts (subscribed/uncalled/called capital), not a pre-computed percentage
column -- `capital_share_pct` is computed here from each row against the
table's own "Total" row, not guessed against some external total. **No
voting-power percentage exists in this table at all**, and this is a real
structural fact, not a data-availability gap: EIB's Source_Map entry already
notes "statutory voting rules are not reducible to a single one-share/one-
vote percentage" -- `voting_power_pct` is left honestly blank with a note,
not computed or guessed.

**Word-position clustering, not line regex** -- confirmed necessary, not a
stylistic choice: EIB's newer statements (2019, 2024) print numbers
comma-grouped ("37,578,019,000"), but older ones (2010, confirmed real) use
*space*-grouped numbers ("37 578 019 000") with no other column delimiter --
a plain-text line regex can't tell an intra-number space from a
column-separating space, since both are literally the same character. Word
x-positions resolve this reliably: the real gap between two word-tokens
belonging to the *same* space-grouped number is ~1.8pt on this table;
the gap between two different *columns* is ~24-30pt (confirmed by measuring
both on a real row this session) -- a wide, unambiguous margin. Numbers are
reassembled from consecutive word-tokens within a small gap threshold,
regardless of whether the renderer used commas (already one word,
gap-clustering is a no-op) or spaces (several words, joined here).

Usage:  python3 scripts/annual_reports_eib.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, MANUAL_DIR, REPO, REPORTS_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402
from annual_reports import fetch  # noqa: E402

ANNUAL_REPORTS_CSV = MANUAL_DIR / "annual_reports.csv"
TARGET = EXTRACTED_DIR / "shares_eib.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_eib_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_NO_VOTING_NOTE = (
    "EIB has no per-member voting-power percentage: statutory voting rules "
    "are not reducible to a single one-share/one-vote figure (Source_Map "
    "caveat, docs/manual/shares_snapshot_2026-08-25.xlsx)."
)

_TABLE_TITLE = "statement of subscriptions to the capital of the bank"
# 2007's PDF drops the spaces inside multi-word names.
_NAME_FIXUPS = {"UNITEDKINGDOM": "United Kingdom", "CZECHREPUBLIC": "Czech Republic", "SLOVAKREPUBLIC": "Slovakia",
                "UnitedKingdom": "United Kingdom", "CzechRepublic": "Czech Republic", "SlovakRepublic": "Slovakia"}
_SAME_ROW_TOLERANCE = 2.0  # pt, words within this of each other's `top` are the same row
_SAME_NUMBER_GAP = 10.0  # pt, gap below this joins two word-tokens into one number (see docstring)


def _is_number_token(text: str) -> bool:
    return text.replace(",", "").isdigit() or (text.rstrip(",").replace(",", "").isdigit() and text.endswith(","))


def _group_into_rows(words: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    current: list[dict] = []
    current_top: float | None = None
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if current_top is None or word["top"] - current_top > _SAME_ROW_TOLERANCE:
            if current:
                rows.append(current)
            current = [word]
            current_top = word["top"]
        else:
            current.append(word)
    if current:
        rows.append(current)
    return rows


def _parse_table_row(row_words: list[dict]) -> tuple[str, float] | None:
    """A table row's words, left to right -> (name, first_number) or None if
    this row has no numeric content at all (a wrapped name continuation, a
    footnote line, etc.)."""

    row_words = sorted(row_words, key=lambda w: w["x0"])
    name_parts: list[str] = []
    i = 0
    while i < len(row_words) and not _is_number_token(row_words[i]["text"]):
        name_parts.append(row_words[i]["text"])
        i += 1
    if i >= len(row_words):
        return None  # no numbers on this line at all

    digits = [row_words[i]["text"].replace(",", "")]
    prev = row_words[i]
    i += 1
    while i < len(row_words) and _is_number_token(row_words[i]["text"]):
        gap = row_words[i]["x0"] - prev["x1"]
        if gap > _SAME_NUMBER_GAP:
            break  # a real column boundary, not a thousands-group space
        digits.append(row_words[i]["text"].replace(",", ""))
        prev = row_words[i]
        i += 1

    name = " ".join(name_parts).rstrip("(*)").strip()
    amount = float("".join(digits))
    return name, amount


def _read_table(words: list[dict]) -> tuple[list[tuple[str, float]], float | None]:
    """Member rows from the first resolvable country to the Total row (or, where
    the total is printed unlabelled, to the end of the run of members)."""

    raw_rows: list[tuple[str, float]] = []
    total: float | None = None
    for row_words in _group_into_rows(words):
        parsed = _parse_table_row(row_words)
        if parsed is None:
            continue
        name, amount = parsed
        name = name.strip()
        if name.lower() == "total" and raw_rows:
            total = amount
            break
        if name and iso3_from_name(_NAME_FIXUPS.get(name, name)):
            raw_rows.append((name, amount))
        elif raw_rows and total is None and not name:
            break  # unlabelled total row after the members
    return raw_rows, total


def _split_by_identity(digits: str) -> int | None:
    """Subscribed capital from a run of digits that is subscribed || uncalled ||
    paid-in with the spacing lost (EIB 2003's text layer): the one split where
    subscribed = uncalled + paid-in."""

    hits = [
        int(digits[:i])
        for i in range(1, len(digits) - 1)
        for j in range(i + 1, len(digits))
        if digits[i] != "0" and digits[j] != "0" and int(digits[:i]) == int(digits[i:j]) + int(digits[j:])
    ]
    return hits[0] if len(hits) == 1 else None


def _read_table_text(text: str) -> tuple[list[tuple[str, float]], float | None]:
    """The same table from a page's text lines, for years whose word gaps are
    unusable and only the identity subscribed = uncalled + paid-in pins the
    columns down."""

    import re

    rows: list[tuple[str, float]] = []
    total = None
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z .]*?)\s*(\d[\d ]{20,})$", line.strip())
        if match:
            name = match.group(1).strip()
            if iso3_from_name(_NAME_FIXUPS.get(name, name)):
                subscribed = _split_by_identity(match.group(2).replace(" ", ""))
                if subscribed:
                    rows.append((name, float(subscribed)))
        elif rows and re.match(r"^\d[\d ]{20,}$", line.strip()) and total is None:
            total = float(_split_by_identity(line.strip().replace(" ", "")) or 0) or None
    return rows, total


def parse_pdf(path: Path, year: int, source_url: str) -> tuple[list[dict], list[dict]]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        compact_title = _TABLE_TITLE.replace(" ", "")

        def is_table_page(page) -> bool:
            # Some years' text layers drop the spaces ("SubscriptionstotheCapital..."), and
            # the prose page about own funds mentions the title's words too, so the page
            # must also carry the Germany row's figures.
            text = (page.extract_text() or "").lower()
            return compact_title in text.replace(" ", "") and "germany" in text and any(c.isdigit() for c in text.split("germany", 1)[1][:40])

        candidates = [i for i, page in enumerate(pdf.pages) if is_table_page(page)]
        if not candidates:
            raise SystemExit(f"error: could not find '{_TABLE_TITLE}' in {path}")
        best = None
        for page_index in candidates:
            raw_rows, total = _read_table(pdf.pages[page_index].extract_words())
            text_rows, text_total = _read_table_text(pdf.pages[page_index].extract_text() or "")
            if len(text_rows) > len(raw_rows):
                raw_rows, total = text_rows, text_total
            if best is None or len(raw_rows) > len(best[0]):
                best = (raw_rows, total, page_index)
        raw_rows, total, page_index = best

    # Denominator = the members' own sum (2005 prints the total row unlabelled); a
    # printed Total, where present, must agree.
    summed = sum(a for _, a in raw_rows)
    if summed <= 0 or (total is not None and abs(summed - total) > 0.001 * total):
        raise SystemExit(f"error: {path}: members sum to {summed:,.0f} but printed Total is {total}")
    total = summed

    rows: list[dict] = []
    unresolved: list[dict] = []
    for name, amount in raw_rows:
        iso3 = iso3_from_name(_NAME_FIXUPS.get(name, name))
        if not iso3:
            unresolved.append({"year": year, "name_raw": name})
            continue
        rows.append({
            "bank": "EIB", "iso3": iso3, "year": year,
            "capital_share_pct": round(amount / total * 100, 6),
            "voting_power_pct": "",
            "source_url": source_url,
            "note": _NO_VOTING_NOTE,
        })
    return rows, unresolved


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "EIB":
            continue
        year = int(row["year"])
        url = row["url"]
        path = fetch(url, f"eib_fs_{year}.pdf")
        rows, unresolved = parse_pdf(path, year, url)
        all_rows += rows
        all_unresolved += unresolved
        total_capital = sum(r["capital_share_pct"] for r in rows)
        print(f"{year}: {len(rows)} rows, capital shares sum to {total_capital:.2f}% "
              f"({'OK' if 95 <= total_capital <= 105 else 'CHECK THIS'})")

    all_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, all_rows)
    write_csv(UNRESOLVED_REPORT, ["year", "name_raw"], all_unresolved)
    print(f"\n{len(all_rows)} rows -> {TARGET.relative_to(REPO)}")
    print(f"{len(all_unresolved)} unresolved names -> {UNRESOLVED_REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
