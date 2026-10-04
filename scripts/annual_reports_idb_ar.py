"""IDB's capital share and voting power per member, FY2002-FY2021 (except 2017, whose
file is corrupt), from the subscriptions table in IDB's own annual reports
(data/raw/annual_reports/Inter-American-...-Annual-Report-<year>*.pdf, hand-downloaded:
iadb.org sits behind a Cloudflare challenge). The 2022-2025 years come from IDB's SEC
filings (annual_reports_idb.py).

Two layouts:
  2002-2007  Ordinary Capital "Appendix I-7, Statement of subscriptions to capital stock
             and voting power": subscribed shares, number of votes, % of votes (dot leaders).
  2008-2021  "Table ... Subscriptions to capital stock, contribution quotas and voting
             power" in USD millions: paid-in, callable, [additional paid-in capital],
             total subscribed, % of total votes, FSO contribution quota.

Capital share = a member's subscribed capital (shares in 2002-2007, USD total after) over
the members' total; voting power = the printed "% of total number of votes" (three
decimals, checked to sum to 100). Panel year = the table's own "as of December 31".

Usage:  python3 scripts/annual_reports_idb_ar.py [year ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, REPO, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

TEXT_DIR = REPO / "data" / "raw" / "text"
TARGET = EXTRACTED_DIR / "shares_idb_ar.csv"
FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_NAME_FIXUPS = {"Korea, Republic of": "Korea, Rep.", "Republic of Korea": "Korea, Rep.", "United States of America": "United States"}
_HEADING_SHARES = re.compile(r"STATEMENT\s+OF\s+SUBSCRIPTIONS\s+TO\s+CAPITAL\s+STOCK\s+AND\s+VOTING\s+POWER", re.I)
_HEADING_TABLE = re.compile(r"subscriptions\s+to\s+capital\s+stock,?\s+(?:contribution\s+quotas,?\s+)?and\s+voting\s+power", re.I)
_AS_OF = re.compile(r"december 31,? ?(\d{4})", re.I)
# Par value implied by the tables: Argentina's 900,154 shares carry USD 10,858.9 million of
# paid-in + callable capital (unchanged through 2021: ARG's 1,609,442 shares = 19,415.4).
USD_MILLION_PER_SHARE = 10858.947 / 900154
BASIC_VOTES = 135  # every member holds 135 votes on top of one per share
_TOTAL_WORDS = ("total", "subtotal", "unallocated", "grand")


def doc_dir(year: int) -> Path | None:
    for candidate in sorted(TEXT_DIR.iterdir()):
        name = candidate.name
        if re.search(rf"Annual[-_]Report[-_]{year}(?![0-9])", name) or (year == 2025 and name.startswith("idb_annual_report_2025")):
            return candidate
    return None


def _numbers(text: str) -> list[str]:
    return re.findall(r"\d[\d,]*\.?\d*", text.replace("$", " "))


def _known(name: str) -> str | None:
    """The member name with a glued footnote letter ("Canadac") removed, if that is what
    it takes to resolve it."""

    if iso3_from_name(name):
        return name
    if len(name) > 3 and name[-1].islower() and iso3_from_name(name[:-1]):
        return name[:-1]
    return None


def _member_line(line: str):
    """(name, numeric tokens) for a table line; dot leaders and footnote digits stripped."""

    cleaned = re.sub(r"(?:\s*\.){2,}", " ", line).replace("$", " ").replace("—", " - ").strip()
    match = re.match(r"^([A-Za-z][A-Za-z ,'()\-]*?)\s*(\d?)\s+((?:[\d,]+\.?\d*|-)(?:\s+(?:[\d,]+\.?\d*|-))*)\s*$", cleaned)
    if not match:
        return None
    name = match.group(1).strip(" ,")
    return _NAME_FIXUPS.get(name, name), match.group(3).split()


def parse_shares_layout(lines: list[str]):
    """2002-2007: name, shares, votes, % votes."""

    members = {}
    for line in lines:
        parsed = _member_line(line)
        if not parsed:
            continue
        name, tokens = parsed
        name = _known(name) or name
        if name.lower().startswith(_TOTAL_WORDS) or not iso3_from_name(name):
            continue
        if len(tokens) == 3 and re.fullmatch(r"\d+\.\d{3}", tokens[2]):
            members[name] = (float(tokens[0].replace(",", "")), float(tokens[2]))
    return members


def parse_table_layout(lines: list[str]):
    """2008-2021: amounts (1 decimal) then the three-decimal % of votes, then optional FSO quota."""

    members = {}
    for line in lines:
        parsed = _member_line(line)
        if not parsed:
            continue
        name, tokens = parsed
        name = _known(name) or name
        if name.lower().startswith(_TOTAL_WORDS) or not iso3_from_name(name):
            continue
        pct_index = next((i for i, t in enumerate(tokens) if re.fullmatch(r"\d+\.\d{3}", t)), None)
        if pct_index is None or pct_index < 2:
            continue
        amounts = tokens[:pct_index]
        if "-" in amounts[:2]:
            paid, callable_ = (0.0 if amounts[0] == "-" else float(amounts[0].replace(",", ""))), (0.0 if amounts[1] == "-" else float(amounts[1].replace(",", "")))
        else:
            paid, callable_ = float(amounts[0].replace(",", "")), float(amounts[1].replace(",", ""))
        members[name] = (paid + callable_, float(tokens[pct_index]))
    return members


def find_tables(directory: Path):
    """[(table year, layout, member dict)] from the pages carrying a subscriptions heading."""

    pages = [p.read_text(encoding="utf-8").splitlines() for p in sorted(directory.glob("p*.txt"))]
    tables = []
    for index, lines in enumerate(pages):
        text = "\n".join(lines[:8])
        layout = "shares" if _HEADING_SHARES.search(text) else "table" if _HEADING_TABLE.search(text) else None
        if not layout:
            continue
        year_match = _AS_OF.search(text)
        if not year_match:
            continue
        chunk = lines + (pages[index + 1] if index + 1 < len(pages) else [])
        members = (parse_shares_layout if layout == "shares" else parse_table_layout)(chunk)
        if len(members) >= 30:
            tables.append((int(year_match.group(1)), layout, members))
    return tables


def main(argv: list[str]) -> int:
    years = [int(a) for a in argv] or list(range(2002, 2022))
    rows = []
    for year in years:
        directory = doc_dir(year)
        if directory is None or not list(directory.glob("p*.txt")):
            print(f"{year}: no text cache")
            continue
        found = [t for t in find_tables(directory) if t[0] == year]
        if not found:
            print(f"{year}: no subscriptions table for that year found")
            continue
        table_year, layout, members = found[0]
        if layout == "table":
            # Dollars are not a clean guide to voting shares (Canada carries non-voting temporary
            # shares; 2011-2013 include capital-increase shares not yet issued), so the capital
            # share is rebuilt from the printed % of votes: votes = shares + 135 basic votes
            # per member, hence share_i = (pct_i - c) / (100 - N c), c = 13500 / total votes.
            # Total votes is estimated from the dollars (10% off moves c by 1e-4 pp).
            n = len(members)
            total_votes = sum(a for a, _ in members.values()) / USD_MILLION_PER_SHARE + BASIC_VOTES * n
            c = BASIC_VOTES * 100 / total_votes
            members = {name: ((pct - c) / (100 - n * c) * 100, pct) for name, (_, pct) in members.items()}
        total_amount = sum(v[0] for v in members.values())
        total_pct = sum(v[1] for v in members.values())
        worst = max(members, key=lambda n: abs(members[n][0] / total_amount * 100 - members[n][1]))
        print(f"    largest capital-vs-votes gap: {worst} {members[worst][0] / total_amount * 100:.3f} vs {members[worst][1]:.3f}")
        status = "OK" if 99.9 <= total_pct <= 100.1 else f"CHECK votes sum {total_pct:.3f}"
        print(f"{year}: {layout} layout, {len(members)} members, votes % sum {total_pct:.3f} {status}")
        for name, (amount, pct) in members.items():
            rows.append({"bank": "IDB", "iso3": iso3_from_name(name), "year": table_year,
                         "capital_share_pct": round(amount / total_amount * 100, 6), "voting_power_pct": pct,
                         "source_url": f"data/raw/annual_reports/{directory.name}.pdf", "note": ""})
    rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, rows)
    print(f"{len(rows)} rows -> {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
