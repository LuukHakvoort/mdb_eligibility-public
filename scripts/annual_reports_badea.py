"""Parse BADEA's "Appendix I: BADEA's Share Capital" table (Member States'
Contributions) out of BADEA's annual reports.

A different, simpler table than CDB's or EIB's, confirmed by inspection:
"Country | <year> | <year-1>" -- both the current and prior year's paid-in
contribution amounts in one table, comma-grouped numbers (no space-grouping
ambiguity like EIB's older documents had). `capital_share_pct` is computed
against the table's own "Total" row for each of the two year columns
separately. **No voting-power figure exists in this table at all** --
matches Source_Map's own framing (BADEA's preferred measure is "Paid-in
member contribution share," with no voting-power column mentioned) --
`voting_power_pct` is left honestly blank, not guessed.

Country names are BADEA's own long official forms ("Hashemite Kingdom of
Jordan," "Kingdom of Saudi Arabia") -- resolved via `_reference.
iso3_from_name()`, with a narrow local fixup list for names it doesn't
already recognize (checked live, not assumed).

Usage:  python3 scripts/annual_reports_badea.py
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
TARGET = EXTRACTED_DIR / "shares_badea.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_badea_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_TABLE_TITLE = "member states’ contributions"
_ROW = re.compile(r"^([A-Za-z][A-Za-z '’.]*?)\s+([\d,]+)\s+([\d,]+)$")

# BADEA's own official-form names that don't already resolve via the shared
# codelist (checked live against every name this table actually uses, not
# guessed in advance).
_NAME_FIXUPS = {
    "Hashemite Kingdom of Jordan": "Jordan",
    "Kingdom of Bahrain": "Bahrain",
    "Republic of Tunisia": "Tunisia",
    "People’s Democratic Republic of Algeria": "Algeria",
    "Kingdom of Saudi Arabia": "Saudi Arabia",
    "Republic of Sudan": "Sudan",
    "Republic of Iraq": "Iraq",
    "Sultanate of Oman": "Oman",
    "State of Palestine": "Palestine, State of",
    "State of Qatar": "Qatar",
    "State of Kuwait": "Kuwait",
    "Lebanese Republic": "Lebanon",
    "State of Libya": "Libya",
    "Arab Republic of Egypt": "Egypt",
    "Kingdom of Morocco": "Morocco",
    "The Islamic Republic of Mauritania": "Mauritania",
}


def _resolve(name: str) -> str:
    return iso3_from_name(_NAME_FIXUPS.get(name, name))


def parse_pdf(path: Path, source_url: str) -> tuple[list[dict], list[dict]]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        page_index = next(
            (i for i, page in enumerate(pdf.pages) if _TABLE_TITLE in (page.extract_text() or "").lower()),
            None,
        )
        if page_index is None:
            raise SystemExit(f"error: could not find \"{_TABLE_TITLE}\" in {path}")
        text = pdf.pages[page_index].extract_text() or ""

    header_line = next((l for l in text.splitlines() if l.strip().startswith("Country ")), None)
    if header_line is None:
        raise SystemExit(f"error: no 'Country <year> <year>' header found on page {page_index} of {path}")
    years = [int(tok) for tok in header_line.split()[1:] if tok.isdigit()]
    if len(years) != 2:
        raise SystemExit(f"error: expected 2 years in header {header_line!r}, found {years}")

    raw_rows: list[tuple[str, float, float]] = []
    totals: tuple[float, float] | None = None
    for line in text.splitlines():
        if line.strip() == header_line.strip():
            continue  # "Country <year> <year>" itself also matches _ROW's shape -- not a data row
        match = _ROW.match(line.strip())
        if not match:
            continue
        name, val_a, val_b = match.groups()
        amounts = (float(val_a.replace(",", "")), float(val_b.replace(",", "")))
        if name.strip().lower() == "total":
            totals = amounts
        else:
            raw_rows.append((name.strip(), *amounts))

    if totals is None or totals[0] <= 0 or totals[1] <= 0:
        raise SystemExit(f"error: no 'Total' row found on page {page_index} of {path} -- can't compute shares")

    rows: list[dict] = []
    unresolved: list[dict] = []
    for name, val_a, val_b in raw_rows:
        iso3 = _resolve(name)
        if not iso3:
            unresolved.append({"years": years, "name_raw": name})
            continue
        for year, value, total in zip(years, (val_a, val_b), totals):
            rows.append({
                "bank": "BADEA", "iso3": iso3, "year": year,
                "capital_share_pct": round(value / total * 100, 6),
                "voting_power_pct": "",
                "source_url": source_url,
                "note": "No voting-power figure published in this table.",
            })
    return rows, unresolved


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "BADEA" or row.get("document"):  # document set = read by annual_reports_badea_annex.py
            continue
        url = row["url"]
        path = fetch(url, f"badea_ar_{row['year']}.pdf")
        rows, unresolved = parse_pdf(path, url)
        all_rows += rows
        all_unresolved += unresolved
        for year in sorted({r["year"] for r in rows}):
            year_rows = [r for r in rows if r["year"] == year]
            total_capital = sum(r["capital_share_pct"] for r in year_rows)
            print(f"{year}: {len(year_rows)} rows, capital shares sum to {total_capital:.2f}% "
                  f"({'OK' if 95 <= total_capital <= 105 else 'CHECK THIS'})")

    all_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, all_rows)
    write_csv(UNRESOLVED_REPORT, ["years", "name_raw"], all_unresolved)
    print(f"\n{len(all_rows)} rows -> {TARGET.relative_to(REPO)}")
    print(f"{len(all_unresolved)} unresolved names -> {UNRESOLVED_REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
