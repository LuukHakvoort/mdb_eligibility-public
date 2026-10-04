"""Parse NDB's "Members Shareholding" slide out of NDB's own investor
presentations.

Real and cleaner than the other banks' tables: pre-computed percentages
already, no amounts to divide. Two things confirmed by inspection, not
assumed:

- **The slide is a two-column visual layout** (member list on the left,
  bullet-point commentary on the right) that `extract_text()` interleaves
  onto the same line for some rows (e.g. "China 18.76% <2 checkmark> Full
  member support for maintaining a very strong financial profile" is one
  extracted line) -- the regex here only anchors the country name and
  percentage at the *start* of the line, not the whole line, and ignores
  whatever commentary trails after.
- **"Prospective member" rows are explicitly skipped, not errors or
  guesses** -- NDB's own footnote: "admitted by NDB's Board of Governors
  and will officially become a member country once it deposits the
  instrument of accession," matching CLAUDE.md's Known Traps
  ("Prospective members are not members"). A presentation dated before a
  real accession (e.g. Uzbekistan's, officially June 2026) will correctly
  still show it as prospective -- this is a real historical snapshot, not
  stale data to "fix."

No voting-power figure is given (matches Source_Map: NDB's preferred
measure is "Subscribed-capital share" only).

Usage:  python3 scripts/annual_reports_ndb.py
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
TARGET = EXTRACTED_DIR / "shares_ndb.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_ndb_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_TABLE_TITLE = "members shareholding"
_ROW = re.compile(r"^([A-Za-z][A-Za-z .'-]*?)\s+([\d.]+)%")
_PROSPECTIVE_ROW = re.compile(r"^([A-Za-z][A-Za-z .'-]*?)\s+Prospective member")


def parse_pdf(path: Path, year: int, source_url: str) -> tuple[list[dict], list[dict]]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        page_index = next(
            (i for i, page in enumerate(pdf.pages) if _TABLE_TITLE in (page.extract_text() or "").lower()),
            None,
        )
        if page_index is None:
            raise SystemExit(f"error: could not find \"{_TABLE_TITLE}\" in {path}")
        text = pdf.pages[page_index].extract_text() or ""

    rows: list[dict] = []
    unresolved: list[dict] = []
    total = 0.0
    for line in text.splitlines():
        stripped = line.strip()
        if _PROSPECTIVE_ROW.match(stripped):
            continue  # not a member yet -- correctly excluded, not an error
        match = _ROW.match(stripped)
        if not match:
            continue
        name, pct_text = match.groups()
        pct = float(pct_text)
        iso3 = iso3_from_name(name.strip())
        if not iso3:
            unresolved.append({"year": year, "name_raw": name.strip()})
            continue
        total += pct
        rows.append({
            "bank": "NDB", "iso3": iso3, "year": year,
            "capital_share_pct": pct,
            "voting_power_pct": pct,
            "source_url": source_url,
            "note": "Voting power derived = capital share: NDB's financial statements state each member's votes equal its subscribed shares (FS 2021-2024).",
        })
    if not (95 <= total <= 105):
        raise SystemExit(f"error: capital shares on page {page_index} of {path} sum to {total:.2f}%, not ~100%")
    return rows, unresolved


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "NDB" or row.get("document"):
            continue
        year = int(row["year"])
        url = row["url"]
        path = fetch(url, f"ndb_investor_{year}.pdf")
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
