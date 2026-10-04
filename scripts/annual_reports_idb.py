"""IDB's capital share and voting power per member, FY2022-FY2025, from the
"Member countries -- subscribed voting shares / number of votes / % of total
votes" table in IDB's annual reports filed with the SEC (EDGAR, CIK 311670,
form ANNLRPT).

**This is the IDB source that isn't blocked.** iadb.org and publications.iadb.org
sit behind a Cloudflare bot-challenge that no plain HTTP client passes (see
docs/coding_decisions.md), but IDB's annual reports on sec.gov are ordinary
HTML. IDB only began filing ANNLRPT in 2023 (for FY2022), so this covers four
years; its earlier SEC filings are bond distribution reports, not Information
Statements. Older years still need IDB's own PDFs (Schedule I-4 of its financial
statements) placed by hand in data/raw/annual_reports/.

Capital share = subscribed voting shares over all members'; voting power =
votes over all votes -- both recomputed from the raw counts and reconciled to the
table's own "Grand total" row. (IDB's votes are shares plus a fixed membership
allotment -- 135 votes per member here -- so the two shares differ slightly.)

The table is found by content -- the first table whose member rows carry three
numbers (shares, votes, a decimal percentage) with the percentage summing to
~100 -- not by header wording, which is split across several rows differently in
FY2022-24 than in FY2025.

Panel year = the report's own 31 December.

Usage:  python3 scripts/annual_reports_idb.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mdbs_scraper_corrected"))
from mdbs_scraper.parsers import parse_tables  # noqa: E402

from _panel import EXTRACTED_DIR, MANUAL_DIR, REPO, REPORTS_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402
from annual_reports import fetch  # noqa: E402

ANNUAL_REPORTS_CSV = MANUAL_DIR / "annual_reports.csv"
TARGET = EXTRACTED_DIR / "shares_idb.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_idb_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_INTEGER = re.compile(r"^\d[\d,]*$")
_DECIMAL = re.compile(r"^\d+\.\d+$")

# Names as IDB's own tables render them -> what _reference.iso3_from_name()
# needs (filled in from what the runs report as unresolved).
_NAME_FIXUPS: dict[str, str] = {}


def parse_member_row(cells: list[str]) -> tuple[str, float, float, float] | None:
    """(name, shares, votes, % of votes) from one row: a name, two integers and
    a decimal percentage."""

    cells = [c.strip() for c in cells if c.strip()]
    if len(cells) != 4 or not (_INTEGER.match(cells[1]) and _INTEGER.match(cells[2]) and _DECIMAL.match(cells[3])):
        return None
    name = re.sub(r"\s*\(\d+\)$", "", cells[0])  # trailing footnote marker "(1)"
    return name, float(cells[1].replace(",", "")), float(cells[2].replace(",", "")), float(cells[3])


def _is_total(name: str) -> bool:
    return name.lower() == "grand total"


def _member_table(tables: list[list[list[str]]]) -> list[list[str]] | None:
    for table in tables:
        parsed = [parse_member_row(row) for row in table]
        members = [p for p in parsed if p and not p[0].lower().startswith(("total", "grand"))]
        if len(members) >= 20 and any(p and _is_total(p[0]) for p in parsed) and 99.5 <= sum(p[3] for p in members) <= 100.5:
            return table
    return None


def parse_filing(path: Path, year: int, source_url: str) -> tuple[list[dict], list[dict]]:
    table = _member_table(parse_tables(path.read_text(encoding="utf-8", errors="replace")))
    if table is None:
        raise SystemExit(f"error: no member shares/votes table found in {path} for {year}")

    members: dict[str, tuple[float, float]] = {}
    stated = None
    for row in table:
        parsed = parse_member_row(row)
        if parsed is None:
            continue
        name, shares, votes, _ = parsed
        if _is_total(name):
            stated = (shares, votes)
        elif not name.lower().startswith("total"):
            members[name] = (shares, votes)
    if stated is None:
        raise SystemExit(f"error: {path} for {year}: no Grand total row found to reconcile against")

    total_shares = sum(s for s, _ in members.values())
    total_votes = sum(v for _, v in members.values())
    for label, summed, printed in (("shares", total_shares, stated[0]), ("votes", total_votes, stated[1])):
        if summed != printed:
            raise SystemExit(
                f"error: {path} for {year}: member {label} sum to {summed:,.0f} but the printed Grand total is "
                f"{printed:,.0f} ({len(members)} members parsed)"
            )

    rows: list[dict] = []
    unresolved: list[dict] = []
    for name, (shares, votes) in members.items():
        iso3 = iso3_from_name(_NAME_FIXUPS.get(name, name))
        if not iso3:
            unresolved.append({"year": year, "name_raw": name})
            continue
        rows.append({
            "bank": "IDB", "iso3": iso3, "year": year,
            "capital_share_pct": round(shares / total_shares * 100, 6),
            "voting_power_pct": round(votes / total_votes * 100, 6),
            "source_url": source_url,
            "note": "",
        })
    return rows, unresolved


def cache_name_for(url: str) -> str:
    parts = url.split("/")
    return f"sec_{parts[-3]}_{parts[-2]}_{parts[-1]}"


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "IDB" or row.get("document") != "sec_annual_report":
            continue
        year, url = int(row["year"]), row["url"]
        path = fetch(url, cache_name_for(url), expect="any", delay=0.4, timeout=120)
        rows, unresolved = parse_filing(path, year, url)
        all_rows += rows
        all_unresolved += unresolved
        print(f"{year}: {len(rows)} members ({len(unresolved)} unresolved this document)")

    all_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, all_rows)
    write_csv(UNRESOLVED_REPORT, ["year", "name_raw"], all_unresolved)
    print(f"\n{len(all_rows)} rows -> {TARGET.relative_to(REPO)}")
    print(f"{len(all_unresolved)} unresolved names -> {UNRESOLVED_REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
