"""Build the enriched estimation panel: data/output/mdb_panel.csv (the
eligible-dyad-year panel, `make panel`) left-joined with
data/extracted/control_variables.csv (country-year controls, `scripts/
build_control_variables.py`, joined on iso3+year -- broadcast across every
bank sharing that country-year) and data/extracted/project_breakdown.csv
(bank-country-year sector/instrument/sovereign breakdown, `scripts/
build_project_breakdown.py`, joined on bank+iso3+year).

Written to **both** `data/output/mdb_panel_with_controls.csv` (git-tracked,
so the build is versioned like every other output in this project) and
`../Control variables/output/mdb_panel_with_controls.csv` (the user's own
requested location, 2026-09-27) -- one build step, two copies, never
diverging.

A left join, never a filter: the row count always equals `mdb_panel.csv`'s
own row count exactly. A blank control-variable cell means that source had
no value for that country-year (see `build_control_variables.py`'s own
per-source coverage notes) -- never guessed, never interpolated.

Usage:  python3 scripts/merge_control_panel.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, OUTPUT_DIR, REPO  # noqa: E402

PANEL_CSV = OUTPUT_DIR / "mdb_panel.csv"
CONTROLS_CSV = EXTRACTED_DIR / "control_variables.csv"
BREAKDOWN_CSV = EXTRACTED_DIR / "project_breakdown.csv"

CONTROL_VARS_REPO = REPO.parent / "Control variables"
DEFAULT_TARGETS = [OUTPUT_DIR / "mdb_panel_with_controls.csv", CONTROL_VARS_REPO / "output" / "mdb_panel_with_controls.csv"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--controls", type=Path, default=CONTROLS_CSV)
    parser.add_argument("--breakdown", type=Path, default=BREAKDOWN_CSV)
    parser.add_argument("--output", type=Path, action="append", dest="outputs",
                         help="Repeatable; defaults to both of this project's usual output locations.")
    args = parser.parse_args(argv)
    targets = args.outputs if args.outputs else DEFAULT_TARGETS

    for path in (args.panel, args.controls, args.breakdown):
        if not path.is_file():
            print(f"error: {path} does not exist. Run: make panel; python3 scripts/build_control_variables.py; "
                  f"python3 scripts/build_project_breakdown.py", file=sys.stderr)
            return 2

    panel = pd.read_csv(args.panel)
    controls = pd.read_csv(args.controls)
    breakdown = pd.read_csv(args.breakdown)

    before = len(panel)
    merged = panel.merge(controls, on=["iso3", "year"], how="left")
    merged = merged.merge(breakdown, on=["bank", "iso3", "year"], how="left")
    assert len(merged) == before, f"row count changed by the join: {before} -> {len(merged)} (should never happen)"

    # Project-breakdown columns are counts/amounts that are genuinely zero
    # when a dyad-year has no lending at all, not missing -- fill only those,
    # never the control-variable columns (a blank control stays blank).
    breakdown_cols = [c for c in breakdown.columns if c not in ("bank", "iso3", "year")]
    zero_filled = merged[breakdown_cols].fillna(0)
    merged[breakdown_cols] = zero_filled.where(merged["any_lending"] == 0, merged[breakdown_cols])

    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(target, index=False)

    print(f"{len(merged)} rows (unchanged from mdb_panel.csv's {before}), {len(merged.columns)} columns total "
          f"({len(controls.columns) - 2} control variables, {len(breakdown.columns) - 3} project-breakdown columns)")
    for target in targets:
        print(f"-> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
