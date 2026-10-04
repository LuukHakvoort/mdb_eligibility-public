"""The revealed-eligibility assertion: observed lending implies eligibility.

If a bank financed a country in a year, that dyad-year was eligible, whatever
the panel says. This is the strongest check available, because it uses ground
truth rather than a second reading of the same sources.

Violations are reported in three kinds, because they mean different things:

- **not yet coded** -- no row in eligibility.csv, or `eligible` is blank. This
  is the expected state early on and shrinks as the manual data is filled in.
- **contradiction** -- a row exists saying `eligible = 0` although the bank
  demonstrably lent. That is a coding error to fix now, while the source that
  produced it is still to hand.
- **accepted exception** -- a "not yet coded" or "contradiction" row that a
  prior session already investigated and explicitly decided not to change
  (`data/manual/accepted_revealed_exceptions.csv`, 2026-09-30) -- e.g. IDA's
  post-graduation transitional lending, or EIB's own-risk lending with no
  public country list to encode against. Still fully listed in the report,
  still visible, but does **not** fail the build: the whole point of this
  check is to catch a *new, unexplained* gap, not to perpetually re-flag a
  case this project has already researched and understood. Zero *unexplained*
  violations are permitted (docs/CLAUDE.md, "Validation").

Usage:  python3 scripts/check_revealed.py [--commitments PATH] [--eligibility PATH]
        [--accepted PATH] [--show N]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from _panel import (
    BANKS, COMMITMENTS_CSV, ELIGIBILITY_CSV, MANUAL_DIR, REPORTS_DIR, REPO,
    load_commitments, load_eligibility, write_csv,
)

VIOLATION_FIELDS = ["bank", "iso3", "year", "kind", "projects"]
ACCEPTED_EXCEPTIONS_CSV = MANUAL_DIR / "accepted_revealed_exceptions.csv"


def load_accepted_exceptions(path: Path) -> set[tuple[str, str, int]]:
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {(row["bank"], row["iso3"], int(row["year"])) for row in csv.DictReader(handle)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--commitments", type=Path, default=COMMITMENTS_CSV)
    parser.add_argument("--eligibility", type=Path, default=ELIGIBILITY_CSV)
    parser.add_argument("--accepted", type=Path, default=ACCEPTED_EXCEPTIONS_CSV)
    parser.add_argument("--report", type=Path, default=REPORTS_DIR / "revealed_violations.csv")
    parser.add_argument("--show", type=int, default=5, help="Example violations per bank to print")
    args = parser.parse_args(argv)

    commitments = load_commitments(args.commitments)
    eligibility, exists = load_eligibility(args.eligibility)
    if not exists:
        print(
            f"note: {args.eligibility.relative_to(REPO) if args.eligibility.is_relative_to(REPO) else args.eligibility}"
            " does not exist yet; every observed dyad-year counts as not yet coded."
        )
    accepted = load_accepted_exceptions(args.accepted)

    coded = {(row["bank"], row["iso3"], row["year"]): row["eligible"] for row in eligibility}

    violations: list[dict] = []
    for row in commitments:
        key = (row["bank"], row["iso3"], row["year"])
        verdict = coded.get(key)
        if verdict is True:
            continue
        if key in accepted:
            kind = "accepted exception"
        else:
            kind = "contradiction" if verdict is False else "not yet coded"
        violations.append({
            "bank": row["bank"],
            "iso3": row["iso3"],
            "year": row["year"],
            "kind": kind,
            "projects": row["projects"],
        })

    bank_order = {bank: index for index, bank in enumerate(BANKS)}
    violations.sort(key=lambda row: (bank_order.get(row["bank"], 99), row["iso3"], row["year"]))
    write_csv(args.report, VIOLATION_FIELDS, violations)

    observed = len(commitments)
    unexplained = [row for row in violations if row["kind"] != "accepted exception"]
    contradictions = [row for row in violations if row["kind"] == "contradiction"]
    accepted_rows = [row for row in violations if row["kind"] == "accepted exception"]
    print(f"\n{'bank':6} {'observed':>9} {'covered':>8} {'not coded':>10} "
          f"{'contradiction':>14} {'accepted':>9}")
    for bank in BANKS:
        bank_rows = [row for row in commitments if row["bank"] == bank]
        if not bank_rows:
            continue
        bad = [row for row in violations if row["bank"] == bank]
        not_coded = sum(1 for row in bad if row["kind"] == "not yet coded")
        accepted_n = sum(1 for row in bad if row["kind"] == "accepted exception")
        contra = len(bad) - not_coded - accepted_n
        print(
            f"{bank:6} {len(bank_rows):9} {len(bank_rows) - len(bad):8} "
            f"{not_coded:10} {contra:14} {accepted_n:9}"
        )
        for row in [r for r in bad if r["kind"] == "contradiction"][: args.show]:
            print(f"       ! {row['iso3']} {row['year']}: coded ineligible, but "
                  f"{row['projects']} project(s) observed")

    print(
        f"\n{len(violations)} of {observed} observed dyad-years are not marked eligible "
        f"({len(contradictions)} contradiction(s), {len(accepted_rows)} accepted exception(s)); "
        f"full list -> {args.report.relative_to(REPO) if args.report.is_relative_to(REPO) else args.report}"
    )
    if unexplained:
        print(
            "FAIL: revealed-eligibility assertion. Zero unexplained violations are permitted "
            "before the panel is used (an 'accepted exception' doesn't count -- see data/manual/"
            "accepted_revealed_exceptions.csv).",
            file=sys.stderr,
        )
        return 2
    print("PASS: every observed dyad-year is marked eligible, or is a documented, accepted exception.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
