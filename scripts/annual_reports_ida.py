"""IDA's voting power and subscriptions-and-contributions per member, FY2005-
FY2026, from the "Statement of Voting Power and Subscriptions and Contributions"
in IDA's own June-30 financial statements (thedocs.worldbank.org and
documents.worldbank.org PDFs).

What IDA publishes is not IBRD's share-capital table: per member it gives the
**number of votes**, the **percentage of total votes**, and the **subscriptions
and contributions committed** (USD million, summed over every replenishment,
at the exchange rates of each pledge). IDA has no share capital in IBRD's sense,
so "capital share" here means a member's share of total subscriptions and
contributions committed -- the closest thing IDA publishes -- and the note on
every row says so. Voting power = votes over all votes, recomputed from the raw
counts and reconciled to the statement's own Total row.

Members are listed in groups whose names have changed over the years (Part I /
Part II; later Non-Recipients / Recipients), each with a subtotal; subtotals and
the Total row are excluded from members and used to reconcile.

Panel year = calendar year of the June 30 statement date (the user's decision
for all June-30 positions; see annual_reports_ibrd.py).

Usage:  python3 scripts/annual_reports_ida.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, MANUAL_DIR, REPO, REPORTS_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402
import ocr  # noqa: E402
from annual_reports import fetch  # noqa: E402

ANNUAL_REPORTS_CSV = MANUAL_DIR / "annual_reports.csv"
TARGET = EXTRACTED_DIR / "shares_ida.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_ida_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_NOTE = (
    "capital_share_pct is this member's share of total subscriptions and contributions committed "
    "(IDA has no share capital); voting_power_pct is votes over all votes."
)

_HEADING = re.compile(r"STATEMENT OF VOTING POWER,?\s+AND SUBSCRIPTIONS\s+AND\s+CONTRIBUTIONS\s+June 30,\s+(\d{4})", re.I)
# name, votes, % of total votes (a "%" sign on the first row of a group only,
# sometimes after a space), then the amount committed with an optional "$".
_ROW = re.compile(
    r"^([A-Za-z\u00c0-\u00ff][^\d$]*?)\s+\$?\s*([\d,]+)\s+([\d.]+)\s*%?\s+\$?\s*([\d,]+\.\d+)\s*$"
)
# FY2004 and earlier print "*" for an amount or share below the rounding (e.g. "Palau 504 * *",
# "Panama 10,185 0.07 *"): the votes still count, the amount is under USD 0.05 million.
_ROW_STAR = re.compile(r"^([A-Za-z\u00c0-\u00ff][^\d$*]*?)\s+([\d,]+)\s+(?:\*|[\d.]+)\s*%?\s+\*\s*$")
# FY2002's OCR loses the decimal point of the one-decimal amounts of Part II members
# ("Afghanistan 13,557 0,10 13" for 1.3): read as tenths, and only for FY2002 -- the sum of the
# committed column must still reconcile to the printed Total.
_ROW_NODOT = re.compile(r"^\.?\s*([A-Za-z][^\d$*:]*?)\s*:?\s+([\d,]+)\s+(?:\*\s*%?|[\d.,]+\s*%?)[\s:]+\$?\s*([\dOo.]{1,4})\s*$")
# (The "$" tolerated before the votes and the loose percentage pattern are for
# OCR'd years: FY2006's Korea row reads "$ 94,639 060% $ 690.80" for 94,639 /
# 0.60%. The percentage is never used -- votes are recomputed -- and the
# amount must still carry decimals, which keeps the debt tables' rows out.)

# "Total--June 30, 2015 b   25,120,295   100.00 %   $ 244,694" -- the year sits in
# the label (so the name pattern above can't read it), the amount can drop its
# decimals, and a comparative "Total--June 30, 2014" row (no percentage) follows.
_TOTAL_ROW = re.compile(
    r"^Total\s*[\u2014\u2013-]+\s*June 30,\s*(\d{4})(?!\d)\D*?\s+([\d,]+)\s+(\d+(?:\.\d+)?)\s*%?\s+\$?\s*([\d,]+(?:\.\d+)?)\s*$"
)
# FY2002 (OCR): a footnote digit sits between the date and the votes ("Total--June 30, 2002 77
# $13,248,130 100.00% $109,387.7"), and the votes carry a "$".
_TOTAL_ROW_FN = re.compile(
    r"^Total\s*[\u2014\u2013-]+\s*June 30,\s*(\d{4})(?!\d)\s+(?:\d{1,2}\s+)?\$?([\d,]+)\s+100(?:\.0+)?\s*%\s+\$?\s*([\d,]+(?:\.\d+)?)\s*$"
)
# FY2023's statement labels the current year's total "Total All Members" (with a
# bare "100 %") and dates only the prior-year comparative under it.
_TOTAL_ALL = re.compile(
    r"^Total All Members\b\D*?\s+([\d,]+)\s+(\d+(?:\.\d+)?)\s*%?\s+\$?\s*([\d,]+(?:\.\d+)?)\s*$"
)

# Names as IDA's own statements render them -> what _reference.iso3_from_name()
# needs (filled in from what the runs report as unresolved).
_NAME_FIXUPS = {
    "Macedonia, former Yugoslav Republic of": "North Macedonia",
    "Macedonia, Former Yugoslav Republic of": "North Macedonia",
    "Kosovo, Republic of": "Kosovo",
    "Cabo Verde, Republic of": "Cabo Verde",
    "Cate d'Ivoire": "Cote d'Ivoire",  # FY2002 (OCR)
    "Traq": "Iraq",  # FY2002 (OCR)
    "C\u00e9te d'Ivoire": "Cote d'Ivoire",  # FY2005's text layer mis-encodes the o-circumflex
}

_STATEMENT_WORDS = ("subtotal", "total")


def _resolve(name: str) -> str:
    """ISO3 for a member name as printed. A footnote letter is sometimes glued
    straight onto the name with no space ("Estoniac", "Tuvaluc", "Kosovo,
    Republic ofd", "Bahamas, Thec"), so a name that doesn't resolve is retried
    without a trailing footnote letter -- only ever a-e, and only if the
    shortened name resolves, so a real name is never truncated."""

    for candidate in (name, name[:-1] if name and name[-1] in "abcde" else None):
        if candidate:
            iso3 = iso3_from_name(_NAME_FIXUPS.get(candidate, candidate))
            if iso3:
                return iso3
    return ""


def parse_rows(lines: list[str], year: int) -> tuple[dict[str, tuple[float, float]], tuple[float, float] | None]:
    """({member: (votes, committed)}, the Total row's (votes, committed) for
    `year`'s own June 30 -- not the prior-year comparative row under it)."""

    members: dict[str, tuple[float, float]] = {}
    total = None
    for line in lines:
        total_match = _TOTAL_ROW.match(line.strip())
        if total_match:
            if int(total_match.group(1)) == year:
                total = (float(total_match.group(2).replace(",", "")), float(total_match.group(4).replace(",", "")))
            continue
        total_fn = _TOTAL_ROW_FN.match(line.strip())
        if total_fn:
            if int(total_fn.group(1)) == year:
                total = (float(total_fn.group(2).replace(",", "")), float(total_fn.group(3).replace(",", "")))
            continue
        total_all = _TOTAL_ALL.match(line.strip())
        if total_all:
            total = total or (float(total_all.group(1).replace(",", "")), float(total_all.group(3).replace(",", "")))
            continue
        match = _ROW.match(line.strip())
        star = None if match else _ROW_STAR.match(line.strip())
        if star:
            star_name = re.sub(r"\s+[a-z](?:,\s*[a-z])*$", "", star.group(1).strip())
            if not star_name.lower().startswith(_STATEMENT_WORDS):
                members[star_name] = (float(star.group(2).replace(",", "")), 0.0)
            continue
        if not match and year == 2002:
            nodot = _ROW_NODOT.match(line.strip())
            if nodot and not nodot.group(1).strip().lower().startswith(_STATEMENT_WORDS):
                digits = nodot.group(3).replace("O", "0").replace("o", "0")
                amount = float(digits) if "." in digits else int(digits) / 10 if digits.isdigit() else None
                if amount is not None:
                    members[re.sub(r"\s+[a-z](?:,\s*[a-z])*$", "", nodot.group(1).strip())] = (float(nodot.group(2).replace(",", "")), amount)
            continue
        if not match:
            continue
        name = re.sub(r"\s+[a-z](?:,\s*[a-z])*$", "", match.group(1).strip())  # trailing footnote letters
        try:
            votes = float(match.group(2).replace(",", ""))
            committed = float(match.group(4).replace(",", ""))
        except ValueError:
            continue  # OCR debris ("," or "." read as a number)
        if name.lower().startswith(_STATEMENT_WORDS):
            continue
        members[name] = (votes, committed)
    return members, total


def page_lines(path: Path) -> list[list[str]]:
    """Every page's lines -- from the PDF's text layer where it has a usable
    one, else OCR (scripts/ocr.py). FY2006 and FY2007's statements use fonts
    whose text layer is "(cid:N)" garbage, so they are read by OCR."""

    import pdfplumber

    if ocr.has_text_layer(path):
        with pdfplumber.open(path) as pdf:
            return [(page.extract_text() or "").splitlines() for page in pdf.pages]
    return [[_clean_ocr_line(line) for line in text.splitlines()] for text in ocr.page_texts(path)]


def _clean_ocr_line(line: str) -> str:
    """Tesseract at 200 dpi reads the decimal point of a small amount as a
    comma ("Pakistan 144,828 0.92 13,99" for $13.99 million). A comma followed
    by exactly two digits can never be a thousands separator (those always have
    three), so a trailing amount of that shape is a decimal -- the sums still
    have to reconcile to the printed Total."""

    line = re.sub(r"^[|\s]+|[|\s]+$", "", line)
    return re.sub(r"(\s\$?\s*\d{1,3}),(\d{2})$", r"\1.\2", line)


def _statement_lines(pages: list[list[str]], year: int) -> list[str]:
    """From the first page that carries the statement -- its heading dated
    June 30 of `year`, or (FY2005's small-caps heading extracts as "S V P S /
    TAT EME NT OF OT ING...") the words "Part I Members" with that date -- and
    has member rows (the table of contents carries the heading too, but no
    rows), through following pages until the year's Total row."""

    for index, lines in enumerate(pages):
        text = "\n".join(lines)
        heading = _HEADING.search(text)
        dated = (heading and int(heading.group(1)) == year) or (
            re.search(rf"June 30,\s*{year}", text) and re.search(r"Part I Members", text)
        )
        if dated and sum(1 for line in lines if _ROW.match(line.strip())) >= 5:
            collected = list(lines)
            while index + 1 < len(pages) and parse_rows(collected, year)[1] is None:
                index += 1
                collected += pages[index]
            return collected
    return []


def parse_pdf(path: Path, year: int, source_url: str) -> tuple[list[dict], list[dict]]:
    lines = _statement_lines(page_lines(path), year)
    if not lines:
        raise SystemExit(f"error: no voting-power statement dated June 30, {year} found in {path}")
    members, total = parse_rows(lines, year)
    if total is None:
        raise SystemExit(f"error: {path} for {year}: no Total row found to reconcile against")

    total_votes = sum(v for v, _ in members.values())
    total_committed = sum(c for _, c in members.values())
    for label, summed, printed in (("votes", total_votes, total[0]), ("committed", total_committed, total[1])):
        if not 99.95 <= summed / printed * 100 <= 100.05:
            raise SystemExit(
                f"error: {path} for {year}: member {label} sum to {summed / printed * 100:.3f}% of the printed "
                f"Total ({len(members)} members parsed)"
            )

    rows: list[dict] = []
    unresolved: list[dict] = []
    for name, (votes, committed) in members.items():
        iso3 = _resolve(name)
        if not iso3:
            unresolved.append({"year": year, "name_raw": name})
            continue
        rows.append({
            "bank": "IDA", "iso3": iso3, "year": year,
            "capital_share_pct": round(committed / total_committed * 100, 6),
            "voting_power_pct": round(votes / total_votes * 100, 6),
            "source_url": source_url,
            "note": _NOTE,
        })
    return rows, unresolved


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "IDA":
            continue
        year, url = int(row["year"]), row["url"]
        path = fetch(url, f"ida_fs_{year}.pdf", delay=0.3, timeout=120)
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
