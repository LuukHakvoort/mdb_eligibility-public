"""ADB's capital share and voting power per member, from the "Statement of
Subscriptions to Capital Stock and Voting Power" (OCR-8) in ADB's annual
Financial Report PDFs (adb.org), as at 31 December of each year.

Per member: number of shares, % of total, par value (total / callable / paid-in),
number of votes, % of total votes. Capital share = shares over all members'
shares; voting power = votes over all votes, recomputed from the raw counts and
reconciled to the statement's own TOTAL row.

**A kerning artifact in this PDF's text layer**: the first digit of a
multi-digit number is separated from the rest by a space ("Afghanistan 3 ,585"
for 3,585; "Australia 6 14,220" for 614,220; "Japan 1 ,656,630"), inconsistently
(small numbers like 426 come through whole). Handled by structure, not by
guessing where spaces belong: a member row is name, shares, then the *first
decimal number* (the percentage of shares), so the tokens between name and that
percentage are shares fragments and are concatenated; votes are the integer
tokens between the last amount (a decimal number) and the final percentage.

Panel year = the statement's own "31 December <year>". Reports through 2012
print amounts in whole thousands (no decimal point), so where the paid-in amount
ends and the vote count begins isn't visible from the tokens alone; it is
recovered from the identity total = callable + paid-in (see `_partition`).

Usage:  python3 scripts/annual_reports_adb.py
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
TARGET = EXTRACTED_DIR / "shares_adb.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_adb_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

# (OCR'd pages -- ADB 2009 -- can put a stray mark or two before "31 December".)
_HEADING = re.compile(r"STATEMENT OF SUBSCRIPTIONS TO CAPITAL STOCK AND VOTING POWER\s+(?:\S{1,3}\s+)?31 December (\d{4})", re.I)
_DECIMAL = re.compile(r"^\d[\d,]*\.\d+$")
_INTEGERISH = re.compile(r"^[\d,]+$")

# Names as ADB's own statements render them -> what _reference.iso3_from_name()
# needs (filled in from what the runs report as unresolved).
_NAME_FIXUPS = {
    "People’s Republic of China": "China",
    "China, People’s Republic of": "China",
    "China, People's Republic of": "China",
    "Taipei,China": "Taiwan, China",
    "The Netherlands": "Netherlands",
    "Micronesia, Federated States of": "Micronesia (Federated States of)",
    "Federated States of Micronesia": "Micronesia (Federated States of)",
    "Republic of Korea": "Korea, Rep.",
    "Republic of the Maldives": "Maldives",
    # 2002-2006's abbreviations
    "China, People\u2019s Rep. of": "China",
    "Fiji Islands": "Fiji",
    "Korea, Rep. of": "Korea, Rep.",
    "Micronesia, Fed. States of": "Micronesia (Federated States of)",
}

_NOT_A_MEMBER = ("total", "regional", "nonregional", "non-regional")


def _partition(tokens: list[str]) -> list[int] | None:
    """Split integer tokens into exactly four numbers -- total, callable,
    paid-in, votes -- where each number is one token or a single leading digit
    plus the next token (the kerning artifact), choosing the split where total
    = callable + paid-in (to within rounding). Only the 2012 report needs the
    joins; the 2002-2011 ones come through whole, and the check is what makes
    joining safe rather than a guess."""

    def numbers(index: int, count: int) -> list[list[int]]:
        if count == 0:
            return [[]] if index == len(tokens) else []
        options: list[list[int]] = []
        if index < len(tokens):
            for width in (1, 2):
                if index + width > len(tokens):
                    continue
                pieces = tokens[index:index + width]
                if width == 2 and not (len(pieces[0]) == 1 and pieces[0].isdigit()):
                    continue
                text = "".join(pieces).replace(",", "")
                if not text.isdigit():
                    continue
                for tail in numbers(index + width, count - 1):
                    options.append([int(text)] + tail)
        return options

    valid = [n for n in numbers(0, 4) if abs(n[0] - n[1] - n[2]) <= 3]
    return valid[0] if len(valid) == 1 else None


def parse_row(line: str) -> tuple[str, int, int, float] | None:
    """(name, shares, votes, % of votes) from one statement line, or None."""

    # "$" is its own token in some years ("$ 49.7") and glued to the number in
    # others ("$47,234,435"); either way it isn't part of the number.
    tokens = [t.lstrip("$") for t in line.replace("\u00ad", "").split()]
    tokens = [t for t in tokens if t]
    # OCR'd pages (ADB 2009) carry margin noise: stray marks trailing the last
    # percentage ("... 67.623 Baa") and one- or two-character marks in front of a
    # name ("oa Bangladesh", "E Afghanistan"). No real row ends in a non-number or
    # begins with a one/two-character token followed by more name.
    # ("... 0.546 2": a stray digit) -- so everything after the last 2-3-decimal
    # token, which is always the final percentage, is dropped.
    last_pct = max((i for i, t in enumerate(tokens) if re.match(r"^\d+\.\d{2,3}$", t)), default=None)
    if last_pct is not None:
        tokens = tokens[:last_pct + 1]
    while len(tokens) > 2 and (len(tokens[0]) <= 2 or not tokens[0][0].isalpha()) and not tokens[1][:1].isdigit():
        tokens.pop(0)
    start = next((i for i, t in enumerate(tokens) if _INTEGERISH.match(t) and any(c.isdigit() for c in t)), None)
    if not start:
        return None
    name = " ".join(tokens[:start])
    rest = tokens[start:]
    pct_index = next((i for i, t in enumerate(rest) if re.match(r"^\d+\.\d{2,3}$", t)), None)
    if pct_index is None or pct_index == 0 or not _DECIMAL.match(rest[-1]):
        return None
    shares_text = "".join(rest[:pct_index]).replace(",", "")
    if not shares_text.isdigit():
        return None
    body = rest[pct_index + 1:-1]
    if any("." in t for t in body):
        # Millions-of-dollars era (2013 on): amounts carry a decimal point, so
        # votes are the integer tokens after the last amount.
        votes_tokens: list[str] = []
        for token in reversed(body):
            if "." in token:
                break
            votes_tokens.append(token)
        votes_text = "".join(reversed(votes_tokens)).replace(",", "")
        if not votes_text.isdigit():
            return None
        votes = int(votes_text)
    else:
        parts = _partition(body)
        if parts is None:
            return None
        votes = parts[3]
    return name, int(shares_text), votes, float(rest[-1].replace(",", ""))


def _is_total_line(line: str) -> bool:
    """The grand TOTAL row -- not "Total Regional (Forward)" or "Total
    Nonregional", whose second word isn't a number."""

    tokens = line.split()
    return len(tokens) > 2 and tokens[0].upper() in ("TOTAL", "TOTALS") and tokens[1].lstrip("$")[:1].isdigit()


def _page_lines(pdf, path: Path, index: int, in_statement: bool) -> list[str]:
    """A page's lines from its text layer -- or, when that layer is font-
    encoding garbage ("(cid:N)" runs, as on ADB's 2009 subscriptions statement)
    on a page that mentions the capital stock or continues the statement, by OCR
    of that one page."""

    text = pdf.pages[index].extract_text() or ""
    if text.count("(cid:") > 30 and (in_statement or "OCR-8" in text or "capital stock" in text.lower()):
        return [re.sub(r"^[|\s]+|[|\s]+$", "", line) for line in ocr.page_text(path, index).splitlines()]
    return text.splitlines()


def _statement_lines(pdf, path: Path, year: int) -> list[str]:
    """Scan pages lazily (these reports run 200-300 pages, and parsing every
    page's text is what makes a full run slow) for the heading dated 31
    December `year`, then take following pages until the TOTAL row."""

    collected: list[str] = []
    found = False
    for index in range(len(pdf.pages)):
        lines = _page_lines(pdf, path, index, found)
        if not found:
            text = "\n".join(lines).replace("\u00ad", "")  # soft hyphens in 2006 and 2009's heading
            heading = _HEADING.search(text)
            if not (heading and int(heading.group(1)) == year and "Afghanistan" in text):
                continue
            found = True
        collected += lines
        if any(_is_total_line(line) for line in lines):
            break
    return collected if found else []


def parse_pdf(path: Path, year: int, source_url: str) -> tuple[list[dict], list[dict]]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        lines = _statement_lines(pdf, path, year)
    if not lines:
        raise SystemExit(f"error: no OCR-8 statement dated 31 December {year} found in {path}")

    members: dict[str, tuple[int, int]] = {}
    stated = None
    for line in lines:
        parsed = parse_row(line)
        if parsed is None:
            continue
        name, shares, votes, _ = parsed
        lowered = name.lower()
        if name.upper() in ("TOTAL", "TOTALS"):  # 2011's font renders it in odd case
            stated = (shares, votes)
        elif lowered.startswith(_NOT_A_MEMBER):
            continue
        else:
            members[name] = (shares, votes)
    if stated is None:
        raise SystemExit(f"error: {path} for {year}: no TOTAL row found to reconcile against")

    total_shares = sum(s for s, _ in members.values())
    total_votes = sum(v for _, v in members.values())
    for label, summed, printed in (("shares", total_shares, stated[0]), ("votes", total_votes, stated[1])):
        if summed != printed:
            raise SystemExit(
                f"error: {path} for {year}: member {label} sum to {summed:,} but the printed TOTAL is {printed:,} "
                f"({len(members)} members parsed)"
            )

    rows: list[dict] = []
    unresolved: list[dict] = []
    for name, (shares, votes) in members.items():
        iso3 = iso3_from_name(_NAME_FIXUPS.get(name, name))
        if not iso3:
            unresolved.append({"year": year, "name_raw": name})
            continue
        rows.append({
            "bank": "AsDB", "iso3": iso3, "year": year,
            "capital_share_pct": round(shares / total_shares * 100, 6),
            "voting_power_pct": round(votes / total_votes * 100, 6),
            "source_url": source_url,
            "note": "",
        })
    return rows, unresolved


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "AsDB":
            continue
        year, url = int(row["year"]), row["url"]
        path = fetch(url, f"adb_fr_{year}.pdf", delay=3.0, timeout=180)
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
