"""Coverage report for the enriched panel: what share of
data/output/mdb_panel_with_controls.csv's rows have a real (non-null) value
for each control variable and project-breakdown column -- the same idea as
`report_zero_share.py`'s coverage table, applied to this session's control
variables instead of lending. A report, not an assertion: prints and writes a
CSV, never fails the build. Gaps here are expected (see `build_control_
variables.py`'s own per-source docstring for why) -- this just makes them
visible instead of silently assumed away.

Usage:  python3 scripts/report_control_coverage.py [--panel PATH] [--report PATH] [--by-year PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import OUTPUT_DIR, REPO, REPORTS_DIR, write_csv  # noqa: E402

PANEL_CSV = OUTPUT_DIR / "mdb_panel_with_controls.csv"
REPORT_CSV = REPORTS_DIR / "control_coverage.csv"

_BASE_PANEL_COLUMNS = {
    "bank", "iso3", "year", "eligibility_basis", "capital_share_pct", "voting_power_pct",
    "recipient_status", "member_since", "projects", "projects_with_positive_amount",
    "any_lending", "amount_available", "usd_nominal_total", "usd_2025_total", "ppp_2025_total", "note",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--report", type=Path, default=REPORT_CSV)
    parser.add_argument("--by-year", type=Path, default=None,
                         help="also write a (column, year) coverage breakdown to this path")
    args = parser.parse_args(argv)

    if not args.panel.is_file():
        print(f"error: {args.panel} does not exist. Run: make controls", file=sys.stderr)
        return 2

    df = pd.read_csv(args.panel)
    total = len(df)
    columns = [c for c in df.columns if c not in _BASE_PANEL_COLUMNS]

    rows = []
    for col in columns:
        non_null = int(df[col].notna().sum())
        rows.append({"column": col, "non_null": non_null, "total": total,
                     "coverage_pct": round(non_null / total * 100, 1) if total else 0})
    rows.sort(key=lambda r: r["coverage_pct"], reverse=True)

    write_csv(args.report, ["column", "non_null", "total", "coverage_pct"], rows)
    print(f"{len(columns)} control/breakdown columns, {total} panel rows")
    print(f"\n{'column':45} {'coverage':>10}")
    for r in rows:
        print(f"{r['column']:45} {r['coverage_pct']:>9}%")
    print(f"\n-> {args.report.relative_to(REPO) if args.report.is_relative_to(REPO) else args.report}")

    if args.by_year:
        year_rows = []
        for col in columns:
            for year, group in df.groupby("year"):
                non_null = int(group[col].notna().sum())
                total_y = len(group)
                year_rows.append({
                    "column": col, "year": int(year), "non_null": non_null, "total": total_y,
                    "coverage_pct": round(non_null / total_y * 100, 1) if total_y else 0,
                })
        write_csv(args.by_year, ["column", "year", "non_null", "total", "coverage_pct"], year_rows)
        print(f"-> {args.by_year.relative_to(REPO) if args.by_year.is_relative_to(REPO) else args.by_year} "
              f"(by-year breakdown, {len(year_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
