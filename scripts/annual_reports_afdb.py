"""Parse AfDB's "Distribution of Voting Powers by Executive Director"
monthly statement into voting-power data for AfDB (not ADF -- this document
series is specifically AfDB-proper's, confirmed live: AfDB publishes AfDB
and ADF as two entirely separate monthly statement series on afdb.org).

**Gives `voting_power_pct` only, not `capital_share_pct`** -- a real,
honest scope limit, not an oversight: this specific document is titled
"Distribution of Voting Powers," and only carries vote counts and voting
percentages, no capital-subscription amounts. A different AfDB statement
series ("Statement of Subscription and Voting Powers") would be needed for
capital share; not fetched this pass.

**Every (name, votes, %) triple on the page is extracted, then deduplicated
by name -- not filtered by x-position.** Each row has *two* side-by-side
blocks: the country's own entry on the left (alphabetical), and a second
block on the right showing every country again, grouped by which Executive
Director represents its constituency (with subtotals). This looked at
first like a left/right column-position problem (and briefly was coded that
way), but a fixed x-position threshold doesn't hold across every row --
confirmed live: "BDIR.1" starts at x0=238.9 on one row (just past a first
threshold guess of 250) while the very next word ("Ms.") starts at
x0=297.8, and some countries' *right-side* constituency entries also fall
well left of any single sane threshold depending on how many director-name
words precede them. The right block is not new information anyway -- it
reports the exact same country and percentage the left block already gave,
just reorganized. So instead: every maximal run of non-numeric words
followed by exactly two numbers (votes, then a percentage) is read as a
candidate anywhere on the page, and results are deduplicated by country
name at the end (keeping one; the two occurrences are checked to agree).

Two pages per document, confirmed real: page 1 is "Regional Members," page
2 is "Non-Regional Members" -- both parsed, giving AfDB's full membership,
not just the regional half.

Usage:  python3 scripts/annual_reports_afdb.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, MANUAL_DIR, REPO, REPORTS_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402
from annual_reports import fetch  # noqa: E402

ANNUAL_REPORTS_CSV = MANUAL_DIR / "annual_reports.csv"
TARGET = EXTRACTED_DIR / "shares_afdb_voting.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_afdb_voting_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_SAME_ROW_TOLERANCE = 2.0
_NO_CAPITAL_NOTE = (
    "This document (\"Distribution of Voting Powers by Executive Director\") gives "
    "voting power only, no capital-subscription amounts -- capital_share_pct not "
    "available from this source."
)

# AfDB's own country-name abbreviations in this document that don't already
# resolve against the shared codelist.
_NAME_FIXUPS = {
    "CENT.AFR.REP": "Central African Republic",
    "DEM.REP.CONGO": "Congo, the Democratic Republic of the",
    "EQ.GUINEA": "Equatorial Guinea",
    "GUINEA BISSAU": "Guinea-Bissau",
    "TÜRKIYE": "Turkey",
    "TURKIYE": "Turkey",
    "SAO TOME & P.": "Sao Tome and Principe",
    "KOREA": "Korea, Rep.",
    "U.K.": "United Kingdom",
    "U.S.A": "United States",
}


def _group_into_rows(words: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    current: list[dict] = []
    current_top: float | None = None
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if current_top is None or word["top"] - current_top > _SAME_ROW_TOLERANCE:
            if current:
                rows.append(current)
            current = [word]
            current_top = word["top"]
        else:
            current.append(word)
    if current:
        rows.append(current)
    return rows


_SKIP_NAMES = {
    "TOTAL REGIONALS", "TOTAL NON-REGIONALS", "GRAND TOTAL", "TOTAL",
    "VOTING POWERS", "EXECUTIVE DIRECTOR", "BDIR OFFICE", "ALTERNATE EXECUTIVE DIRECTOR",
}


def _is_number(text: str) -> bool:
    return text.replace(",", "").replace(".", "").isdigit()


def _extract_candidates(row_words: list[dict]) -> list[tuple[str, float]]:
    """Every (name, percentage) candidate anywhere in this row -- a row can
    hold more than one (the left block's own entry, plus however many
    countries' redundant constituency entries also land on this visual
    line). See module docstring for why this replaced x-position filtering."""

    ordered = sorted(row_words, key=lambda w: w["x0"])
    candidates: list[tuple[str, float]] = []
    i = 0
    while i < len(ordered):
        if _is_number(ordered[i]["text"]) or ordered[i]["text"].startswith("BDIR"):
            i += 1
            continue
        name_parts = []
        while i < len(ordered) and not _is_number(ordered[i]["text"]) and not ordered[i]["text"].startswith("BDIR"):
            name_parts.append(ordered[i]["text"])
            i += 1
        if i + 1 < len(ordered) and _is_number(ordered[i]["text"]) and _is_number(ordered[i + 1]["text"]):
            name = " ".join(name_parts)
            if name not in _SKIP_NAMES and "." not in ordered[i]["text"]:  # votes count, not itself a percentage
                try:
                    candidates.append((name, float(ordered[i + 1]["text"])))
                except ValueError:
                    pass
            i += 2
    return candidates


def parse_pdf(path: Path, year: int, source_url: str) -> tuple[list[dict], list[dict], list[dict]]:
    import pdfplumber

    raw_candidates: list[tuple[str, float]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            for row_words in _group_into_rows(words):
                raw_candidates += _extract_candidates(row_words)

    # Deduplicate by name -- the left (alphabetical) and right (by-
    # constituency) blocks report the same country twice. Disagreements are
    # reported, not silently resolved (see module docstring).
    by_name: dict[str, list[float]] = {}
    for name, pct in raw_candidates:
        by_name.setdefault(name, []).append(pct)

    rows: list[dict] = []
    unresolved: list[dict] = []
    conflicts: list[dict] = []
    total = 0.0
    for name, pcts in by_name.items():
        if len(set(pcts)) > 1:
            conflicts.append({"year": year, "name_raw": name, "values": pcts})
        pct = pcts[0]
        resolved_name = _NAME_FIXUPS.get(name, name)
        iso3 = iso3_from_name(resolved_name)
        if not iso3:
            unresolved.append({"year": year, "name_raw": name})
            continue
        total += pct
        rows.append({
            "bank": "AfDB", "iso3": iso3, "year": year,
            "capital_share_pct": "",
            "voting_power_pct": pct,
            "source_url": source_url,
            "note": _NO_CAPITAL_NOTE,
        })
    if not (95 <= total <= 105):
        raise SystemExit(f"error: voting powers in {path} sum to {total:.2f}%, not ~100% "
                          f"({len(rows)} rows, {len(unresolved)} unresolved, {len(conflicts)} conflicts)")
    return rows, unresolved, conflicts


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    all_conflicts: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "AfDB":
            continue
        year = int(row["year"])
        url = row["url"]
        path = fetch(url, f"afdb_voting_{year}.pdf")
        rows, unresolved, conflicts = parse_pdf(path, year, url)
        all_rows += rows
        all_unresolved += unresolved
        all_conflicts += conflicts
        total_voting = sum(r["voting_power_pct"] for r in rows)
        print(f"{year}: {len(rows)} rows, voting powers sum to {total_voting:.2f}% "
              f"({'OK' if 95 <= total_voting <= 105 else 'CHECK THIS'})")

    all_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, all_rows)
    write_csv(UNRESOLVED_REPORT, ["year", "name_raw"], all_unresolved)
    if all_conflicts:
        write_csv(REPORTS_DIR / "shares_afdb_voting_conflicts.csv", ["year", "name_raw", "values"], all_conflicts)
    print(f"\n{len(all_rows)} rows -> {TARGET.relative_to(REPO)}")
    print(f"{len(all_unresolved)} unresolved names -> {UNRESOLVED_REPORT.relative_to(REPO)}")
    print(f"{len(all_conflicts)} names had disagreeing left/right-block values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
