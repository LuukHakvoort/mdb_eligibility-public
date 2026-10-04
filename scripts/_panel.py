"""Shared definitions for the panel: banks, paths, and CSV loading.

The three validation checks must agree on what a bank code is, what counts as
an eligible dyad-year, and how a missing file behaves, so those decisions live
here rather than being repeated. Moves into ``src/mdb_eligibility/`` when the
package exists.
"""

from __future__ import annotations

import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANUAL_DIR = REPO / "data" / "manual"
EXTRACTED_DIR = REPO / "data" / "extracted"
OUTPUT_DIR = REPO / "data" / "output"
REPORTS_DIR = OUTPUT_DIR / "reports"

COMMITMENTS_CSV = EXTRACTED_DIR / "commitments.csv"
BANK_COVERAGE_CSV = EXTRACTED_DIR / "bank_coverage.csv"
ELIGIBILITY_CSV = OUTPUT_DIR / "eligibility.csv"

# Canonical bank code -> the project scraper's bank_id. Fourteen institutions:
# CLAUDE.md's canonical list plus CABEI (the collection plan's section 5 counts
# fourteen, and CABEI has real project data).
#
# **ADF was briefly its own canonical bank code (decision 2, 2026-09-24 --
# 2026-09-28), merged back into AfDB.** It was split off to give the
# concessional (African Development Fund) window its own commitments row,
# but never got independent shareholding/membership/mandate/window data of
# its own -- every one of those columns was always copied from AfDB or left
# null, so the split only ever separated *lending*, not any real covariate.
# That lending split also had no honest answer for projects tagged with
# *both* windows (127 of them, and disproportionately the largest ones --
# see docs/coding_decisions.md, 2026-09-28): counting a blended project's
# full dollar amount toward both AfDB and ADF would double-count it.
# AfDB's ordinary-vs-concessional split now lives as columns on one AfDB
# row (`scripts/build_afdb_window_breakdown.py`) instead of as a second bank
# code.
BANKS: dict[str, str] = {
    "IBRD": "ibrd",
    "IDA": "ida",
    "AfDB": "afdb",
    "AsDB": "adb",
    "IDB": "idb",
    "EBRD": "ebrd",
    "EIB": "eib",
    "IsDB": "isdb",
    "CAF": "caf",
    "CDB": "cdb",
    "AIIB": "aiib",
    "BADEA": "badea",
    "NDB": "ndb",
    "CABEI": "cabei",
}

CANONICAL_BANKS: list[str] = list(BANKS)

# The study window (CLAUDE.md), also the scraper's default year filter.
MIN_YEAR = 2002
MAX_YEAR = 2026
YEARS: list[int] = list(range(MIN_YEAR, MAX_YEAR + 1))

COMMITMENTS_FIELDS = ["bank", "iso3", "year", "projects", "projects_with_positive_amount"]

# data/output/eligibility.csv, per CLAUDE.md.
ELIGIBILITY_FIELDS = [
    "bank", "iso3", "year", "bank_exists", "member", "in_mandate", "window_ok",
    "barred", "barred_evidenced", "eligible", "eligible_strict", "member_since",
    "source", "note",
]

TRUE_VALUES = {"1", "true", "yes", "y", "t"}
FALSE_VALUES = {"0", "false", "no", "n", "f"}


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV into stripped string dicts. Tolerates a BOM from Excel."""

    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> Path:
    """Write a CSV as UTF-8 with LF endings, so diffs stay reviewable."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def and3(*values: bool | None) -> bool | None:
    """Three-valued AND: False beats everything, then None, then True.

    Used to combine eligibility's five components: if any is definitely False
    (the bank didn't exist, the country was barred), the combination is False
    even when another component is still unknown. If nothing is False but at
    least one is unknown, the combination is unknown -- not a guess either
    way. Only True in every input yields True.
    """
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


def not3(value: bool | None) -> bool | None:
    """Three-valued NOT: unknown stays unknown."""
    return None if value is None else (not value)


def flag(value: str) -> bool | None:
    """Parse a panel flag. Returns None for blank/unrecognized -- "not coded yet".

    A blank is deliberately not False: the whole point of the harness is to
    tell "no one has coded this" apart from "coded as ineligible".
    """

    text = (value or "").strip().casefold()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return None


def load_commitments(path: Path = COMMITMENTS_CSV) -> list[dict]:
    """Load commitments.csv as {bank, iso3, year:int, projects:int, ...}."""

    if not path.is_file():
        raise SystemExit(
            f"{path} does not exist. Build it first: python3 scripts/build_commitments.py"
        )
    rows: list[dict] = []
    for row in read_csv(path):
        if not row.get("year", "").isdigit():
            continue
        rows.append({
            "bank": row["bank"],
            "iso3": row["iso3"],
            "year": int(row["year"]),
            "projects": int(row.get("projects") or 0),
            "projects_with_positive_amount": int(row.get("projects_with_positive_amount") or 0),
        })
    return rows


def load_bank_coverage(path: Path = BANK_COVERAGE_CSV) -> dict[str, tuple[int | None, int | None]]:
    """Load {bank: (coverage_start_year, coverage_end_year)}, either bound optional.

    Sourced from the project scraper's banks.json (coverage_start_year/
    coverage_end_year) by build_commitments.py -- see docs/architecture.md.
    These mark data coverage, not bank existence: CAF has operated since 1970,
    but its IATI file only starts in 2006. A bank absent from this file (most
    of them) is treated as covered for the whole study window.
    """

    if not path.is_file():
        return {}
    coverage: dict[str, tuple[int | None, int | None]] = {}
    for row in read_csv(path):
        bank = row.get("bank", "")
        if not bank:
            continue
        start = row.get("coverage_start_year", "")
        end = row.get("coverage_end_year", "")
        coverage[bank] = (
            int(start) if start.isdigit() else None,
            int(end) if end.isdigit() else None,
        )
    return coverage


def in_coverage(bank: str, year: int, coverage: dict[str, tuple[int | None, int | None]]) -> bool:
    """True unless `year` falls outside `bank`'s known data-coverage window."""

    start, end = coverage.get(bank, (None, None))
    if start is not None and year < start:
        return False
    if end is not None and year > end:
        return False
    return True


def load_eligibility(path: Path = ELIGIBILITY_CSV) -> tuple[list[dict], bool]:
    """Load eligibility.csv. Returns (rows, exists).

    A missing file is not an error here: until the panel is built, every check
    should still run and report what is missing. Callers say so once, in a
    single line, rather than crashing or silently treating it as empty.
    """

    if not path.is_file():
        return [], False
    rows: list[dict] = []
    for row in read_csv(path):
        if not row.get("year", "").isdigit():
            continue
        rows.append({
            "bank": row.get("bank", ""),
            "iso3": row.get("iso3", ""),
            "year": int(row["year"]),
            "eligible": flag(row.get("eligible", "")),
            "source": row.get("source", ""),
            "note": row.get("note", ""),
        })
    return rows, True
