"""Build data/extracted/shareholder_weights.csv: one shareholder "decision-
making weight" per (bank, iso3, year), derived from data/output/
membership.csv, for the UNGA independent-variable pipeline
(scripts/build_unga_iv.py).

**Weight source**: `voting_power_pct`, falling back to `capital_share_pct`
when voting power is null -- the user's own choice, since without it EIB
(which has zero non-null `voting_power_pct` rows in the whole panel) would
never get any independent-variable coverage at all. `weight_basis` records
which one was actually used ("voting" or "capital").

**Gap-filling (LOCF)**: `capital_share_pct`/`voting_power_pct` are only
populated for the specific years a source snapshot exists -- e.g. AIIB has
capital-share data every year 2016-2025 but voting-power data only for
2022-2024. This script carries the last known weight forward across gap
years, **the user's own choice, for this derived file only** -- it does not
touch `membership.csv`/`shareholders_panel.csv`, which keep their existing
"never interpolate" rule (see docs/coding_decisions.md, 2026-09-27/-28).
Carried-forward rows get `_carried_forward` appended to `weight_basis`, and
`weight_source_year` records which real year the value actually came from
(blank when the row is its own real data).

Carry-forward only ever happens **within a contiguous run of `member == 1`
years** for that (bank, iso3) pair -- never past a year the country actually
left the bank (or was never confirmed a member: `member` is left blank/null
for "not yet coded", not coerced to a guess, matching this project's
three-valued-logic convention throughout). A row with `member != 1` is
dropped entirely before this script even runs, so it can never receive or
donate a carried-forward weight.

Usage:  python3 scripts/build_shareholder_weights.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import OUTPUT_DIR, EXTRACTED_DIR, REPO  # noqa: E402

MEMBERSHIP_CSV = OUTPUT_DIR / "membership.csv"
TARGET = EXTRACTED_DIR / "shareholder_weights.csv"

OUTPUT_COLUMNS = ["bank", "iso3", "year", "weight_pct", "weight_basis", "weight_source_year"]


def compute(membership: pd.DataFrame) -> pd.DataFrame:
    """Apply this module's weight/LOCF logic to an already-loaded membership
    frame. Split out from main() so tests can exercise it directly."""

    df = membership.copy()
    df = df[df["member"] == 1].copy()
    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    df = df.sort_values(["bank", "iso3", "year"]).reset_index(drop=True)

    df["weight_raw"] = df["voting_power_pct"].where(
        df["voting_power_pct"].notna(), df["capital_share_pct"]
    )
    df["basis_raw"] = np.select(
        [df["voting_power_pct"].notna(), df["capital_share_pct"].notna()],
        ["voting", "capital"],
        default=None,
    )
    df["own_year"] = df["year"].where(df["weight_raw"].notna())

    # A contiguous run of member==1 years within one (bank, iso3): breaks
    # wherever the year sequence jumps (a non-member year was filtered out
    # in between). Carry-forward must never cross that break.
    prev_year = df.groupby(["bank", "iso3"])["year"].shift(1)
    new_run = prev_year.isna() | (df["year"] != prev_year + 1)
    df["run_id"] = new_run.groupby([df["bank"], df["iso3"]]).cumsum()

    group_cols = ["bank", "iso3", "run_id"]
    df["weight_pct"] = df.groupby(group_cols)["weight_raw"].ffill()
    df["weight_basis"] = df.groupby(group_cols)["basis_raw"].ffill()
    df["weight_source_year"] = df.groupby(group_cols)["own_year"].ffill()

    carried = df["weight_source_year"].notna() & (df["weight_source_year"] != df["year"])
    df.loc[carried, "weight_basis"] = df.loc[carried, "weight_basis"] + "_carried_forward"
    df["weight_source_year"] = df["weight_source_year"].where(carried)

    out = df[["bank", "iso3", "year", "weight_pct", "weight_basis", "weight_source_year"]].copy()
    out["weight_source_year"] = out["weight_source_year"].astype("Int64")
    return out.sort_values(["bank", "iso3", "year"]).reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--membership", type=Path, default=MEMBERSHIP_CSV)
    parser.add_argument("--output", type=Path, default=TARGET)
    args = parser.parse_args(argv)

    if not args.membership.is_file():
        print(f"error: {args.membership} does not exist. Run: make membership", file=sys.stderr)
        return 2

    membership = pd.read_csv(args.membership)
    out = compute(membership)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)

    real = int((out["weight_source_year"].isna() & out["weight_pct"].notna()).sum())
    carried = int(out["weight_source_year"].notna().sum())
    never = int(out["weight_pct"].isna().sum())
    print(f"{len(out)} (bank, iso3, year) member-rows -> {args.output}")
    print(f"  {real:6} real (own-year) weights")
    print(f"  {carried:6} carried forward (LOCF)")
    print(f"  {never:6} never had any weight data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
