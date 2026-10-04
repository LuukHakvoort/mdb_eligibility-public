"""CDB's capital share and voting power per member, 2002-2025, from the "subscriptions
by member countries and their voting power" note / Schedule 3 ("Statement of
Subscription to Capital Stock and Voting Power") of the Ordinary Capital Resources
financial statements inside CDB's annual reports (data/raw/annual_reports/cdb_<year>.pdf,
downloaded by hand: caribank.org is not fetchable by script).

Reads the cached page text (scripts/dump_pdf_text.py -> data/raw/text/cdb_<year>/), which
repairs the rotated and doubled-glyph pages several years use. The table is found by
content: pages with a "Voting Power" header and member rows. Each document carries the
year-end table and the prior year's; both are read and the document's own year wins.

Per member: shares -> capital share = shares over all members' shares; votes -> voting
power = votes over all votes. The five UK territories (Anguilla, Montserrat, British
Virgin Islands, Cayman Islands, Turks and Caicos) are "a single member" for voting
(Charter Art. 3): their votes are printed once, on one row, so the others have capital
share only. Both recomputed values are checked against the printed percentage columns.

Usage:  python3 scripts/annual_reports_cdb_ar.py [year ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, MANUAL_DIR, REPO, REPORTS_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

TEXT_DIR = REPO / "data" / "raw" / "text"
TARGET = EXTRACTED_DIR / "shares_cdb_ar.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_cdb_ar_unresolved.csv"
ANNUAL_REPORTS_CSV = MANUAL_DIR / "annual_reports.csv"
FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_NAME_FIXUPS = {
    "St. Lucia": "Saint Lucia", "St Lucia": "Saint Lucia",
    "St. Vincent and the Grenadines": "Saint Vincent and the Grenadines",
    "St. Kitts and Nevis": "Saint Kitts and Nevis", "St. Kitts & Nevis": "Saint Kitts and Nevis",
    "Turks and Caicos": "Turks and Caicos Islands",
    "Bahamas, The": "Bahamas",
}
_FOOTNOTE = re.compile(r"\s*/?\s*\d\s*/?\s*$")
_ROW = re.compile(r"^([A-Za-z][A-Za-z .,'&/\d-]*?)\s+(\d{1,3}(?:,\d{3})*)\s+(\d+\.\d+)\b(.*)$")
_ROW_NAME_BELOW = re.compile(r"^(\d{1,3}(?:,\d{3})*)\s+(\d+\.\d+)\b(.*)$")  # 2013: the name is on the line after its numbers
_DECIMAL = re.compile(r"(?<![\d,.])\d+\.\d+(?![\d.])")
_INT = re.compile(r"(?<![\d.$])\d{1,3}(?:,\d{3})+(?![\d.])|(?<![\d.,$])\d{3,}(?![\d.,])")
_YEAR_LINE = re.compile(r"^(20\d{2}|19\d{2})$")
_HEADER = re.compile(r"voting power|no\. of", re.I)


def _clean(name: str) -> str:
    name = re.sub(r"\s+", " ", _FOOTNOTE.sub("", name)).strip(" .").replace(" & ", " and ")
    return _NAME_FIXUPS.get(name, name)


def pages_for(year: int) -> list[list[str]]:
    directory = TEXT_DIR / f"cdb_{year}"
    return [(f.read_text(encoding="utf-8").splitlines()) for f in sorted(directory.glob("p*.txt"))]


def _is_fragment(line: str) -> bool:
    line = re.sub(r"\s*/?\s*\d\s*/?\s*$", "", line) if re.search(r"/", line) else line
    return bool(line) and not re.search(r"\d", line) and len(line) < 40 and not line.endswith(":")


def _member_rows(lines: list[str]) -> list[tuple[str, int, float, float | None, int | None]]:
    """(name, shares, % of shares, votes, % of votes) rows in reading order. Long
    names wrap across lines, before the numbers ("Trinidad and / Tobago 19,342 ...")
    or after them ("St. Vincent 859 ... / and the / Grenadines"); a name that does not
    resolve on its own is tried joined to the fragment above, then to those below."""

    rows = []
    pending = ""
    cleaned = [line.strip().replace("$", "") for line in lines]
    for index, line in enumerate(cleaned):
        match = _ROW.match(line)
        below = _ROW_NAME_BELOW.match(line) if not match else None
        if below and index + 1 < len(cleaned):
            name = ""
            bloc = None
            for extra in cleaned[index + 1: index + 4]:
                bloc_match = re.match(r"^(.*?/\s*\d)\s+(\d{1,3},\d{3})\s+(\d+\.\d+)$", extra)
                if bloc_match:  # the UK territories' pooled votes ride on the British Virgin Islands line
                    extra, bloc = bloc_match.group(1), (int(bloc_match.group(2).replace(",", "")), float(bloc_match.group(3)))
                if not _is_fragment(extra):
                    break
                name = _clean(f"{name} {extra}")
                if iso3_from_name(name):
                    break
            if not iso3_from_name(name):
                continue
            match = re.match(r"^(.*)$", "")
            shares, pct, rest = int(below.group(1).replace(",", "")), float(below.group(2)), below.group(3)
            decimals = _DECIMAL.findall(rest)
            votes_pct = float(decimals[-1]) if decimals else None
            votes = None
            if votes_pct is not None:
                ints = _INT.findall(rest[: rest.rfind(decimals[-1])])
                votes = int(ints[-1].replace(",", "")) if ints else None
            if bloc:
                votes, votes_pct = bloc
            rows.append((name, shares, pct, votes, votes_pct))
            pending = ""
            continue
        if not match:
            if _is_fragment(line):
                pending = line
            continue
        name, shares, pct, rest = _clean(match.group(1)), int(match.group(2).replace(",", "")), float(match.group(3)), match.group(4)
        if pending and not iso3_from_name(name):
            joined = _clean(f"{pending} {name}")
            if iso3_from_name(joined):
                name = joined
        if not iso3_from_name(name):
            tail = name
            for extra in cleaned[index + 1: index + 4]:
                if not _is_fragment(extra):
                    break
                tail = _clean(f"{tail} {extra}")
                if iso3_from_name(tail):
                    name = tail
                    break
        pending = ""
        decimals = _DECIMAL.findall(rest)
        votes_pct = float(decimals[-1]) if decimals else None
        votes = None
        if votes_pct is not None:
            before = rest[: rest.rfind(decimals[-1])]
            ints = _INT.findall(before)
            votes = int(ints[-1].replace(",", "")) if ints else None
        rows.append((name, shares, pct, votes, votes_pct))
    return rows


def tables_for(year: int) -> dict[int, list[tuple]]:
    """{table year: member rows} from the contiguous pages that carry the subscription
    tables. A table's year is the bare year line above it; the first unlabelled table
    is the document's own year, the next one the prior year."""

    pages = pages_for(year)
    candidates = []
    for index, lines in enumerate(pages):
        text = "\n".join(lines)
        rows = _member_rows(lines)
        resolved = [r for r in rows if iso3_from_name(r[0])]
        if len(resolved) >= 4 and _HEADER.search(text) and re.search(r"member", text, re.I):
            candidates.append(index)
    # the Non-Regional States continue on the next page, which carries no header of its own
    for index in list(candidates):
        following = index + 1
        if following < len(pages) and following not in candidates:
            if len([r for r in _member_rows(pages[following]) if iso3_from_name(r[0])]) >= 3:
                candidates.append(following)
    candidates.sort()
    tables: dict[int, list[tuple]] = {}
    ordered: list[tuple[int | None, list[tuple]]] = []
    current_year: int | None = None
    current: list[tuple] = []
    for index in candidates:
        for line in pages[index]:
            stripped = line.strip()
            if _YEAR_LINE.match(stripped) and int(stripped) != current_year:
                if current:
                    ordered.append((current_year, current))
                current_year, current = int(stripped), []
        current += [r for r in _member_rows(pages[index]) if iso3_from_name(r[0])]
    if current:
        ordered.append((current_year, current))
    seen_years: list[int] = []
    for label, rows in ordered:
        table_year = label if label else (year if year not in tables else year - 1)
        if table_year in tables:
            table_year = year - 1 if table_year == year else table_year
        if table_year not in tables and len(rows) >= 10:
            tables[table_year] = rows
    return tables


def build_rows(table_year: int, rows: list[tuple], source: str) -> tuple[list[dict], list[str]]:
    # one row per member (the "Additional subscriptions" repeat has no decimals so is not here)
    by_member: dict[str, tuple] = {}
    for row in rows:
        by_member.setdefault(row[0], row)
    total_shares = sum(r[1] for r in by_member.values())
    total_votes = sum(r[3] for r in by_member.values() if r[3])
    problems = []
    out = []
    for name, (_, shares, pct, votes, votes_pct) in by_member.items():
        capital = shares / total_shares * 100
        if abs(capital - pct) > 0.06:
            problems.append(f"{name}: computed {capital:.2f}% vs printed {pct}%")
        voting = ""
        if votes and total_votes:
            voting = round(votes / total_votes * 100, 6)
            if votes_pct is not None and abs(voting - votes_pct) > 0.06:
                problems.append(f"{name}: votes computed {voting:.2f}% vs printed {votes_pct}%")
        out.append({"bank": "CDB", "iso3": iso3_from_name(name), "year": table_year,
                    "capital_share_pct": round(capital, 6), "voting_power_pct": voting, "source_url": source,
                    "note": "" if voting != "" else "UK-territory bloc row: no individual voting power printed (single member for voting, Charter Art. 3)."})
    return out, problems


def main(argv: list[str]) -> int:
    years = [int(a) for a in argv] or list(range(2002, 2026))
    sources = {int(r["year"]): r["url"] for r in read_csv(ANNUAL_REPORTS_CSV) if r.get("bank") == "CDB"}
    result: dict[int, tuple[list[dict], str]] = {}
    ranks: dict[int, tuple[bool, bool]] = {}
    for year in years:
        if not (TEXT_DIR / f"cdb_{year}").is_dir():
            print(f"{year}: no text cache")
            continue
        tables = tables_for(year)
        for table_year, rows in sorted(tables.items()):
            source = f"data/raw/annual_reports/cdb_{year}.pdf"
            built, problems = build_rows(table_year, rows, source)
            own = table_year == year
            # the document's own table wins, unless it fails to reconcile and a comparative does
            rank = (bool(problems), not own)
            if table_year not in result or rank < ranks[table_year]:
                result[table_year] = (built, source)
                ranks[table_year] = rank
            print(f"{year}: table {table_year}{'' if own else ' (prior-year comparative)'}: {len(built)} members"
                  f"{' PROBLEMS: ' + '; '.join(problems[:3]) if problems else ' OK'}")
        if not tables:
            print(f"{year}: no table found")
    all_rows = [r for _, (rows, _) in sorted(result.items()) for r in rows]
    all_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, all_rows)
    print(f"\n{len(all_rows)} rows -> {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
