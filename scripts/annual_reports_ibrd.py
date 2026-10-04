"""IBRD's capital subscriptions and voting power per member, FY2003-FY2026,
from the "Statement of Subscriptions to Capital Stock and Voting Power" in
IBRD's own annual reports filed with the SEC (EDGAR, CIK 51120, form ANNLRPT).

Why EDGAR, and why it's better than IBRD's own website here: every fiscal year
is a uniform HTML filing with the full financial statements (each 3-9 MB), the
same table in every one, and stable URLs -- where worldbank.org's PDFs sit
under unguessable per-document hashes. sec.gov requires a User-Agent that
identifies the requester (403 without one); `annual_reports.USER_AGENT`
carries the project contact the user configured.

Columns per member: shares, % of total, total amount (USD million), amounts
paid in, amounts subject to call, number of votes, % of total votes. Capital
share = a member's shares over all members' shares; voting power = votes over
all votes (both recomputed from the raw counts, then reconciled to the table's
own Total row).

The table is split across several consecutive HTML tables (one per printed
page), so tables are collected from the first one that has the member/votes
header until a "Total" row has been seen. FY2006 and FY2007 have no
June-30-dated filing on EDGAR; their financial statements sit in the
September information statements, which carry the same table.

Panel year = the calendar year of the June 30 statement date (FY2024 -> 2024),
by the user's decision -- deliberately not the n-1 rule Decision 4 uses for
income classifications, since a shareholding position is a point-in-time fact
on the statement date.

Usage:  python3 scripts/annual_reports_ibrd.py
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
TARGET = EXTRACTED_DIR / "shares_ibrd.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_ibrd_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_NUMBER = re.compile(r"^\d+(?:\.\d+)?$")
_FOOTNOTE = re.compile(r"\s*\(\s*[a-z]\s*\)\s*$|\s+[a-z]$")

# Names as IBRD's own tables render them (the capitalisation of "Former
# Yugoslav Republic Of" even varies by year) -> what _reference.iso3_from_name()
# needs. "Serbia and Montenegro" (FY2005-2006, before the split) is a genuine
# predecessor state the shared resolver deliberately doesn't map -- left
# unresolved, not guessed at (reference_conventions.md section 7).
_NAME_FIXUPS = {
    "Macedonia, former Yugoslav Republic of": "North Macedonia",
    "Macedonia, Former Yugoslav Republic of": "North Macedonia",
    "Macedonia, Former Yugoslav Republic Of": "North Macedonia",
    "Kosovo, Republic of": "Kosovo",
    "Cabo Verde, Republic of": "Cabo Verde",
    "Naoero": "Nauru",  # FY2026's own spelling
}


def _numbers(cells: list[str]) -> list[float]:
    values = []
    for cell in cells:
        cleaned = cell.replace("$", "").replace(",", "").replace("%", "").strip()
        if _NUMBER.match(cleaned):
            values.append(float(cleaned))
    return values


def parse_member_row(cells: list[str]) -> tuple[str, float, float] | None:
    """(name, shares, votes) from one table row, or None if it isn't a data
    row. Layout: name, shares, % of total, total amount, paid in, subject to
    call, votes, % of votes -- with blank spacer cells and stray "$"/"%"
    cells between them that vary by year, so only the *numeric* cells are
    read: shares is the first, votes the second-to-last."""

    if not cells:
        return None
    name = _FOOTNOTE.sub("", cells[0].strip())
    if not name or name.lower() in {"member", "subscriptions", "voting power"}:
        return None
    numbers = _numbers(cells[1:])
    if len(numbers) < 5 or numbers[0] != int(numbers[0]) or numbers[-2] != int(numbers[-2]):
        return None
    return name, numbers[0], numbers[-2]


def _member_tables(tables: list[list[list[str]]]) -> list[list[list[str]]]:
    """The consecutive tables making up the statement: from the first that
    carries both the Subscriptions/Voting Power header and a member row, until
    one has a Total row."""

    start = None
    for index, table in enumerate(tables):
        head = " ".join(" ".join(row) for row in table[:5]).lower()
        if "voting power" in head and "subscriptions" in head and any(
            row and row[0].strip() == "Afghanistan" for row in table
        ):
            start = index
            break
    if start is None:
        return []
    collected = []
    for table in tables[start:]:
        collected.append(table)
        if any(row and row[0].strip().lower().startswith("total") and parse_member_row(row) for row in table):
            break
    return collected


# FY2003 and FY2004 are plain-text filings (EDGAR .txt), not HTML: dot-leader
# rows, "Afghanistan......  300  0.02%  $ 36.2  $ 3.6  $ 32.6  550  0.03%".
_TEXT_HEADING = re.compile(r"STATEMENT OF SUBSCRIPTIONS TO\s+CAPITAL STOCK AND VOTING POWER\s+June 30, (\d{4})")
_TEXT_ROW = re.compile(
    r"^([A-Za-z][^\n]*?)\.{2,}\s*([\d,]+)\s+[\d.]+%?\s+\$?\s*[\d,.]+\s+\$?\s*[\d,.]+\s+\$?\s*[\d,.]+\s+([\d,]+)\s+[\d.]+%?\s*$"
)


def _text_member_rows(text: str, year: int, path: Path) -> list[list[str]]:
    """Plain-text filings: rows as the same [name, shares, ..., votes, ...]
    cell lists the HTML path yields, from the section headed "STATEMENT OF
    SUBSCRIPTIONS TO CAPITAL STOCK AND VOTING POWER, June 30, <year>"."""

    match = next((m for m in _TEXT_HEADING.finditer(text) if int(m.group(1)) == year), None)
    if match is None:
        raise SystemExit(f"error: {path}: no 'Subscriptions to Capital Stock and Voting Power, June 30, {year}' heading")
    section = text[match.start():match.start() + 60000]
    # The Total rows sit in a second <Table> after the members', so cut at the
    # statement's closing footer, not the first </Table>.
    end = section.upper().find("NOTES TO FINANCIAL STATEMENTS ARE AN INTEGRAL")
    section = section[:end] if end > 0 else section
    rows: list[list[str]] = []
    for line in section.splitlines():
        row = _TEXT_ROW.match(line.rstrip())
        if row:
            rows.append([row.group(1).strip(), row.group(2), "0", "0", "0", "0", row.group(3), "0"])
        elif line.startswith("Total") and "June 30" in line:
            numbers = re.findall(r"\$?\s*(\d[\d,]{3,})", line.partition("..")[2])  # after the label's dot leaders
            if len(numbers) >= 2:
                rows.append([f"Total\u2014June 30, {year}", numbers[0], "0", "0", "0", "0", numbers[-1], "0"])
    return rows


def parse_filing(path: Path, year: int, source_url: str) -> tuple[list[dict], list[dict]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".txt":
        member_tables = [_text_member_rows(text, year, path)]
    else:
        member_tables = _member_tables(parse_tables(text))
    if not member_tables or not member_tables[0]:
        raise SystemExit(f"error: no Subscriptions/Voting Power table found in {path} for {year}")

    members: dict[str, tuple[float, float]] = {}
    stated = None
    for table in member_tables:
        for row in table:
            parsed = parse_member_row(row)
            if parsed is None:
                continue
            name, shares, votes = parsed
            if name.lower().startswith("total"):
                # Two Total rows: "Total--June 30, 2015" and then the prior-year
                # comparative "Total--June 30, 2014", which has no percentage
                # cells -- the first is the current year's.
                if stated is None:
                    if f"June 30, {year}" not in name:
                        raise SystemExit(
                            f"error: {path}: first Total row is {name!r}, expected it to be dated June 30, {year} "
                            f"-- wrong filing for this fiscal year"
                        )
                    stated = (shares, votes)
            else:
                members[name] = (shares, votes)
    if stated is None:
        raise SystemExit(f"error: {path} for {year}: no Total row found to reconcile against")

    total_shares = sum(s for s, _ in members.values())
    total_votes = sum(v for _, v in members.values())
    for label, summed, printed in (("shares", total_shares, stated[0]), ("votes", total_votes, stated[1])):
        if not 99.95 <= summed / printed * 100 <= 100.05:
            raise SystemExit(
                f"error: {path} for {year}: member {label} sum to {summed / printed * 100:.3f}% of the printed "
                f"Total ({len(members)} members parsed)"
            )

    rows: list[dict] = []
    unresolved: list[dict] = []
    for name, (shares, votes) in members.items():
        iso3 = iso3_from_name(_NAME_FIXUPS.get(name, name))
        if not iso3:
            unresolved.append({"year": year, "name_raw": name})
            continue
        rows.append({
            "bank": "IBRD", "iso3": iso3, "year": year,
            "capital_share_pct": round(shares / total_shares * 100, 6),
            "voting_power_pct": round(votes / total_votes * 100, 6),
            "source_url": source_url,
            "note": "",
        })
    return rows, unresolved


def cache_name_for(url: str) -> str:
    """sec_<cik>_<accession folder>_<document>, derived from the URL itself so
    the cache never depends on anything but the row in annual_reports.csv."""

    parts = url.split("/")
    return f"sec_{parts[-3]}_{parts[-2]}_{parts[-1]}"


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "IBRD":
            continue
        year, url = int(row["year"]), row["url"]
        path = fetch(url, cache_name_for(url), expect="any", delay=0.4)
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
