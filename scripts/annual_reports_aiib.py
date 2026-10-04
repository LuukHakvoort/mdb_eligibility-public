"""AIIB's capital shares (2016-2024) and published voting power (2022-2024),
from two different document types -- and a separate, clearly-labelled
*computed* voting-power series for the years AIIB doesn't publish one.

**Capital share** comes from the "Share capital" note of each year-end
financial statement (Note C14 in 2019, C16 in 2020-2022, C15 in 2024 -- the
note number shifts, so it's found by its table, not its number): one row per
member with total shares, subscribed capital, callable capital, paid-in
capital, and a printed Total row to reconcile against. 2019-2021 add two
paid-in-received columns; wrapped names ("Brunei / Darussalam", "Hong Kong, /
China") are rejoined. Capital share = a member's subscribed capital over the
sum of all members'.

**Voting power** is *not* the same as capital share (China 2024: 30.69% of
capital, 26.57% of votes -- the gap is real and systematic, from Article 28 of
the Articles of Agreement: 12% of all votes are "basic votes" split equally
across every member, and founding members get 600 flat). It is published, per
member, in the annual report's "Board of Governors Voting Power" appendix, but
only for 2022 (voting % only, no vote counts), 2023 and 2024 (full breakdown)
of the reports fetched: the 2016-2021 annual-report PDFs carry no such table
(scanned for it, including OCR of the image-only 2018 report).

**2016-2018 are scanned, image-only PDFs** (no text layer at all) and are read
by OCR -- `scripts/ocr.py`, the `tesseract` command, cached per page. OCR
misreads digits, so trusting it needs more than the printed-total check: see
`parse_capital_lines` for the per-row double check that makes it safe.

**Computed series, kept out of the shareholders panel on purpose.** For 2019-
2021 (capital known, voting not published) Article 28 gives the formula, and
the published 2022-2024 tables let the formula be *checked* against reality
rather than trusted: `aiib_voting_computed.csv` lists computed vs. published for
those years. It cannot be exact -- voting rights on shares with overdue payments
are suspended (Iran 2024: 9,485 share votes on 15,808 shares), a per-member,
per-year fact not recoverable for years with no published table -- so the
computed values are a separate file for the user to decide on, never silently
mixed into `voting_power_pct`.

**Also written, as evidence only:** the 2022 appendix prints every member's
real "Membership Date", so `aiib_membership_dates_2022_annex.csv` records them.
Not merged into `data/manual/accession_dates.csv` -- AIIB's date is when
membership took effect (founders: Dec 25, 2015, the Articles' entry into
force), which differs from some existing rows' dates (approval dates, or the
Jan 2016 opening) by up to several years (Brazil: signed 2015, effective Nov
2022) -- a semantic difference to decide, not a fact to overwrite silently.

Usage:  python3 scripts/annual_reports_aiib.py
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
TARGET = EXTRACTED_DIR / "shares_aiib.csv"
COMPUTED_TARGET = EXTRACTED_DIR / "aiib_voting_computed.csv"
MEMBERSHIP_DATES_TARGET = EXTRACTED_DIR / "aiib_membership_dates_2022_annex.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_aiib_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]
COMPUTED_FIELDS = [
    "iso3", "year", "computed_voting_pct", "published_voting_pct", "abs_error_pp",
    "share_votes_assumed", "founding_member", "note",
]

# Names as AIIB's own PDFs render them -> what _reference.iso3_from_name() needs.
_NAME_FIXUPS = {
    "EI Salvador": "El Salvador",  # 2025 statements: capital I for lower-case l
    # Bare "Korea" is AIIB's own spelling for the Republic of Korea (a member
    # since 2015; North Korea is not one) -- a page-specific fix, not a change
    # to the shared resolver (see the 2026-09-21 "two country names still don't
    # resolve" entry in docs/coding_decisions.md).
    "Korea": "Korea, Rep.",
    "Hong Kong, SAR": "Hong Kong, China",  # 2017's own spelling
    "UAE": "United Arab Emirates",
    "Kyrgyzstan": "Kyrgyz Republic",
    "Vietnam": "Viet Nam",
}

_NOT_A_MEMBER = {"total", "total regional", "total non-regional", "grand total"}

# --- capital: the "Share capital" note's member table ------------------------------

# name, total shares, subscribed, callable, paid-in (all comma-grouped whole
# numbers, thousands of USD), then in 2019-2021 up to two more columns
# (paid-in received / not yet received), each a number or "-".
_CAPITAL_ROW = re.compile(
    r"^([A-Za-zÀ-ÿ][^\d]*?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)(?:\s+(?:[\d,]+|-)){0,2}$"
)
def _clean_ocr_line(line: str) -> str:
    """Tesseract noise seen on AIIB's scanned 2016-2018 statements: table
    gridlines read as "|" or curly quotes at either end of a line, a lone "."
    or "-" between two numbers ("Qatar ... 48,360 . 72,540", "Nepal ... 16,200
    - 3,240 12,960"). None of it is data: the columns after "paid-in capital"
    are never used, and the dash-before-a-number case is a gridline, not a
    zero (a real zero dash comes last on the line, and is left alone)."""

    line = re.sub(r"^[|‘’“”'`\s]+|[|‘’“”'`\s]+$", "", line)
    line = re.sub(r"\s[.‘’“”|]\s", " ", line)
    return re.sub(r"\s-\s(?=[\d])", " ", line)


_HEADER_WORDS = {"shares", "share", "capital", "members", "member", "paid-in", "callable", "total", "subscribed", "received", "yet", "not"}


def _rejoin_wrapped_names(lines: list[str]) -> list[str]:
    """2019's note wraps long names over two lines ("Brunei" / "Darussalam
    524 52,400 ...", "Hong Kong," / "China 7,651 ..."). Join a short,
    digit-free, capitalised fragment onto the following line -- but never a
    column-header line, which is also digit-free."""

    joined: list[str] = []
    pending: str | None = None
    for line in lines:
        stripped = line.strip()
        words = stripped.split()
        is_fragment = (
            bool(words) and len(words) <= 3 and not any(c.isdigit() for c in stripped)
            and all(w[0].isupper() for w in words) and not any(w.lower() in _HEADER_WORDS for w in words)
        )
        if pending is not None:
            joined.append(f"{pending} {stripped}")
            pending = None
        elif is_fragment:
            pending = stripped
        else:
            joined.append(stripped)
    return joined


def parse_capital_lines(lines: list[str]) -> tuple[dict[str, float], list[str], float | None]:
    """{name: subscribed capital}, the names of any rows whose subscribed
    capital can't be verified, and the printed Total row's subscribed capital
    where present.

    Every row carries two independent ways to confirm the one number this
    parser uses (subscribed capital): shares x 100 (thousand USD, par 100,000)
    and callable + paid-in. A row is accepted if *either* agrees with it, and
    rejected only if both fail. That is what makes OCR safe here: on the
    scanned 2016-2018 statements a single misread digit turned up in a
    different column on each of four rows (Turkey's paid-in "622,000" for
    522,000; Cambodia's; Luxembourg's callable; Maldives' share count "2" for
    72) -- none touching subscribed capital, all caught by the other relation
    holding -- while a misread in the subscribed cell itself would break
    both. A misread in a tiny member moves the column total by far less than
    the reconciliation tolerance, so the total alone would never notice."""

    members: dict[str, float] = {}
    inconsistent: list[str] = []
    stated_total = None
    for line in _rejoin_wrapped_names(lines):
        match = _CAPITAL_ROW.match(line)
        if not match:
            continue
        name = match.group(1).strip()
        values = [float(match.group(i).replace(",", "")) for i in (2, 3, 4, 5)]
        shares, subscribed, callable_, paid_in = values
        if name.lower() == "total":
            stated_total = subscribed
        elif name.lower() not in _NOT_A_MEMBER:
            members[name] = subscribed
            if abs(shares * 100 - subscribed) > 1 and abs(callable_ + paid_in - subscribed) > 2:
                inconsistent.append(name)
    return members, inconsistent, stated_total


def page_lines(path: Path) -> list[list[str]]:
    """Every page's lines: the PDF's own text layer where it has one, else
    OCR (cached; see scripts/ocr.py) with line noise cleaned. AIIB's
    2016-2018 statements have no text layer at all."""

    import pdfplumber

    if ocr.has_text_layer(path):
        with pdfplumber.open(path) as pdf:
            return [(page.extract_text() or "").splitlines() for page in pdf.pages]
    return [[_clean_ocr_line(line) for line in text.splitlines()] for text in ocr.page_texts(path)]


def _capital_page_lines(pages: list[list[str]]) -> list[str]:
    """The note's member table, possibly over two pages. Anchored on a page
    that both says "Share capital" and carries at least 10 member rows, then
    extended forward until a printed Total row has been seen."""

    for index, lines in enumerate(pages):
        text = "\n".join(lines)
        rows = sum(1 for line in _rejoin_wrapped_names(lines) if _CAPITAL_ROW.match(line))
        # 2016's table page carries only the column headers, not the "Share
        # capital" note title (that's on the page before it).
        if rows >= 10 and (re.search(r"share capital", text, re.I) or (
                re.search(r"subscribed", text, re.I) and re.search(r"callable", text, re.I))):
            collected = list(lines)
            while index + 1 < len(pages):
                if any(re.match(r"^Total\s+[\d,]+\s+[\d,]+", line.strip()) for line in collected):
                    break
                index += 1
                collected += pages[index]
            return collected
    return []


# --- voting: the annual report's "Board of Governors Voting Power" appendix --------

# 2023 and 2024: serial, name, subscription amount (million USD, one
# decimal), % of total subscriptions, share votes, founding votes ("600" or
# "-"), basic votes, total votes, % of total votes. 2024 prints two members
# per line side by side, so this is searched for, not anchored.
_VOTING_ROW = re.compile(
    r"(\d{1,3})\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.,\- ]*?)\s+([\d,]+\.\d)\s+([\d.]+)%\s+"
    r"([\d,]+)\s+(600|-)\s+([\d,]+)\s+([\d,]+)\s+([\d.]+)%"
)
# 2022: serial, name, membership date, voting % only.
_VOTING_ROW_2022 = re.compile(
    r"^(\d{1,3})\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.,\- ]*?)\s+"
    r"((?:Jan|Feb|Mar|March|Apr|April|May|June|July|Aug|Sept|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+\d{4})\s+([\d.]+)%$"
)
_STATED_GRAND_TOTAL = re.compile(r"Grand Total\s+([\d,]+\.\d)\s+[\d.]+%\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+[\d.]+%")


def parse_voting_lines(lines: list[str]) -> dict[str, dict]:
    """Full-breakdown appendix (2023, 2024): {name: {...}}."""

    members: dict[str, dict] = {}
    for line in lines:
        for match in _VOTING_ROW.finditer(line):
            name = match.group(2).strip()
            if name.lower() in _NOT_A_MEMBER:
                continue
            members[name] = {
                "subscribed_musd": float(match.group(3).replace(",", "")),
                "share_votes": float(match.group(5).replace(",", "")),
                "founding": match.group(6) == "600",
                "basic_votes": float(match.group(7).replace(",", "")),
                "total_votes": float(match.group(8).replace(",", "")),
                "voting_pct": float(match.group(9)),
            }
    return members


def parse_voting_lines_2022(lines: list[str]) -> dict[str, dict]:
    members: dict[str, dict] = {}
    for line in lines:
        match = _VOTING_ROW_2022.match(line.strip())
        if match:
            members[match.group(2).strip()] = {"membership_date": match.group(3), "voting_pct": float(match.group(4))}
    return members


def _voting_page_lines(pages: list[list[str]]) -> list[str]:
    """Walk backward from the end for the appendix's pages: any page whose
    text names the voting-power appendix and carries member rows, plus the
    directly preceding/following pages while they still do."""

    def rows(lines: list[str]) -> int:
        return sum(len(_VOTING_ROW.findall(line)) + bool(_VOTING_ROW_2022.match(line.strip())) for line in lines)

    for index in range(len(pages) - 1, -1, -1):
        text = "\n".join(pages[index])
        if re.search(r"voting power", text, re.I) and rows(pages[index]) >= 10:
            start = index
            while start > 0 and rows(pages[start - 1]) >= 3:
                start -= 1
            end = index
            while end + 1 < len(pages) and rows(pages[end + 1]) >= 3:
                end += 1
            return [line for lines in pages[start:end + 1] for line in lines]
    return []


# --- per-year assembly --------------------------------------------------------------


def _iso3(name: str) -> str:
    return iso3_from_name(_NAME_FIXUPS.get(name, name))


def _capital_for_year(path: Path, year: int) -> dict[str, float]:
    lines = _capital_page_lines(page_lines(path))
    if not lines:
        raise SystemExit(f"error: no share-capital member table found in {path} for {year}")
    members, inconsistent, stated_total = parse_capital_lines(lines)
    if inconsistent:
        raise SystemExit(
            f"error: {path} for {year}: subscribed capital couldn't be verified for {inconsistent} (neither "
            f"shares x 100 nor callable + paid-in agrees with it) -- misread digits or a real anomaly, check the page"
        )
    total = sum(members.values())
    if stated_total is None:
        raise SystemExit(f"error: {path} for {year}: no printed Total row found to reconcile against")
    if not 99.95 <= total / stated_total * 100 <= 100.05:
        raise SystemExit(
            f"error: {path} for {year}: member subscriptions sum to {total / stated_total * 100:.3f}% "
            f"of the printed Total ({len(members)} members parsed)"
        )
    return members


def _voting_for_year(path: Path, year: int) -> dict[str, dict]:
    lines = _voting_page_lines(page_lines(path))
    if not lines:
        raise SystemExit(f"error: no voting-power appendix found in {path} for {year}")
    members = parse_voting_lines(lines) or parse_voting_lines_2022(lines)
    if not members:
        raise SystemExit(f"error: {path} for {year}: voting-power page found but no rows parsed")
    total = sum(m["voting_pct"] for m in members.values())
    if not 99.9 <= total <= 100.1:
        raise SystemExit(f"error: {path} for {year}: published voting % sum to {total:.3f}%, not ~100%")
    return members


def compute_voting(shares: dict[str, float], founders: set[str]) -> dict[str, float]:
    """Article 28 of the Articles of Agreement: total votes = share votes +
    founding votes (600 each) + basic votes, where basic votes are 12% of the
    aggregate, split equally among every member. Share votes are assumed
    equal to shares held (100,000 USD par each) -- i.e. *no* votes suspended
    for overdue payment, which is what makes this an approximation."""

    share_votes = {name: subscribed / 100.0 for name, subscribed in shares.items()}  # thousands of USD -> shares
    founding = {name: (600.0 if name in founders else 0.0) for name in shares}
    basic_total = 0.12 / 0.88 * (sum(share_votes.values()) + sum(founding.values()))
    basic_each = basic_total / len(shares)
    totals = {name: share_votes[name] + founding[name] + basic_each for name in shares}
    grand = sum(totals.values())
    return {name: total / grand * 100 for name, total in totals.items()}


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    capital: dict[int, tuple[dict[str, float], str]] = {}
    voting: dict[int, tuple[dict[str, dict], str]] = {}
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "AIIB":
            continue
        year, url, document = int(row["year"]), row["url"], row.get("document", "")
        path = fetch(url, f"aiib_{document}_{year}.pdf")
        if document == "financial_statements":
            capital[year] = (_capital_for_year(path, year), url)
            print(f"{year} capital: {len(capital[year][0])} members, reconciles to the printed Total")
        elif document == "annual_report":
            voting[year] = (_voting_for_year(path, year), url)
            print(f"{year} voting:  {len(voting[year][0])} members, published % sum to ~100")

    # Founding members = those carrying 600 founding votes in any published
    # full-breakdown table (2023, 2024).
    founders: set[str] = set()
    for members, _ in voting.values():
        founders |= {name for name, m in members.items() if m.get("founding")}

    rows: list[dict] = []
    unresolved: list[dict] = []
    computed_rows: list[dict] = []
    for year in sorted(capital):
        shares, capital_url = capital[year]
        total = sum(shares.values())
        published = voting.get(year, ({}, ""))[0]
        published_by_iso3 = {_iso3(name): m for name, m in published.items() if _iso3(name)}
        computed = compute_voting(shares, founders)
        for name, subscribed in shares.items():
            iso3 = _iso3(name)
            if not iso3:
                unresolved.append({"year": year, "name_raw": name})
                continue
            published_member = published_by_iso3.get(iso3)
            if published_member is not None:
                voting_value = published_member["voting_pct"]
                note = ""
                source = voting[year][1]
            else:
                voting_value, note, source = "", (
                    "voting_power_pct not published for this year in any fetched document; see "
                    "aiib_voting_computed.csv for an Article 28 approximation, deliberately not merged in."
                ), capital_url
            rows.append({
                "bank": "AIIB", "iso3": iso3, "year": year,
                "capital_share_pct": round(subscribed / total * 100, 6),
                "voting_power_pct": voting_value,
                "source_url": capital_url if published_member is None else f"{capital_url} ; {source}",
                "note": note,
            })
            computed_rows.append({
                "iso3": iso3, "year": year,
                "computed_voting_pct": round(computed[name], 6),
                "published_voting_pct": published_member["voting_pct"] if published_member else "",
                "abs_error_pp": round(abs(computed[name] - published_member["voting_pct"]), 4) if published_member else "",
                "share_votes_assumed": round(subscribed / 100.0),
                "founding_member": int(name in founders),
                "note": "" if published_member else "computed only; no published table this year to check against",
            })

    date_rows = []
    for year, (members, url) in voting.items():
        for name, member in members.items():
            if "membership_date" in member and _iso3(name):
                date_rows.append({
                    "iso3": _iso3(name), "name_raw": name, "as_of_year": year,
                    "membership_date": member["membership_date"], "source_url": url,
                })
    date_rows.sort(key=lambda r: r["iso3"])
    write_csv(MEMBERSHIP_DATES_TARGET, ["iso3", "name_raw", "as_of_year", "membership_date", "source_url"], date_rows)

    rows.sort(key=lambda r: (r["iso3"], r["year"]))
    computed_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, rows)
    write_csv(COMPUTED_TARGET, COMPUTED_FIELDS, computed_rows)
    write_csv(UNRESOLVED_REPORT, ["year", "name_raw"], unresolved)
    print(f"\n{len(rows)} rows -> {TARGET.relative_to(REPO)}")
    print(f"{len(computed_rows)} computed-vs-published rows -> {COMPUTED_TARGET.relative_to(REPO)}")
    print(f"{len(date_rows)} membership dates -> {MEMBERSHIP_DATES_TARGET.relative_to(REPO)}")
    print(f"{len(unresolved)} unresolved names -> {UNRESOLVED_REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
