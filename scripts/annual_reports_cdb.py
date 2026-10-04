"""Parse CDB's "subscriptions by member countries and their voting power"
table (Note 19(c)/21(c)/etc. -- the note *number* shifts between years, so
this searches by content, not a fixed note number) out of CDB's annual
financial-statement PDFs.

**Not generic table detection** (verified this session: `pdfplumber.
extract_tables()` finds 0 tables on these pages -- they're borderless,
whitespace-aligned statement tables). Parses `extract_text()` output
line-by-line instead: a country name, then whichever of its numeric columns
are present. Real edge cases found by inspecting two real years (2019, 2024)
before writing this, not assumed:

- The five UK-territory rows (Anguilla, Montserrat, British Virgin Islands,
  Cayman Islands, Turks and Caicos Islands) are "considered a single member
  ... for the purpose of Articles 26 and 32" (a footnote on every page) --
  most of them have a capital-share percentage but no individual voting-power
  percentage at all. Handled by only requiring the first decimal percentage
  (capital share); voting power is written blank, not guessed, when a
  second one isn't present on that line.
- Footnote markers on territory names vary by year: "Anguilla1/" (2024) vs
  "Anguilla /1" (2019) -- stripped before country-name resolution.
- Section header, subtotal, "Additional subscriptions," and "Total -" rows
  are skipped explicitly, not accidentally matched as country rows.

Usage:  python3 scripts/annual_reports_cdb.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, MANUAL_DIR, REPO, REPORTS_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402
from annual_reports import fetch  # noqa: E402

ANNUAL_REPORTS_CSV = MANUAL_DIR / "annual_reports.csv"
TARGET = EXTRACTED_DIR / "shares_cdb.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_cdb_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_SKIP_PREFIXES = (
    "CARIBBEAN DEVELOPMENT BANK", "ORDINARY CAPITAL RESOURCES", "NOTES TO",
    "For the year ended", "(expressed in", "NOTE ", "The subscriptions by",
    "Regional States", "Non-Regional", "Sub-total", "Additional subscriptions",
    "Prepayment discount", "Total -", "Total ", "In accordance with Article",
    "1/", "2/", "Member Shares", "Voting Power", "Gross", "Receivable",
)

# Footnote markers this bank's PDFs attach to territory names, in either order.
_FOOTNOTE_MARKER = re.compile(r"\s*/?\d/?\s*$|\d/\s*$")
_DECIMAL = re.compile(r"\d+\.\d+")

# Names as CDB's own PDFs render them -> what _reference.iso3_from_name() needs.
_NAME_FIXUPS = {
    "St. Lucia": "Saint Lucia",
    "St. Vincent and the Grenadines": "Saint Vincent and the Grenadines",
    "St. Kitts and Nevis": "Saint Kitts and Nevis",
}


def _clean_name(raw: str) -> str:
    name = _FOOTNOTE_MARKER.sub("", raw).strip()
    return _NAME_FIXUPS.get(name, name)


def _parse_row(line: str) -> tuple[str, float, float | None] | None:
    line = line.strip()
    if not line or line[0].isdigit() or any(line.startswith(p) for p in _SKIP_PREFIXES):
        return None
    match = re.match(r"^([A-Za-z][A-Za-z .'&/\d-]*?)\s+[\d,]", line)
    if not match:
        return None
    name = _clean_name(match.group(1))
    if not name or name[0].isdigit():
        return None
    decimals = _DECIMAL.findall(line)
    if not decimals:
        return None
    capital_pct = float(decimals[0])
    voting_pct = float(decimals[1]) if len(decimals) >= 2 else None
    return name, capital_pct, voting_pct


_YEAR_LABEL = re.compile(r"^(19|20)\d{2}$")


def _split_into_table_instances(pages_text: list[str]) -> list[tuple[int | None, list[str]]]:
    """CDB's own financial-statement PDFs repeat the whole subscriptions
    table twice per document -- current year and the comparative prior year
    (confirmed live: the 2024 document's pages 106-107 are headed "2024",
    pages 108-109 are the *same table*, headed "2023"). Splits the
    concatenated matched-page lines into (year, lines) chunks at each bare
    year-label line, rather than assuming every matched page belongs to the
    single year requested."""

    lines = [line for text in pages_text for line in text.splitlines()]
    instances: list[tuple[int | None, list[str]]] = []
    current_year: int | None = None
    current_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if _YEAR_LABEL.match(stripped):
            if current_lines:
                instances.append((current_year, current_lines))
            current_year = int(stripped)
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        instances.append((current_year, current_lines))
    return instances


def parse_pdf(path: Path, requested_year: int, source_url: str) -> tuple[list[dict], list[dict]]:
    import pdfplumber

    rows: list[dict] = []
    unresolved: list[dict] = []
    with pdfplumber.open(path) as pdf:
        page_texts = [page.extract_text() or "" for page in pdf.pages]
        # The table's "Non-Regional States" continuation page doesn't repeat
        # "subscriptions by member" (only the intro sentence does) -- confirmed
        # on both 2019 and 2024 documents, always the very next page.
        matched_indices = {i for i, text in enumerate(page_texts) if "subscriptions by member" in text.lower()}
        matched_indices |= {i + 1 for i in matched_indices if i + 1 < len(page_texts)}
        matched_pages_text = [page_texts[i] for i in sorted(matched_indices)]
    for year, lines in _split_into_table_instances(matched_pages_text):
        if year is None:
            continue  # couldn't find a year label for this chunk -- don't guess which year it is
        for line in lines:
            parsed = _parse_row(line)
            if parsed is None:
                continue
            name, capital_pct, voting_pct = parsed
            iso3 = iso3_from_name(name)
            if not iso3:
                unresolved.append({"year": year, "name_raw": name, "source_document_year": requested_year})
                continue
            rows.append({
                "bank": "CDB", "iso3": iso3, "year": year,
                "capital_share_pct": capital_pct,
                "voting_power_pct": voting_pct if voting_pct is not None else "",
                "source_url": source_url,
                "note": "" if voting_pct is not None else
                        "UK-territory bloc row: no individual voting-power percentage on this line.",
            })
    return rows, unresolved


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "CDB" or row["url"].startswith("file:"):
            continue  # file: rows are hand-downloaded reports, read by annual_reports_cdb_ar.py
        year = int(row["year"])
        url = row["url"]
        cache_name = f"cdb_fs_{year}.pdf"
        path = fetch(url, cache_name)
        rows, unresolved = parse_pdf(path, year, url)
        all_rows += rows
        all_unresolved += unresolved
        years_found = sorted({r["year"] for r in rows})
        print(f"document requested for {year}: found years {years_found}")
        for found_year in years_found:
            year_rows = [r for r in rows if r["year"] == found_year]
            total_capital = sum(r["capital_share_pct"] for r in year_rows)
            print(f"  {found_year}: {len(year_rows)} rows, capital shares sum to "
                  f"{total_capital:.2f}% ({'OK' if 95 <= total_capital <= 105 else 'CHECK THIS'})")

    # A document's comparative prior year may already be covered by another
    # document's own "current year" table -- keep the more directly-sourced
    # one (deduplicate by (iso3, year), preferring rows from the document
    # that names this year as its own current year, i.e. appears first).
    seen: set[tuple[str, int]] = set()
    deduped: list[dict] = []
    for row in all_rows:
        key = (row["iso3"], row["year"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    all_rows = deduped

    all_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, all_rows)
    write_csv(UNRESOLVED_REPORT, ["year", "name_raw", "source_document_year"], all_unresolved)
    print(f"\n{len(all_rows)} rows -> {TARGET.relative_to(REPO)}")
    print(f"{len(all_unresolved)} unresolved names -> {UNRESOLVED_REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
