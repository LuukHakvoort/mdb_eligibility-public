"""Build data/output/mdb_panel_final.csv: data/output/mdb_panel_with_controls
.csv left-joined with the UNGA independent variables (scripts/
build_unga_iv.py's `unga_bank_year_reference_points.csv`, plus each
recipient's own ideal point from `unga_ideal_points.csv`), at both `t`
(=`year`) and `t1` (=`year - 1`).

Written to **both** `data/output/mdb_panel_final.csv` and `../Final
dataset/output/mdb_panel_final.csv` -- a new file, not an overwrite of
`mdb_panel_with_controls.csv`, same dual-write pattern as `merge_control_
panel.py`. The individual-shareholder companion file
(`unga_large_shareholder_distances.csv`) is copied alongside, unmodified --
it is deliberately not merged into this wide panel (see build_unga_iv.py's
docstring).

For each of the five reference points (hegemonic, g7, g10, ls, coalition),
each of the two ideal-point measures (all, fp), and each lag (t, t1): a
distance column `unga_<pool>_dist_<measure>_<lag>` = `|recipient ideal
point - reference ideal point|`. **Never zero-filled** -- unlike the
project-breakdown columns in `merge_control_panel.py`, a missing UNGA
distance is never a real, countable zero, so a missing operand on either
side leaves the distance blank, full stop; there is no fillna step in this
script at all, by design.

A left join, never a filter: the row count always equals `mdb_panel_with_
controls.csv`'s own row count exactly.

Usage:  python3 scripts/merge_unga_iv.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, OUTPUT_DIR, REPO  # noqa: E402

PANEL_CSV = OUTPUT_DIR / "mdb_panel_with_controls.csv"
REFERENCE_CSV = EXTRACTED_DIR / "unga_bank_year_reference_points.csv"
IDEAL_POINTS_CSV = EXTRACTED_DIR / "unga_ideal_points.csv"
DISTANCES_CSV = EXTRACTED_DIR / "unga_large_shareholder_distances.csv"

FINAL_DATASET_REPO = REPO.parent / "Final dataset"
DEFAULT_TARGETS = [OUTPUT_DIR / "mdb_panel_final.csv", FINAL_DATASET_REPO / "output" / "mdb_panel_final.csv"]
DEFAULT_DISTANCES_TARGETS = [FINAL_DATASET_REPO / "output" / "unga_large_shareholder_distances.csv"]

POOLS = ["hegemonic", "g7", "g10", "ls", "coalition"]
MEASURES = ["all", "fp"]


def _reference_pool_columns(reference: pd.DataFrame) -> list[str]:
    return [c for c in reference.columns if c not in ("bank", "year")]


def merge(panel: pd.DataFrame, reference: pd.DataFrame, ideal_points: pd.DataFrame) -> pd.DataFrame:
    merged = panel.copy()
    before = len(merged)

    # Recipient's own ideal point, at t and t-1.
    ip_t = ideal_points.rename(columns={
        "idealpoint_all": "unga_recipient_ip_all_t", "idealpoint_fp": "unga_recipient_ip_fp_t",
    })
    merged = merged.merge(ip_t[["iso3", "year", "unga_recipient_ip_all_t", "unga_recipient_ip_fp_t"]],
                           on=["iso3", "year"], how="left")

    merged["_year_m1"] = merged["year"] - 1
    ip_t1 = ideal_points.rename(columns={
        "year": "_year_m1", "idealpoint_all": "unga_recipient_ip_all_t1", "idealpoint_fp": "unga_recipient_ip_fp_t1",
    })
    merged = merged.merge(ip_t1[["iso3", "_year_m1", "unga_recipient_ip_all_t1", "unga_recipient_ip_fp_t1"]],
                           on=["iso3", "_year_m1"], how="left")

    # Bank-year reference points, at t and t-1.
    pool_cols = _reference_pool_columns(reference)
    ref_t = reference.rename(columns={c: f"unga_{c}_t" for c in pool_cols})
    merged = merged.merge(ref_t, on=["bank", "year"], how="left")

    ref_t1 = reference.rename(columns={"year": "_year_m1", **{c: f"unga_{c}_t1" for c in pool_cols}})
    merged = merged.merge(ref_t1, on=["bank", "_year_m1"], how="left")
    merged = merged.drop(columns=["_year_m1"])

    assert len(merged) == before, f"row count changed by the join: {before} -> {len(merged)} (should never happen)"

    # Distance columns: never zero-filled (see module docstring) -- no
    # fillna anywhere in this function.
    for lag in ("t", "t1"):
        for pool in POOLS:
            for measure in MEASURES:
                ref_col = f"unga_{pool}_ip_{measure}_{lag}"
                recip_col = f"unga_recipient_ip_{measure}_{lag}"
                dist_col = f"unga_{pool}_dist_{measure}_{lag}"
                merged[dist_col] = (merged[recip_col] - merged[ref_col]).abs()

    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--reference", type=Path, default=REFERENCE_CSV)
    parser.add_argument("--ideal-points", type=Path, default=IDEAL_POINTS_CSV)
    parser.add_argument("--distances", type=Path, default=DISTANCES_CSV)
    parser.add_argument("--output", type=Path, action="append", dest="outputs",
                         help="Repeatable; defaults to both of this project's usual output locations.")
    parser.add_argument("--distances-output", type=Path, action="append", dest="distances_outputs",
                         help="Repeatable; where to copy the individual-shareholder companion file.")
    args = parser.parse_args(argv)
    targets = args.outputs if args.outputs else DEFAULT_TARGETS
    distances_targets = args.distances_outputs if args.distances_outputs else DEFAULT_DISTANCES_TARGETS

    for path, hint in (
        (args.panel, "make controls"),
        (args.reference, "python3 scripts/build_unga_iv.py"),
        (args.ideal_points, "python3 scripts/build_unga_ideal_points.py"),
        (args.distances, "python3 scripts/build_unga_iv.py"),
    ):
        if not path.is_file():
            print(f"error: {path} does not exist. Run: {hint}", file=sys.stderr)
            return 2

    panel = pd.read_csv(args.panel, low_memory=False)
    reference = pd.read_csv(args.reference)
    ideal_points = pd.read_csv(args.ideal_points)
    before = len(panel)

    merged = merge(panel, reference, ideal_points)

    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(target, index=False)

    for target in distances_targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.distances, target)

    new_cols = len(merged.columns) - len(panel.columns)
    print(f"{len(merged)} rows (unchanged from mdb_panel_with_controls.csv's {before}), "
          f"{len(merged.columns)} columns total ({new_cols} new UNGA columns)")
    for target in targets:
        print(f"-> {target}")
    for target in distances_targets:
        print(f"-> {target} (individual large-shareholder distances, unmodified copy)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
