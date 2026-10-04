"""Build data/extracted/other_mdb_lending.csv -- the H4 instrument: for
every (excluded bank, recipient iso3, year), how much every *other*
eligible MDB lent to that recipient that year. Needs no external dataset --
derived entirely from data/output/mdb_panel.csv, which already has one row
per eligible (or revealed-eligible) (bank, iso3, year) with a USD total.

**The pool, for a given (excluded_bank, iso3, year)**: every OTHER bank
with its own row for that exact (iso3, year) in mdb_panel.csv. A bank with
no row there isn't part of the pool at all -- it was structurally unable to
lend (ineligible or didn't exist yet that year), not a missing observation.
This matches the project's own framing of eligibility as a sample
restriction (docs/CLAUDE.md's opening paragraph), not a covariate.

**Two totals, per the user's own explicit spec** (2026-09-30):
- `other_mdb_usd_available` -- sum of the pool's `usd_2025_total`, with a
  blank pool member treated as 0 (best-effort; safe to use directly in a
  regression without the missingness itself distorting the sum).
- `other_mdb_usd_strict` -- the same sum, but blank if ANY pool member's
  `usd_2025_total` is itself blank (a genuine data gap, not zero lending) --
  a robustness check, not the default.
Plus `other_mdb_n_eligible` (pool size) and `other_mdb_n_missing_amount`
(how many of the pool had a blank amount) -- the coverage diagnostics.

`scripts/merge_other_mdb_lending.py` is the companion script that lags this
table by one year and merges the `_t1` versions onto the wide panel.

Usage:  python3 scripts/build_other_mdb_lending.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, OUTPUT_DIR, REPO  # noqa: E402

PANEL_CSV = OUTPUT_DIR / "mdb_panel.csv"
TARGET = EXTRACTED_DIR / "other_mdb_lending.csv"

OUTPUT_COLUMNS = [
    "bank", "iso3", "year",
    "other_mdb_usd_available", "other_mdb_usd_strict",
    "other_mdb_n_eligible", "other_mdb_n_missing_amount",
    "other_mdb_ppp_available", "other_mdb_ppp_strict", "other_mdb_ppp_n_missing_amount",
]


def build(panel: pd.DataFrame) -> pd.DataFrame:
    """For every (bank, iso3, year) row in `panel`, sum every OTHER bank's
    usd_2025_total (and the PPP-adjusted ppp_2025_total) at that same (iso3, year). Split out from main() so
    tests can exercise it directly on a small fixture."""

    if panel.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    grid = panel[["bank", "iso3", "year"]].drop_duplicates()
    pool = panel[["bank", "iso3", "year", "usd_2025_total", "ppp_2025_total"]].rename(
        columns={"bank": "_other_bank"})

    # Every (focal bank, iso3, year) joined against every row sharing that
    # (iso3, year) -- then the focal bank's own row is excluded from its
    # own pool.
    joined = grid.merge(pool, on=["iso3", "year"], how="left")
    joined = joined[joined["bank"] != joined["_other_bank"]]

    agg = joined.groupby(["bank", "iso3", "year"], as_index=False).agg(
        other_mdb_usd_available=("usd_2025_total", lambda s: s.fillna(0).sum()),
        other_mdb_usd_strict=("usd_2025_total", lambda s: s.sum() if s.notna().all() else pd.NA),
        other_mdb_n_eligible=("usd_2025_total", "size"),
        other_mdb_n_missing_amount=("usd_2025_total", lambda s: int(s.isna().sum())),
        # PPP version, same pool (2026-10-04): an unpriced member counts as 0 in
        # the available total, exactly as an unmatched USD member does.
        other_mdb_ppp_available=("ppp_2025_total", lambda s: s.fillna(0).sum()),
        other_mdb_ppp_strict=("ppp_2025_total", lambda s: s.sum() if s.notna().all() else pd.NA),
        other_mdb_ppp_n_missing_amount=("ppp_2025_total", lambda s: int(s.isna().sum())),
    )

    # A (bank, iso3, year) with no other eligible bank at all (pool size 0)
    # is a real, countable zero -- an empty sum is 0, not missing, and its
    # diagnostics correctly read 0/0 rather than disappearing from the
    # output (grid's left-merge keeps it; groupby on a pool of size 0
    # wouldn't produce a row on its own, so re-merge onto the full grid).
    out = grid.merge(agg, on=["bank", "iso3", "year"], how="left")
    out["other_mdb_usd_available"] = out["other_mdb_usd_available"].fillna(0.0)
    out["other_mdb_n_eligible"] = out["other_mdb_n_eligible"].fillna(0).astype(int)
    out["other_mdb_n_missing_amount"] = out["other_mdb_n_missing_amount"].fillna(0).astype(int)
    out["other_mdb_ppp_available"] = out["other_mdb_ppp_available"].fillna(0.0)
    out["other_mdb_ppp_n_missing_amount"] = out["other_mdb_ppp_n_missing_amount"].fillna(0).astype(int)
    # other_mdb_usd_strict: an empty pool sums to a real 0 too (no
    # component can be missing if there are no components) -- only leave it
    # blank where a real pool had at least one missing component.
    out.loc[out["other_mdb_n_eligible"] == 0, "other_mdb_usd_strict"] = 0.0
    out.loc[out["other_mdb_n_eligible"] == 0, "other_mdb_ppp_strict"] = 0.0

    return out.sort_values(["bank", "iso3", "year"])[OUTPUT_COLUMNS].reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--output", type=Path, default=TARGET)
    args = parser.parse_args(argv)

    if not args.panel.is_file():
        print(f"error: {args.panel} does not exist. Run: make panel", file=sys.stderr)
        return 2

    panel = pd.read_csv(args.panel, usecols=["bank", "iso3", "year", "usd_2025_total", "ppp_2025_total"])
    out = build(panel)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)

    output_display = args.output.relative_to(REPO) if args.output.is_relative_to(REPO) else args.output
    print(f"{len(out)} (bank, iso3, year) rows -> {output_display}")
    print(f"  other_mdb_n_eligible == 0 (no other eligible bank that year): "
          f"{int((out['other_mdb_n_eligible'] == 0).sum())} rows")
    print(f"  other_mdb_usd_strict blank (a real missing component): "
          f"{int(out['other_mdb_usd_strict'].isna().sum())} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
