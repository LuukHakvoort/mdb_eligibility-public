"""NDB's capital share and voting power per member, from the "Paid-in capital"
note of NDB's annual financial statements (FY2021-FY2023 FS, FY2024 annual report).

Each note prints a statement of capital subscriptions -- shares per member -- for the
report's year and the prior year, and states that "the voting power of each member
shall be equal to the number of its subscribed shares", so capital share and voting
power are the same percentage: shares over the members' total subscribed shares
(reconciled to the printed Total row). Panel year = the block's own 31 December.

2015-2019: FS 2021 shows the 31 December 2020 position as the five founders at
100,000 shares each (500,000 = the whole subscribed capital) and its Note 21 says
Bangladesh and UAE were first admitted in 2021, so 2015-2019 carry the same five
equal shares; those rows say so in their note (derived, not printed for those years --
the FS for FY2016-2020 are not on ndb.int).

Usage:  python3 scripts/annual_reports_ndb_fs.py
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
TARGET = EXTRACTED_DIR / "shares_ndb_fs.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_ndb_fs_unresolved.csv"
FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_BLOCK_HEADING = re.compile(r"^\s*as at december 31, (\d{4})\b(?!.*as at)", re.I)
_ROW = re.compile(r"^([A-Za-z][A-Za-z .]*?)\s+(\d[\d,]*)\s+\d[\d,]*\s+\d[\d,]*\s+\d[\d,]*\s+")
_NAME_FIXUPS = {"UAE": "United Arab Emirates"}
_DERIVED_FROM_2020 = "No admissions before 2021 (FS 2021 Note 21); five founders at 100,000 shares each, as printed for 31 Dec 2020."


def parse_blocks(text: str) -> dict[int, dict[str, float]]:
    """{year: {member name: shares}} for each single-date subscription table."""

    blocks: dict[int, dict[str, float]] = {}
    year = None
    current: dict[str, float] = {}
    for line in text.splitlines():
        heading = _BLOCK_HEADING.match(line)
        if heading:
            year, current = int(heading.group(1)), {}
            # FS 2023 labels its prior-year block "31 December 2023" a second time (a typo:
            # it totals 514,980 shares, the 31 Dec 2022 position printed in FS 2022).
            while year in blocks:
                year -= 1
            continue
        if year is None:
            continue
        row = _ROW.match(line.strip())
        if not row:
            continue
        name, shares = row.group(1).strip(), float(row.group(2).replace(",", ""))
        if name.lower() == "total":
            members_total = sum(current.values())
            if members_total == shares:
                blocks.setdefault(year, current)
            year = None
        else:
            current[name] = shares
    return blocks


def rows_for(year: int, members: dict[str, float], url: str, note: str = "") -> tuple[list[dict], list[dict]]:
    total = sum(members.values())
    rows, unresolved = [], []
    for name, shares in members.items():
        iso3 = iso3_from_name(_NAME_FIXUPS.get(name, name))
        if not iso3:
            unresolved.append({"year": year, "name_raw": name})
            continue
        share = round(shares / total * 100, 6)
        rows.append({"bank": "NDB", "iso3": iso3, "year": year, "capital_share_pct": share, "voting_power_pct": share,
                     "source_url": url, "note": note})
    return rows, unresolved


def main() -> int:
    import pdfplumber

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    seen: set[int] = set()
    founders_2020: tuple[dict[str, float], str] | None = None
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "NDB" or row.get("document") != "financial_statements":
            continue
        url = row["url"]
        path = fetch(url, f"ndb_fs_{row['year']}.pdf", delay=1.0, timeout=180)
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if "statement of capital subscriptions" in page_text.lower():
                    text += page_text + "\n"
        for year, members in sorted(parse_blocks(text).items()):
            if year in seen:
                continue
            seen.add(year)
            rows, unresolved = rows_for(year, members, url)
            all_rows += rows
            all_unresolved += unresolved
            if year == 2020:
                founders_2020 = (members, url)
            print(f"{year}: {len(rows)} members from {Path(url).name}")
    if founders_2020:
        members, url = founders_2020
        for year in range(2015, 2020):
            rows, _ = rows_for(year, members, url, _DERIVED_FROM_2020)
            all_rows += rows

    all_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, all_rows)
    write_csv(UNRESOLVED_REPORT, ["year", "name_raw"], all_unresolved)
    print(f"\n{len(all_rows)} rows -> {TARGET.relative_to(REPO)}")
    print(f"{len(all_unresolved)} unresolved names -> {UNRESOLVED_REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
