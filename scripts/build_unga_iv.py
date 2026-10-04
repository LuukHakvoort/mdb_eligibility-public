"""Build the bank-year UNGA reference points and the individual large-
shareholder distances -- the core computation behind the UNGA independent
variables (scripts/merge_unga_iv.py joins these onto the panel).

Four constructions, each a **distance** between a recipient's own UNGA
ideal point and a reference point (docs/coding_decisions.md has the full
account of every judgement call below):

1. **Hegemonic**: the bank's single largest shareholder that year (by
   `weight_pct`; ties broken alphabetically by iso3). A structural fact
   about the bank, computed even if that shareholder happens to have no
   UNGA data that year (in which case the distance itself is null, but
   `largest_shareholder_iso3` is still reported).
2. **G7** / **G10**: vote-power-weighted average ideal point of whichever
   fixed-list G7 (`G7_ISO3`) or G10 (`G10_ISO3`) members are shareholders
   that year.
3. **Large shareholders ("ls")**: vote-power-weighted average ideal point
   of shareholders holding more than `LARGE_SHAREHOLDER_THRESHOLD_PCT`
   (5%) of the bank's decision-making weight that year.
4. **Coalition**: vote-power-weighted average ideal point across *all* of
   the bank's shareholders that year.

For 2-4, weights are **renormalized to sum to 1** among whichever
shareholders in that pool actually have both a weight and UNGA data that
year (a shareholder with a weight but no UNGA coverage is skipped, not
silently treated as zero-weight -- the user's own confirmed choices this
session). The **recipient is never excluded** from a pool merely for being
a shareholder of its own bank (also the user's own choice) -- these
reference points are computed purely per (bank, year), with no notion of
"the recipient" at all, which is what makes that inclusion automatic rather
than a special case.

**Two outputs:**

- `data/extracted/unga_bank_year_reference_points.csv` -- one row per
  (bank, year), the four reference points (`hegemonic_ip_*`, `g7_ip_*`,
  `g10_ip_*`, `ls_ip_*`, `coalition_ip_*`, each for both `idealpoint_all`
  and `idealpoint_fp`) plus supporting counts/identities. This is what
  `merge_unga_iv.py` joins onto the panel at both `t` and `t-1`.
- `data/extracted/unga_large_shareholder_distances.csv` -- the individual-
  shareholder companion file `merge_unga_iv.py` does *not* merge into the
  wide panel (a bank-year's qualifying >5% shareholders vary in number and
  identity, so they don't fit as a fixed set of wide columns). Long format:
  one row per (bank, recipient_iso3, year, lag, large_shareholder_iso3),
  for both `t` (lag's reference year = `year`) and `t1` (`year - 1`),
  covering every (bank, iso3, year) triple in `--panel`. A bank-year with
  zero qualifying large shareholders simply contributes no rows for that
  (bank, year, lag) -- consistent with `ls_n_shareholders` being 0 in the
  reference-points file, not a missing-data gap.

Usage:  python3 scripts/build_unga_iv.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, OUTPUT_DIR, REPO  # noqa: E402

WEIGHTS_CSV = EXTRACTED_DIR / "shareholder_weights.csv"
IDEAL_POINTS_CSV = EXTRACTED_DIR / "unga_ideal_points.csv"
PANEL_CSV = OUTPUT_DIR / "mdb_panel_with_controls.csv"
REFERENCE_OUTPUT = EXTRACTED_DIR / "unga_bank_year_reference_points.csv"
DISTANCES_OUTPUT = EXTRACTED_DIR / "unga_large_shareholder_distances.csv"

# Standard political G7. Standard financial "Group of Ten" -- 11 members
# despite the name (Switzerland joined as an associate in 1964); the usual
# IMF/BIS grouping cited in this literature. Fixed lists, per the user's
# own confirmed choice this session (not redefined per-bank).
G7_ISO3 = frozenset({"CAN", "FRA", "DEU", "ITA", "JPN", "GBR", "USA"})
G10_ISO3 = frozenset({"BEL", "CAN", "FRA", "DEU", "ITA", "JPN", "NLD", "SWE", "CHE", "GBR", "USA"})

# A named, documented, easily-adjustable threshold for "large shareholder" --
# the user's own choice this session (5%), not a standard blocking-minority
# figure (those tend to run 15-25%). Change this one constant to change the
# threshold everywhere it's used.
LARGE_SHAREHOLDER_THRESHOLD_PCT = 5.0

REFERENCE_COLUMNS = [
    "bank", "year",
    "largest_shareholder_iso3", "largest_shareholder_weight_pct", "largest_shareholder_weight_basis",
    "hegemonic_ip_all", "hegemonic_ip_fp",
    "g7_ip_all", "g7_n_shareholders_all", "g7_ip_fp", "g7_n_shareholders_fp",
    "g10_ip_all", "g10_n_shareholders_all", "g10_ip_fp", "g10_n_shareholders_fp",
    "ls_ip_all", "ls_n_shareholders_all", "ls_ip_fp", "ls_n_shareholders_fp",
    "coalition_ip_all", "coalition_n_shareholders_all", "coalition_ip_fp", "coalition_n_shareholders_fp",
]
DISTANCES_COLUMNS = [
    "bank", "recipient_iso3", "year", "lag",
    "large_shareholder_iso3", "large_shareholder_weight_pct",
    "distance_all", "distance_fp",
]


def _weighted_pool(wip: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Renormalized vote-power-weighted average ideal point per (bank, year),
    over whichever rows of `wip` (weight, both ideal-point columns possibly
    null) the caller has already filtered to one pool.

    `idealpoint_all` and `idealpoint_fp` are filtered and renormalized
    **independently** -- a shareholder present for one measure but not the
    other (routine since `idealpoint_fp` now reaches 2025 via `build_unga_
    ideal_points.py`'s FP extension while `idealpoint_all` never does)
    still contributes to whichever measure it actually has. Sharing one
    renormalization across both measures would silently under-weight the
    true average whenever the two measures' coverage differs -- pandas'
    `.sum()` skips a NaN contribution but still counts that shareholder's
    weight in the denominator, which for a pool with zero `idealpoint_all`
    coverage (every 2025 row) previously produced a spurious `0.0` instead
    of a correct null. `..._n_shareholders_all`/`_fp` are therefore two
    separate counts, not one shared count.
    """

    columns = ["bank", "year", f"{prefix}_ip_all", f"{prefix}_n_shareholders_all",
               f"{prefix}_ip_fp", f"{prefix}_n_shareholders_fp"]
    if wip.empty:
        return pd.DataFrame(columns=columns)

    per_measure = []
    for measure in ("all", "fp"):
        sub = wip[wip[f"idealpoint_{measure}"].notna()]
        ip_col, n_col = f"{prefix}_ip_{measure}", f"{prefix}_n_shareholders_{measure}"
        if sub.empty:
            per_measure.append(pd.DataFrame(columns=["bank", "year", ip_col, n_col]))
            continue
        total_w = sub.groupby(["bank", "year"])["weight_pct"].transform("sum")
        contrib = (sub["weight_pct"] / total_w) * sub[f"idealpoint_{measure}"]
        agg = sub.assign(_contrib=contrib).groupby(["bank", "year"], as_index=False).agg(
            **{ip_col: ("_contrib", "sum"), n_col: ("shareholder_iso3", "count")}
        )
        per_measure.append(agg)

    return per_measure[0].merge(per_measure[1], on=["bank", "year"], how="outer")[columns]


def build_reference_points(weights: pd.DataFrame, ideal_points: pd.DataFrame) -> pd.DataFrame:
    """The four reference-point constructions, one row per (bank, year)."""

    if weights.empty:
        return pd.DataFrame(columns=REFERENCE_COLUMNS)

    valid = weights[weights["weight_pct"].notna()].copy()

    # --- Hegemonic: largest shareholder by raw weight, alphabetical tie-break.
    ranked = valid.sort_values(["bank", "year", "weight_pct", "iso3"], ascending=[True, True, False, True])
    largest = ranked.groupby(["bank", "year"], as_index=False).first()[
        ["bank", "year", "iso3", "weight_pct", "weight_basis"]
    ].rename(columns={
        "iso3": "largest_shareholder_iso3",
        "weight_pct": "largest_shareholder_weight_pct",
        "weight_basis": "largest_shareholder_weight_basis",
    })
    ip_for_largest = ideal_points.rename(columns={
        "iso3": "largest_shareholder_iso3", "idealpoint_all": "hegemonic_ip_all", "idealpoint_fp": "hegemonic_ip_fp",
    })[["largest_shareholder_iso3", "year", "hegemonic_ip_all", "hegemonic_ip_fp"]]
    largest = largest.merge(ip_for_largest, on=["largest_shareholder_iso3", "year"], how="left")

    # --- The three weighted-average pools share one weight+ideal-point join.
    wip = valid.merge(
        ideal_points.rename(columns={"iso3": "shareholder_iso3"}),
        left_on=["iso3", "year"], right_on=["shareholder_iso3", "year"], how="inner",
    )

    coalition = _weighted_pool(wip, "coalition")
    g7 = _weighted_pool(wip[wip["shareholder_iso3"].isin(G7_ISO3)], "g7")
    g10 = _weighted_pool(wip[wip["shareholder_iso3"].isin(G10_ISO3)], "g10")
    ls = _weighted_pool(wip[wip["weight_pct"] > LARGE_SHAREHOLDER_THRESHOLD_PCT], "ls")

    out = largest
    for part in (coalition, g7, g10, ls):
        out = out.merge(part, on=["bank", "year"], how="outer")

    return out.sort_values(["bank", "year"])[REFERENCE_COLUMNS].reset_index(drop=True)


def build_large_shareholder_distances(
    weights: pd.DataFrame, ideal_points: pd.DataFrame, panel_grid: pd.DataFrame,
) -> pd.DataFrame:
    """Individual distance to every qualifying (>5%) large shareholder, for
    every (bank, recipient_iso3, year) in `panel_grid`, at both t and t-1."""

    if weights.empty or panel_grid.empty:
        return pd.DataFrame(columns=DISTANCES_COLUMNS)

    valid = weights[weights["weight_pct"].notna()]
    wip = valid.merge(
        ideal_points.rename(columns={"iso3": "shareholder_iso3"}),
        left_on=["iso3", "year"], right_on=["shareholder_iso3", "year"], how="inner",
    )
    ls_members = wip[wip["weight_pct"] > LARGE_SHAREHOLDER_THRESHOLD_PCT][
        ["bank", "year", "shareholder_iso3", "weight_pct", "idealpoint_all", "idealpoint_fp"]
    ].rename(columns={"year": "ref_year"})

    grid = panel_grid[["bank", "iso3", "year"]].drop_duplicates()
    t_frame = grid.assign(ref_year=grid["year"], lag="t")
    t1_frame = grid.assign(ref_year=grid["year"] - 1, lag="t1")
    recipient_grid = pd.concat([t_frame, t1_frame], ignore_index=True).rename(columns={"iso3": "recipient_iso3"})

    distances = recipient_grid.merge(ls_members, on=["bank", "ref_year"], how="inner")

    recipient_ip = ideal_points.rename(columns={
        "iso3": "recipient_iso3", "year": "ref_year",
        "idealpoint_all": "recipient_ip_all", "idealpoint_fp": "recipient_ip_fp",
    })
    distances = distances.merge(recipient_ip, on=["recipient_iso3", "ref_year"], how="left")

    distances["distance_all"] = (distances["recipient_ip_all"] - distances["idealpoint_all"]).abs()
    distances["distance_fp"] = (distances["recipient_ip_fp"] - distances["idealpoint_fp"]).abs()
    distances = distances.rename(columns={
        "shareholder_iso3": "large_shareholder_iso3", "weight_pct": "large_shareholder_weight_pct",
    })

    return distances.sort_values(["bank", "recipient_iso3", "year", "lag", "large_shareholder_iso3"])[
        DISTANCES_COLUMNS
    ].reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--weights", type=Path, default=WEIGHTS_CSV)
    parser.add_argument("--ideal-points", type=Path, default=IDEAL_POINTS_CSV)
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--reference-output", type=Path, default=REFERENCE_OUTPUT)
    parser.add_argument("--distances-output", type=Path, default=DISTANCES_OUTPUT)
    args = parser.parse_args(argv)

    for path, hint in (
        (args.weights, "python3 scripts/build_shareholder_weights.py"),
        (args.ideal_points, "python3 scripts/build_unga_ideal_points.py"),
        (args.panel, "make controls"),
    ):
        if not path.is_file():
            print(f"error: {path} does not exist. Run: {hint}", file=sys.stderr)
            return 2

    weights = pd.read_csv(args.weights)
    ideal_points = pd.read_csv(args.ideal_points)
    panel = pd.read_csv(args.panel, usecols=["bank", "iso3", "year"])

    reference = build_reference_points(weights, ideal_points)
    distances = build_large_shareholder_distances(weights, ideal_points, panel)

    args.reference_output.parent.mkdir(parents=True, exist_ok=True)
    reference.to_csv(args.reference_output, index=False)
    args.distances_output.parent.mkdir(parents=True, exist_ok=True)
    distances.to_csv(args.distances_output, index=False)

    print(f"{len(reference)} (bank, year) reference-point rows -> {args.reference_output}")
    for col in ("hegemonic_ip_all", "g7_ip_all", "g10_ip_all", "ls_ip_all", "coalition_ip_all"):
        non_null = int(reference[col].notna().sum())
        print(f"  {col:18} {non_null:6} / {len(reference)} non-null")
    print(f"{len(distances)} individual large-shareholder distance rows -> {args.distances_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
