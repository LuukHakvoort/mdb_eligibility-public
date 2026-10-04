"""Merge data/extracted/other_mdb_lending.csv onto data/output/mdb_panel_
with_controls.csv as a one-year lag: "other MDBs' lending in year t-1
predicts the focal bank's lending in year t" (the H4 instrument's own
framing, user's spec 2026-09-30). Doesn't touch merge_control_panel.py's
own tested merge logic -- this is a small, additive step that overwrites
mdb_panel_with_controls.csv in place, adding columns only.

Same `_year_m1` lag-shift pattern as merge_unga_iv.py: the source table's
`year` is shifted forward by one, then left-joined onto the panel's own
`year` on `["bank", "iso3", "year"]` -- so a focal observation in year Y
picks up the source table's Y-1 row. No LOCF anywhere in this file; a
missing prior year leaves the `_t1` columns blank, never guessed.

`other_mdb_usd_t1` is the `other_mdb_usd_available` total (the user's own
name for it) -- **use this one in regressions**. `other_mdb_usd_strict_t1`
is the robustness-check companion (blank whenever a pool component's own
USD figure was itself a genuine data gap, never when the pool was
legitimately empty). `other_mdb_usd_millions_t1`/`ln1p_other_mdb_usd_t1`
are convenience transforms of `other_mdb_usd_t1`, not of the strict total.

Usage:  python3 scripts/merge_other_mdb_lending.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, OUTPUT_DIR, REPO  # noqa: E402

PANEL_CSV = OUTPUT_DIR / "mdb_panel_with_controls.csv"
OTHER_MDB_CSV = EXTRACTED_DIR / "other_mdb_lending.csv"
CONTROL_VARS_REPO = REPO.parent / "Control variables"
DEFAULT_TARGETS = [PANEL_CSV, CONTROL_VARS_REPO / "output" / "mdb_panel_with_controls.csv"]

NEW_COLUMNS = [
    "other_mdb_usd_t1", "other_mdb_usd_millions_t1", "ln1p_other_mdb_usd_t1",
    "other_mdb_usd_strict_t1", "other_mdb_n_eligible_t1", "other_mdb_n_missing_amount_t1",
    "other_mdb_ppp_t1", "other_mdb_ppp_millions_t1", "ln1p_other_mdb_ppp_t1",
    "other_mdb_ppp_strict_t1", "other_mdb_ppp_n_missing_amount_t1",
]


def merge(panel: pd.DataFrame, other_mdb: pd.DataFrame) -> pd.DataFrame:
    """Split out from main() so tests can exercise it directly on small
    fixtures, same pattern as merge_unga_iv.py."""

    lagged = other_mdb.copy()
    lagged["_year_p1"] = lagged["year"] + 1  # this row's year becomes the *next* year's t-1 reference
    lagged = lagged.rename(columns={
        "other_mdb_usd_available": "other_mdb_usd_t1",
        "other_mdb_usd_strict": "other_mdb_usd_strict_t1",
        "other_mdb_n_eligible": "other_mdb_n_eligible_t1",
        "other_mdb_n_missing_amount": "other_mdb_n_missing_amount_t1",
        "other_mdb_ppp_available": "other_mdb_ppp_t1",
        "other_mdb_ppp_strict": "other_mdb_ppp_strict_t1",
        "other_mdb_ppp_n_missing_amount": "other_mdb_ppp_n_missing_amount_t1",
    })[["bank", "iso3", "_year_p1", "other_mdb_usd_t1", "other_mdb_usd_strict_t1",
        "other_mdb_n_eligible_t1", "other_mdb_n_missing_amount_t1",
        "other_mdb_ppp_t1", "other_mdb_ppp_strict_t1", "other_mdb_ppp_n_missing_amount_t1"]]

    merged = panel.merge(
        lagged, left_on=["bank", "iso3", "year"], right_on=["bank", "iso3", "_year_p1"], how="left",
    ).drop(columns=["_year_p1"])

    merged["other_mdb_usd_millions_t1"] = merged["other_mdb_usd_t1"] / 1e6
    merged["ln1p_other_mdb_usd_t1"] = np.log1p(merged["other_mdb_usd_t1"])
    # PPP-adjusted version (2026-10-04): same transforms on the PPP total.
    merged["other_mdb_ppp_millions_t1"] = merged["other_mdb_ppp_t1"] / 1e6
    merged["ln1p_other_mdb_ppp_t1"] = np.log1p(merged["other_mdb_ppp_t1"])

    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--other-mdb", type=Path, default=OTHER_MDB_CSV)
    parser.add_argument("--output", type=Path, action="append", dest="outputs",
                         help="Repeatable; defaults to both of this project's usual output locations.")
    args = parser.parse_args(argv)

    for path, hint in ((args.panel, "make controls"), (args.other_mdb, "python3 scripts/build_other_mdb_lending.py")):
        if not path.is_file():
            print(f"error: {path} does not exist. Run: {hint}", file=sys.stderr)
            return 2

    panel = pd.read_csv(args.panel)
    other_mdb = pd.read_csv(args.other_mdb)

    before = len(panel)
    merged = merge(panel, other_mdb)
    assert len(merged) == before, f"row count changed by the join: {before} -> {len(merged)} (should never happen)"

    targets = args.outputs if args.outputs else DEFAULT_TARGETS
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(target, index=False)

    print(f"{len(merged)} rows, +{len(NEW_COLUMNS)} other-MDB-lending columns -> "
          f"{', '.join(str(t.relative_to(REPO)) if t.is_relative_to(REPO) else str(t) for t in targets)}")
    for col in NEW_COLUMNS:
        non_null = int(merged[col].notna().sum())
        print(f"  {col:32} {non_null:6} / {len(merged)} non-null")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
