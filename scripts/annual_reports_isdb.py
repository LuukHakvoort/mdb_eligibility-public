"""Parse IsDB's "Statement of IsDB Share Capital Subscription" and "Statement
of IsDB Voting Power" annexes out of its annual-report PDFs -- shares
history for IsDB, which `scripts/shares_wayback_isdb.py` deliberately never
covered (its member_countries.json has accession dates only).

Both a capital share and a voting share are published for every member, every
year -- better coverage than most banks in this project. Three real layouts
across the years fetched, all confirmed live on the actual pages:

- **Combined table** (2011-2015, Hijri fiscal years): one table, one row per
  member -- shares, called-up/callable/total capital, "% of total", paid-up/
  overdue/not-yet-due, then votes and "% voting", all on one line. In 2014
  the page also carries an unrelated sidebar whose text is glued onto the end
  of some rows, so the row pattern is anchored only at the line's *start*.
- **Split annexes** (2018 onward): capital in one annex ("5A"/"6A"), voting
  in the next ("5B"/"6B"), two separate tables. 2018-2020 prefix every row with
  a running S/N number; 2024 does not.
- Anything that doesn't match either shape is treated as not-a-row, never
  guessed at.

Everything is recomputed from the raw share/vote counts rather than copying
the printed percentages: the printed "% of total" is relative to the
*authorized* capital (including a small unallocated "Uncommitted" reserve, ~1%
in 2013/2014/2020) in some years and to subscribed capital in others, and
rounds to two decimals -- so it isn't comparable across years. Every share
here is a share of the members' *own* subscribed total, the same basis used
for CABEI and EBRD. Each document's own printed "Sub-Total" row is the
cross-check: the parsed members must sum to it.

Fiscal years: IsDB reported on the lunar Hijri year until 2015, then switched
to the calendar year. A Hijri year is ~354 days, so year-end dates drift ~11
days earlier each Gregorian year -- Mar 2003, Feb 2004 ... Jan 2007, Jan 2008,
Dec 2008 ... Nov 2011 -- and the statements themselves are sometimes dated a few
weeks after year-end (1429H's is 23 Mar 2009). Each statement is assigned to the
calendar year whose 31 December is *nearest* its date, which gives exactly one
statement per year (1427H, 19 Jan 2007 -> 2006; 1428H, 9 Jan 2008 -> 2007; 1429H,
23 Mar 2009 -> 2008); a plain "year of the date" rule would put two statements in
2008 and none in 2007. The exact as-at date is in
data/manual/annual_reports.csv's note.

Usage:  python3 scripts/annual_reports_isdb.py
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
TARGET = EXTRACTED_DIR / "shares_isdb.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_isdb_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

# The printed name for this bank's own totals rows -- excluded from members,
# used as the cross-check.
_STATED_TOTAL_NAMES = {"sub-total", "sub total", "subtotal"}
# Rows in the tables that aren't members: the Grand Total (equal to the
# Sub-Total plus the unallocated reserve), the "Uncommitted" reserve itself
# ("Uncommited" in 2025's own spelling) -- shares nobody holds yet -- and the
# bare "Total" some voting annexes print instead of a Sub-Total.
_NOT_A_MEMBER = {"grand total", "total", "uncommitted", "uncommited", "net shortfall"}
_HEADING = re.compile(r"share capital subscription|subscriptions to capital stock|statement of isdb voting power", re.I)

# Names as IsDB's own PDFs render them -> what _reference.iso3_from_name()
# needs. Checked live against every name in the annexes fetched.
_NAME_FIXUPS = {
    "Kyrgyz": "Kyrgyz Republic",  # 2013's truncated form
    "Kyrghyz": "Kyrgyz Republic",  # 2019-2023's own misspelling, in the annexes themselves
    "Islamic Republic of Iran": "Iran",  # 2007's own long form
}

# One numeric-ish cell: a number (possibly negative: 2012 prints "-0.00"), "*"
# (nil), "-" (nil), or "(0.00)" (a negative/rounding adjustment) -- all appear
# in the overdue/not-yet-due columns.
_T = r"(?:-?[\d,.]+%?|\*|-|\([\d,.]+\))"
# A country name: anything that doesn't start with a digit and contains none
# (S/N numbers are stripped separately, ahead of the name).
_NAME = r"([^\d\s*(][^\d]*?)"
_SN = r"^(?:\d{1,2}\.?\s+)?"  # "1 Afghanistan" or, in 2009, "1. Afghanistan"
# Sidebar text glued onto the end of a row (confirmed on 2014 and 2019: annex
# titles, page-range labels like "6A-9B", "(1395H-2019G) 104") -- tolerated
# only when it starts with a letter, a "(", or a digit-then-letter, so a row
# from some *other* table that happens to carry more plain numbers after
# these ones still doesn't match.
_TAIL = r"(?:\s+(?:[A-Za-z(]|\d+[A-Za-z]).*)?$"

# Combined layout: name, shares, then seven cells (called-up, callable,
# total, % of total, paid-up, overdue, not-yet-due), then votes and % voting.
# Votes can carry decimals in the Sub-Total row only (2015: "4,578,363.08").
_COMBINED_ROW = re.compile(
    _SN + _NAME + r"\s+([\d,]+)(?:\s+" + _T + r"){7}\s+([\d,]+(?:\.\d+)?)\s+([\d.]+%?)(?:\s|$)"
)
# 2007-2008 print six cells, not seven, between the share count and the votes:
# "% of total, callable, paid-in, overdue, not yet due" plus one amount column
# ("1 Afghanistan 993 0.07 9.93 4.930 2.600 1.172 1.228 1,253 0.12").
_COMBINED_ROW_6 = re.compile(
    _SN + _NAME + r"\s+([\d,]+)(?:\s+" + _T + r"){6}\s+([\d,]+(?:\.\d+)?)\s+([\d.]+%?)(?:\s|$)"
)
# 2012's variant of the combined layout puts "% of total" right after the
# share count instead of after the capital amounts: name, shares, "% of
# total", then five cells (total, callable, paid-in, overdue, not-yet-due),
# then votes and "% voting". (Its second annex table, "Part 2", repeats the
# capital amounts without votes -- no row pattern here matches that one,
# deliberately, since Part 1 already has everything.)
_COMBINED_ROW_2012 = re.compile(
    _SN + _NAME + r"\s+([\d,]+)\s+[\d.]+%(?:\s+" + _T + r"){5}\s+([\d,]+)\s+[\d.]+%" + _TAIL
)
# Split capital annex: name, shares, called-up, callable, total, "% of
# total" (a % sign in most years, none in 2017), then paid-up/overdue/
# not-yet-due -- one to three cells, since 2017's table drops an empty cell
# on some rows rather than printing a placeholder.
_CAPITAL_ROW = re.compile(
    _SN + _NAME + r"\s+([\d,]+)\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\d.]+%?(?:\s+" + _T + r"){1,3}" + _TAIL
)
# 2025's capital annex has no share-count column at all: name, called-up,
# callable, total (ID million), "% of total", then the three cells. The
# total capital amount is proportional to shares (every share has the same
# par value), so its ratio is the same capital share.
_CAPITAL_AMOUNT_ROW = re.compile(
    _SN + _NAME + r"\s+[\d,.]+\s+[\d,.]+\s+([\d,.]+)\s+[\d.]+%\s+" + _T + r"\s+" + _T + r"\s+" + _T + _TAIL
)
# Split voting annex: name, votes, "% voting" (no % sign in 2017; the
# Sub-Total row's votes carry decimals there and in 2015).
_VOTING_ROW = re.compile(_SN + _NAME + r"\s+([\d,]+(?:\.\d+)?)\s+[\d.]+%?" + _TAIL)

# 2019's capital and voting annexes share a page layout with the Board of
# Executive Directors' constituency list, so director names and titles get
# glued onto the *front* of some rows ("Hon. Dr. Hamad Suleiman Al Bazai Saudi
# Arabia 6 Qatar 363,236 ..."). These are the same row shapes searched for
# anywhere in the line, but only where a running S/N number marks the real
# start of the row -- confirmed present on every row of this layout.
_SN_MID = r"(?:^|\s)\d{1,2}\s+"
_CAPITAL_ROW_MID = re.compile(
    _SN_MID + _NAME + r"\s+([\d,]+)\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\d.]+%?(?:\s+" + _T + r"){1,3}" + _TAIL
)
_VOTING_ROW_MID = re.compile(_SN_MID + _NAME + r"\s+([\d,]+(?:\.\d+)?)\s+[\d.]+%?" + _TAIL)


def _to_number(text: str) -> float:
    return float(text.replace(",", ""))


def _clean_name(raw: str) -> str:
    name = raw.strip()
    return _NAME_FIXUPS.get(name, name)


def parse_lines(lines: list[str]) -> tuple[dict[str, dict], list[str], dict[str, float | None]]:
    """Members keyed by ISO3 ({"shares": ..., "votes": ...}, either may be
    missing -- resolving names *before* merging matters: the capital and
    voting annexes spell some names differently, e.g. "Cote D'Ivoire" vs
    "C\u00f4te D'Ivoire" within the same year's document), the names that
    didn't resolve, and the stated Sub-Total shares/votes where printed."""

    members: dict[str, dict] = {}
    unresolved: list[str] = []
    stated: dict[str, float | None] = {"shares": None, "votes": None}

    def record(name: str, key: str, value: float) -> None:
        lowered = name.lower()
        if lowered in _STATED_TOTAL_NAMES or (key == "votes" and lowered == "total"):
            stated[key] = value
        elif lowered in _NOT_A_MEMBER or "shortfall" in lowered:
            return
        else:
            iso3 = iso3_from_name(name)
            if iso3:
                members.setdefault(iso3, {})[key] = value
            elif name not in unresolved:
                unresolved.append(name)

    for line in lines:
        line = line.strip()
        combined = _COMBINED_ROW.match(line) or _COMBINED_ROW_2012.match(line) or _COMBINED_ROW_6.match(line)
        if combined:
            name = _clean_name(combined.group(1))
            record(name, "shares", _to_number(combined.group(2)))
            record(name, "votes", _to_number(combined.group(3)))
            continue
        capital = _CAPITAL_ROW.match(line) or _CAPITAL_AMOUNT_ROW.match(line)
        if capital:
            record(_clean_name(capital.group(1)), "shares", _to_number(capital.group(2)))
            continue
        voting = _VOTING_ROW.match(line)
        if voting:
            record(_clean_name(voting.group(1)), "votes", _to_number(voting.group(2)))
            continue
        capital_mid = _CAPITAL_ROW_MID.search(line)
        if capital_mid:
            record(_clean_name(capital_mid.group(1)), "shares", _to_number(capital_mid.group(2)))
            continue
        voting_mid = _VOTING_ROW_MID.search(line)
        if voting_mid:
            record(_clean_name(voting_mid.group(1)), "votes", _to_number(voting_mid.group(2)))
    return members, unresolved, stated


def _count_hits(lines: list[str]) -> int:
    return sum(
        1 for line in lines
        if any(pattern.match(line.strip()) for pattern in (_COMBINED_ROW, _COMBINED_ROW_2012, _COMBINED_ROW_6, _CAPITAL_ROW, _CAPITAL_AMOUNT_ROW, _VOTING_ROW))
        or _CAPITAL_ROW_MID.search(line) or _VOTING_ROW_MID.search(line)
    )


def _statement_lines(pdf) -> list[str]:
    """The annex sits in the last part of every report. Walk backward from
    the end to the last page that both names one of the statement headings
    and matches the row patterns (an unmistakable anchor -- confirmed
    necessary: later "approvals by country" tables in the same reports match
    the row patterns loosely, so row-shape alone picks the wrong page), keep
    extending backward through adjacent pages that still carry rows (the
    capital annex right before a voting annex), then forward through the
    pages after the anchor until both a shares total and a votes total have
    been seen (a two-page combined table, or a voting annex following a
    capital one). Avoids parsing every page of a 40 MB PDF."""

    after: list[list[str]] = []  # pages after the anchor, collected walking backward
    anchor = None
    for page in reversed(pdf.pages):
        text = page.extract_text() or ""
        lines = text.splitlines()
        if _HEADING.search(text) and _count_hits(lines) >= 5:
            anchor = lines
            break
        after.append(lines)
    if anchor is None:
        return []
    after.reverse()

    before: list[list[str]] = []
    for page in reversed(pdf.pages[: len(pdf.pages) - len(after) - 1]):
        lines = (page.extract_text() or "").splitlines()
        if _count_hits(lines) < 3:
            break
        before.append(lines)
    before.reverse()

    selected = [line for lines in before for line in lines] + anchor
    for lines in after:
        _, _, stated = parse_lines(selected)
        if stated["shares"] is not None and stated["votes"] is not None:
            break
        selected += lines
    return selected


def parse_pdf(path: Path, year: int, source_url: str) -> tuple[list[dict], list[dict]]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        lines = _statement_lines(pdf)
    if not lines:
        raise SystemExit(f"error: no share-capital / voting-power statement found in {path} for {year}")

    members, unresolved_names, stated = parse_lines(lines)
    total_shares = sum(m["shares"] for m in members.values() if "shares" in m)
    total_votes = sum(m["votes"] for m in members.values() if "votes" in m)
    for label, summed in (("shares", total_shares), ("votes", total_votes)):
        if stated[label] is None:
            raise SystemExit(f"error: {path} for {year}: no Sub-Total row found for {label}")
        if not 99.9 <= summed / stated[label] * 100 <= 100.1:
            raise SystemExit(
                f"error: {path} for {year}: parsed member {label} sum to {summed / stated[label] * 100:.3f}% "
                f"of the printed Sub-Total ({len(members)} members parsed)"
            )

    rows = [
        {
            "bank": "IsDB", "iso3": iso3, "year": year,
            "capital_share_pct": round(values["shares"] / total_shares * 100, 6) if "shares" in values else "",
            "voting_power_pct": round(values["votes"] / total_votes * 100, 6) if "votes" in values else "",
            "source_url": source_url,
            "note": "",
        }
        for iso3, values in members.items()
    ]
    return rows, [{"year": year, "name_raw": name} for name in unresolved_names]


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "IsDB" or row.get("document"):  # document set = read by annual_reports_isdb_early.py
            continue
        year = int(row["year"])
        url = row["url"]
        path = fetch(url, f"isdb_ar_{year}.pdf")
        rows, unresolved = parse_pdf(path, year, url)
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
