"""Seed data/manual/accession_dates.csv with one blank row per (bank, country).

The country list is drawn from data/extracted/commitments.csv -- itself built
from the project scraper's own dyad_country_year.csv (see
scripts/build_commitments.py). Observed lending proves the country was a
recipient at some point, so each pair is evidenced rather than guessed -- but
it is a *lower bound* on membership in two ways:

- non-borrowing members never appear (Germany in AIIB, Japan in AsDB, every
  EBRD shareholder that is not a country of operations);
- a member that happens not to have borrowed inside the window is missing.

Those have to be added when the borrowing-member and shareholder lists are
transcribed (data/manual/shares_snapshot_2026-08-25.xlsx is the current-year
starting point -- see docs/manual_data_checklist.md). This file is a worklist
to fill in, not a membership roster.

``accession_date``, ``source`` and ``note`` are deliberately left blank: no
date is inferred from lending data. ``earliest_observed_year`` is filled in --
it is a hard upper bound on accession (if a bank lent to a country in year Y,
it was a member by Y), not a substitute for a real source. Confirm or correct
against it; don't just copy it into accession_date.

Usage:  python3 scripts/seed_accession_dates.py [--force]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from _panel import BANKS, COMMITMENTS_CSV, MANUAL_DIR, REPO, load_commitments
from _reference import country_name

TARGET = MANUAL_DIR / "accession_dates.csv"

FIELDNAMES = [
    "bank", "iso3", "country_name", "accession_date", "source", "note",
    "earliest_observed_year",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite the file even though it may contain hand-entered dates",
    )
    parser.add_argument("--commitments", type=Path, default=COMMITMENTS_CSV)
    args = parser.parse_args(argv)

    if TARGET.exists() and not args.force:
        print(
            f"{TARGET.relative_to(REPO)} already exists; refusing to overwrite hand-entered "
            "data. Pass --force to regenerate from scratch.",
            file=sys.stderr,
        )
        return 2

    if not args.commitments.is_file():
        print(
            f"error: {args.commitments} does not exist. Build it first: "
            "python3 scripts/build_commitments.py",
            file=sys.stderr,
        )
        return 2

    commitments = load_commitments(args.commitments)
    earliest: dict[tuple[str, str], int] = {}
    for row in commitments:
        key = (row["bank"], row["iso3"])
        if key not in earliest or row["year"] < earliest[key]:
            earliest[key] = row["year"]

    rows: list[dict[str, str]] = []
    print(f"{'bank':6} {'pairs':>5}")
    for bank in BANKS:
        pairs = sorted(iso3 for (b, iso3) in earliest if b == bank)
        for iso3 in pairs:
            rows.append({
                "bank": bank,
                "iso3": iso3,
                "country_name": country_name(iso3),
                "accession_date": "",
                "source": "",
                "note": "",
                "earliest_observed_year": str(earliest[(bank, iso3)]),
            })
        print(f"{bank:6} {len(pairs):5}")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("w", encoding="utf-8", newline="") as handle:
        # LF, not the csv module's default CRLF: these files are hand-edited
        # and reviewed as diffs, and .gitattributes normalizes to LF anyway.
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} rows for {len(BANKS)} banks to {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
