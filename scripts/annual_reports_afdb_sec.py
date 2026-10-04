"""AfDB's capital share and voting power per member, from AfDB's annual reports
(Information Statement) filed on SEC EDGAR as form ANNLRPT (CIK 785677).

Each report carries, in the notes to its financial statements, a table of every
member's total shares, % of total shares, amount paid, callable capital, number
of votes and % of total voting power, as at 31 December of the previous year
(reports are filed in mid-year: the filing dated Aug 2010 is the position at 31
Dec 2009). The panel year is that statement date's year, read from the
document's own sentence "A list of the members at 31 December <year> showing
each member's voting power and the amount of its subscription..." -- not from
the filing date.

This is AfDB-proper only (ADF is a separate institution with its own
statements; see docs/coding_decisions.md), and it is the AfDB *capital* source
`annual_reports_afdb.py`'s voting-only monthly statement never had.

Capital share = a member's shares over all members' shares; voting power =
votes over all votes, both recomputed from the raw counts and reconciled to the
table's own TOTAL row.

Usage:  python3 scripts/annual_reports_afdb_sec.py
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
TARGET = EXTRACTED_DIR / "shares_afdb_sec.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_afdb_sec_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_NUMBER = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
_STATEMENT_YEAR = re.compile(r"members? (?:at|as at|as of) (?:the )?31\s*December (\d{4}) showing", re.I)

# Names as AfDB's own tables render them -> what _reference.iso3_from_name()
# needs (filled in from what the runs report as unresolved).
_NAME_FIXUPS = {
    "KOREA": "Korea, Rep.", "Korea": "Korea, Rep.", "Korea*": "Korea, Rep.",
    "U.K.": "United Kingdom", "U.S.A.": "United States", "U. S.A.": "United States",
    "SAO TOME & PRINCIPE": "Sao Tome and Principe", "Sao Tome & Principe": "Sao Tome and Principe",
    "S\u00e3o Tom\u00e9 & Pr\u00edncipe": "Sao Tome and Principe",
    "Cote d\u2019lvoire": "Cote d'Ivoire",  # 2010-2011's own typo: lower-case L for capital I
    "Republic of the Congo": "Congo, Rep.",
}


def statement_year(text: str) -> int | None:
    match = _STATEMENT_YEAR.search(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).replace("&nbsp;", " "))
    return int(match.group(1)) if match else None


def parse_member_row(cells: list[str]) -> tuple[str, list[float]] | None:
    """(name, the six numbers). Layout: [serial], name, total shares, % of
    shares, amount paid, callable capital, number of votes, % of voting power --
    the serial is its own cell in most years and glued onto the name ("1
    Algeria") in others, so only the numeric cells after the name are read."""

    cells = [c.strip() for c in cells if c.strip()]
    if len(cells) < 7:
        return None
    if _NUMBER.match(cells[0].replace(",", "")) and not _NUMBER.match(cells[1].replace(",", "")):
        cells = cells[1:]  # serial number in its own cell
    name = re.sub(r"^\d+\s+", "", cells[0])  # serial glued onto the name
    numbers = [float(c.replace(",", "")) for c in cells[1:] if _NUMBER.match(c)]
    if not name or _NUMBER.match(name) or len(numbers) != 6:
        return None
    return name, numbers


def _is_total(name: str) -> bool:
    return name.lower() in ("total", "grand total")


def _member_tables(tables: list[list[list[str]]]) -> list[list[list[str]]]:
    """The consecutive tables (one per printed page, with page-number-only
    tables between them) making up the member statement. Found by content,
    not header wording -- the header spans two or three rows split differently
    from year to year -- as the first run of tables whose member rows' two
    percentage columns each sum to ~100. (The loans-by-country tables have the
    same shape but only one percentage column.)"""

    for start in range(len(tables)):
        rows = [parse_member_row(row) for row in tables[start]]
        if sum(1 for r in rows if r) < 10:
            continue
        collected: list[list[list[str]]] = []
        for table in tables[start:start + 8]:
            parsed = [parse_member_row(row) for row in table]
            if collected and not any(parsed):
                continue  # a page-number-only table between two pages
            collected.append(table)
            if any(p and _is_total(p[0]) for p in parsed):
                break
        members = [p for table in collected for row in table if (p := parse_member_row(row)) and not p[0].lower().startswith(("sub", "total", "grand"))]
        if len(members) >= 30 and 99 <= sum(n[1] for _, n in members) <= 101 and 99 <= sum(n[5] for _, n in members) <= 101:
            return collected
    return []


def parse_filing(path: Path, source_url: str) -> tuple[int, list[dict], list[dict]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    year = statement_year(text)
    if year is None:
        raise SystemExit(f"error: {path}: no 'members at 31 December <year> showing' sentence to date the table by")
    member_tables = _member_tables(parse_tables(text))
    if not member_tables:
        raise SystemExit(f"error: no shares/votes member table found in {path}")

    members: dict[str, tuple[float, float]] = {}
    stated = None
    for table in member_tables:
        for row in table:
            parsed = parse_member_row(row)
            if parsed is None:
                continue
            name, numbers = parsed
            shares, votes = numbers[0], numbers[4]
            if _is_total(name):
                stated = stated or (shares, votes)
            elif not name.lower().startswith(("sub", "total")):
                members[name] = (shares, votes)
    if stated is None:
        raise SystemExit(f"error: {path}: no TOTAL row found to reconcile against")

    total_shares = sum(s for s, _ in members.values())
    total_votes = sum(v for _, v in members.values())
    for label, summed, printed in (("shares", total_shares, stated[0]), ("votes", total_votes, stated[1])):
        if not 99.95 <= summed / printed * 100 <= 100.05:
            raise SystemExit(
                f"error: {path} (statement year {year}): member {label} sum to {summed / printed * 100:.3f}% of the "
                f"printed TOTAL ({len(members)} members parsed)"
            )

    rows: list[dict] = []
    unresolved: list[dict] = []
    for name, (shares, votes) in members.items():
        iso3 = iso3_from_name(_NAME_FIXUPS.get(name, name))
        if not iso3:
            unresolved.append({"year": year, "name_raw": name})
            continue
        rows.append({
            "bank": "AfDB", "iso3": iso3, "year": year,
            "capital_share_pct": round(shares / total_shares * 100, 6),
            "voting_power_pct": round(votes / total_votes * 100, 6),
            "source_url": source_url,
            "note": "",
        })
    return year, rows, unresolved


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
        if row.get("bank") != "AfDB" or row.get("document") != "sec_annual_report":
            continue
        expected, url = int(row["year"]), row["url"]
        path = fetch(url, cache_name_for(url), expect="any", delay=0.4, timeout=120)
        year, rows, unresolved = parse_filing(path, url)
        if year != expected:
            raise SystemExit(f"error: {url}: indexed as {expected} but the document's own statement date is {year}")
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
