"""Add one-year-lagged versions of the UCDP conflict and banking-crisis
columns onto data/output/mdb_panel_with_controls.csv: `ucdp_armed_
conflict_t1`, `ucdp_war_t1`, `ucdp_conflict_intensity_t1`, `banking_
crisis_t1`. The contemporaneous versions are already on the panel via the
normal country-year outer-merge in build_control_variables.py/merge_
control_panel.py -- this script only adds the lag, reading data/extracted/
control_variables.csv as the source (it already has everything needed; no
separate "build" stage for the lag itself).

Same `_year_m1` shift pattern as merge_unga_iv.py: the source's `year` is
shifted back by one and left-joined onto the panel's own `iso3` + `year` --
so a focal observation in year Y picks up the source's Y-1 row. No LOCF
anywhere in this file; a missing prior year leaves the `_t1` columns blank,
never guessed -- including years outside either source's own documented
coverage window (2026, and years before MIN_YEAR), which are blank in
control_variables.csv itself and so stay blank here too.

Overwrites data/output/mdb_panel_with_controls.csv in place (both its usual
dual-write targets) -- a small additive step, doesn't touch merge_control_
panel.py's own tested merge logic at all.

Usage:  python3 scripts/merge_conflict_crisis_lags.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, OUTPUT_DIR, REPO  # noqa: E402

PANEL_CSV = OUTPUT_DIR / "mdb_panel_with_controls.csv"
CONTROLS_CSV = EXTRACTED_DIR / "control_variables.csv"
CONTROL_VARS_REPO = REPO.parent / "Control variables"
DEFAULT_TARGETS = [PANEL_CSV, CONTROL_VARS_REPO / "output" / "mdb_panel_with_controls.csv"]

LAGGED_SOURCE_COLUMNS = ["ucdp_armed_conflict", "ucdp_war", "ucdp_conflict_intensity", "banking_crisis"]
NEW_COLUMNS = [f"{c}_t1" for c in LAGGED_SOURCE_COLUMNS]


def merge(panel: pd.DataFrame, controls: pd.DataFrame) -> pd.DataFrame:
    """Split out from main() so tests can exercise it directly on small
    fixtures, same pattern as merge_unga_iv.py/merge_other_mdb_lending.py."""

    present = [c for c in LAGGED_SOURCE_COLUMNS if c in controls.columns]
    lagged = controls[["iso3", "year", *present]].copy()
    lagged["year"] = lagged["year"] + 1  # this row's year becomes the *next* year's t-1 reference
    lagged = lagged.rename(columns={c: f"{c}_t1" for c in present})

    merged = panel.merge(lagged, on=["iso3", "year"], how="left")
    for col in NEW_COLUMNS:
        if col not in merged.columns:
            merged[col] = pd.NA  # source didn't have this column at all -- stays blank, not an error

    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--controls", type=Path, default=CONTROLS_CSV)
    parser.add_argument("--output", type=Path, action="append", dest="outputs",
                         help="Repeatable; defaults to both of this project's usual output locations.")
    args = parser.parse_args(argv)

    for path, hint in (
        (args.panel, "make controls"),
        (args.controls, "python3 scripts/build_control_variables.py"),
    ):
        if not path.is_file():
            print(f"error: {path} does not exist. Run: {hint}", file=sys.stderr)
            return 2

    panel = pd.read_csv(args.panel, low_memory=False)
    controls = pd.read_csv(args.controls)

    before = len(panel)
    merged = merge(panel, controls)
    assert len(merged) == before, f"row count changed by the join: {before} -> {len(merged)} (should never happen)"

    targets = args.outputs if args.outputs else DEFAULT_TARGETS
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(target, index=False)

    print(f"{len(merged)} rows, +{len(NEW_COLUMNS)} conflict/crisis lag columns -> "
          f"{', '.join(str(t.relative_to(REPO)) if t.is_relative_to(REPO) else str(t) for t in targets)}")
    for col in NEW_COLUMNS:
        non_null = int(merged[col].notna().sum())
        print(f"  {col:32} {non_null:6} / {len(merged)} non-null")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
