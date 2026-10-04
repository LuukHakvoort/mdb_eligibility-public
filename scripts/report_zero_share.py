"""Zero-share report: how much of each bank's eligible panel shows no lending.

A bank whose eligible dyad-years are overwhelmingly empty usually has an
eligibility set that is too wide -- most often the membership-versus-recipient-
status confusion (collection plan section 3.4). Above roughly 95%, look again.

An eligible dyad-year outside the bank's own data-coverage window (e.g. CDB
2024-2026, BADEA 2023-2026 -- see data/extracted/bank_coverage.csv) is excluded
from the share entirely: "no lending because the source doesn't cover this
year" is not evidence the eligibility set is too wide, and counting it in would
inflate the share for exactly the banks whose source is thinnest.

This is a report, not an assertion: it prints, writes a CSV, and exits 0. High
shares are a signal to investigate, not proof of an error, and some banks (NDB,
AIIB early on) genuinely lend to few of their eligible members.

Usage:  python3 scripts/report_zero_share.py [--commitments PATH] [--eligibility PATH]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _panel import (
    BANK_COVERAGE_CSV, BANKS, COMMITMENTS_CSV, ELIGIBILITY_CSV, REPORTS_DIR, REPO,
    in_coverage, load_bank_coverage, load_commitments, load_eligibility, write_csv,
)

FIELDS = [
    "bank", "eligible_dyad_years", "out_of_coverage", "in_coverage_dyad_years",
    "with_lending", "without_lending", "zero_share", "flag",
]
SUSPICIOUS_SHARE = 0.95


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--commitments", type=Path, default=COMMITMENTS_CSV)
    parser.add_argument("--eligibility", type=Path, default=ELIGIBILITY_CSV)
    parser.add_argument("--coverage", type=Path, default=BANK_COVERAGE_CSV)
    parser.add_argument("--report", type=Path, default=REPORTS_DIR / "zero_share.csv")
    args = parser.parse_args(argv)

    commitments = load_commitments(args.commitments)
    eligibility, exists = load_eligibility(args.eligibility)
    coverage = load_bank_coverage(args.coverage)
    if not exists:
        print(
            f"note: {args.eligibility} does not exist yet; no dyad-year is eligible, so every "
            "bank reports n/a."
        )

    observed = {(row["bank"], row["iso3"], row["year"]) for row in commitments}
    eligible = {
        (row["bank"], row["iso3"], row["year"]) for row in eligibility if row["eligible"] is True
    }

    rows: list[dict] = []
    print(f"\n{'bank':6} {'eligible':>9} {'in-cov':>7} {'lending':>8} {'no lending':>11} {'zero share':>11}")
    for bank in BANKS:
        bank_eligible = {key for key in eligible if key[0] == bank}
        in_window = {key for key in bank_eligible if in_coverage(bank, key[2], coverage)}
        out_of_window = len(bank_eligible) - len(in_window)
        with_lending = len(in_window & observed)
        total_in_window = len(in_window)
        without = total_in_window - with_lending
        share = (without / total_in_window) if total_in_window else None
        flag = "" if share is None else ("WIDE?" if share > SUSPICIOUS_SHARE else "")
        rows.append({
            "bank": bank,
            "eligible_dyad_years": len(bank_eligible),
            "out_of_coverage": out_of_window,
            "in_coverage_dyad_years": total_in_window,
            "with_lending": with_lending,
            "without_lending": without,
            "zero_share": "" if share is None else f"{share:.3f}",
            "flag": flag,
        })
        printed = "n/a" if share is None else f"{share:6.1%}"
        print(f"{bank:6} {len(bank_eligible):9} {out_of_window:7} {with_lending:8} {without:11} {printed:>11} {flag}")

    write_csv(args.report, FIELDS, rows)
    total_eligible = sum(int(row["eligible_dyad_years"]) for row in rows)
    if not total_eligible:
        print("\nNo eligible dyad-years yet: the panel is empty, so there is nothing to judge.")
    print(
        f"\nWrote {args.report.relative_to(REPO) if args.report.is_relative_to(REPO) else args.report}"
        f" ({total_eligible} eligible dyad-years; {len(observed)} observed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
