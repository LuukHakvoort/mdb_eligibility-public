"""Recreate "MDB positions within the UNGA country distribution" -- the
user's existing Stata figure, rebuilt from this repo's own pipeline output
instead of the older, now-superseded static data it was originally drawn
from.

Two things overlaid on one chart:

- **The global country distribution**, per year: the light band is the
  10th-90th percentile of every country's own ideal point that year
  (`data/extracted/unga_ideal_points.csv`), the dark band the 25th-75th,
  and the dashed line the median. Bands are percentiles of the raw
  cross-country distribution, not a confidence interval around anything.
- **Each MDB's own trajectory**: `coalition_ip_*` from `data/extracted/
  unga_bank_year_reference_points.csv` -- the vote-power-weighted average
  ideal point across *all* of that bank's shareholders that year (the
  "shareholder-weighted bank position"; see `scripts/build_unga_iv.py` for
  the weight-fallback/LOCF/renormalization rules already baked into this
  column -- nothing new is computed here). A bank's line starts the first
  year it has that data (e.g. AIIB 2016, NDB 2015).

**Two separate charts, one per measure** -- the user's explicit request,
after asking what `idealpointall`/`idealpointfp` actually mean:

- `unga_positions_chart.png` (the default/primary one) uses **idealpointfp**
  only, through **2025** (`data/extracted/unga_ideal_points.csv` extends
  `idealpoint_fp` to 2025 via a companion release -- see `docs/coding_
  decisions.md`, 2026-09-28 -- while `idealpoint_all` never reaches past
  2024 in this bundle at all).
- `unga_positions_chart_idealpointall.png` uses **idealpointall** only,
  through 2024 (the latest year this bundle has it).
Each chart's own footnote states explicitly which measure it uses, so
the two are never mistaken for each other.

**Uses matplotlib** (`pip install matplotlib`) -- a new, scoped dependency
for this one script, the user's own choice over this repo's usual
dependency-free hand-written-SVG convention (`scripts/report_
panel_balance.py`), for closer visual fidelity to the original Stata plot.

Writes both PNGs plus the underlying per-year numbers behind each (bands,
median, each bank's position) as a `..._data.csv` alongside it, for
transparency/reuse. Default output directory: `../Final dataset/output/`.

Usage:  python3 scripts/plot_unga_positions.py
        python3 scripts/plot_unga_positions.py --measure all   # just one chart
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: this script never needs an interactive window
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import CANONICAL_BANKS, EXTRACTED_DIR, MIN_YEAR, REPO  # noqa: E402

IDEAL_POINTS_CSV = EXTRACTED_DIR / "unga_ideal_points.csv"
REFERENCE_CSV = EXTRACTED_DIR / "unga_bank_year_reference_points.csv"

FINAL_DATASET_REPO = REPO.parent / "Final dataset"
OUTPUT_DIR = FINAL_DATASET_REPO / "output"

PERCENTILES = {"p10": 0.10, "p25": 0.25, "p50": 0.50, "p75": 0.75, "p90": 0.90}

# One entry per measure: which raw columns to read, how to label the chart,
# the explicit note the user asked for (which measure is/isn't used), and
# where each chart's outputs go by default.
MEASURES: dict[str, dict] = {
    "fp": {
        "ideal_point_col": "idealpoint_fp", "coalition_col": "coalition_ip_fp",
        "display_name": "idealpointfp", "other_name": "idealpointall",
        "ylabel": "Foreign-policy ideal point (idealpointfp)",
        "note": "Uses idealpointfp (final-passage votes only) -- not idealpointall. "
                "See unga_positions_chart_idealpointall.png for that measure.",
        "png": OUTPUT_DIR / "unga_positions_chart.png",
        "data_csv": OUTPUT_DIR / "unga_positions_chart_data.csv",
    },
    "all": {
        "ideal_point_col": "idealpoint_all", "coalition_col": "coalition_ip_all",
        "display_name": "idealpointall", "other_name": "idealpointfp",
        "ylabel": "All-votes ideal point (idealpointall)",
        "note": "Uses idealpointall (all votes, including paragraph/amendment votes) -- not idealpointfp. "
                "See unga_positions_chart.png for that measure.",
        "png": OUTPUT_DIR / "unga_positions_chart_idealpointall.png",
        "data_csv": OUTPUT_DIR / "unga_positions_chart_idealpointall_data.csv",
    },
}

# A fixed, documented bank -> color mapping, the user's own explicit request
# (2026-09-28) after the tab20 default proved hard to read: each color is
# traced to that bank's own real logo (downloaded from Wikimedia Commons/the
# bank's own site, dominant color measured by pixel analysis -- HSV-filtered
# for saturated, non-background pixels, not eyeballed), then adjusted in
# HSL (brightened/saturated, never re-hued) only as far as needed for two
# things: (1) two logos landing on nearly the same real color (e.g. AsDB's
# and IBRD's logos are both solid navy) get separated in lightness/hue so
# they're still distinguishable on a 14-line chart; (2) three explicit
# requirements -- IBRD and IDB read as a related pair (IDB's own Commons
# logo is monochrome black ink, so there is no real color of its own to
# defer to), BADEA and IsDB read as a related green pair (both logos really
# do use green, independently), and AIIB is red (its actual logo color,
# turns out -- a dark maroon/brick red in both current logo variants,
# brightened here for visibility, not an override). Sourcing notes and the
# measured hex per bank are in docs/coding_decisions.md, 2026-09-28.
BANK_COLORS: dict[str, str] = {
    "IBRD": "#0F388A",   # World Bank Group logo: navy blue (measured #002244)
    "IDA": "#06ADEA",    # IDA logo's own "International Development Association" cyan accent
    "AfDB": "#00A383",   # official brand green, Pantone 3405C (#00A86A)
    "AsDB": "#1E808F",   # logo is solid navy, nearly identical to IBRD's -- shifted to teal to separate
    "IDB": "#2A73C6",    # logo is monochrome ink; assigned a lighter blue paired with IBRD, per request
    "EBRD": "#734DCB",   # logo blue shifted toward violet -- otherwise indistinguishable from EIB/CABEI
    "EIB": "#0B2EDA",    # EU flag blue from the logo, brightened
    "IsDB": "#3CB45A",   # green half of the logo's gradient globe, paired with BADEA
    "CAF": "#68B234",    # logo's green half (the other half is blue, already well represented)
    "CDB": "#D89E18",    # logo's gold ring -- the blue disc is the pixel-majority color but that hue is already crowded
    "AIIB": "#C91D2B",   # logo's own maroon/brick red, brightened -- "AIIB should be red," and it already is
    "BADEA": "#298E4B",  # logo's green globe icon, paired with IsDB
    "NDB": "#AEB82E",    # logo's yellow-green swirl (ndb.int's own site logo, not a generic placeholder)
    "CABEI": "#4CBAF0",  # logo's own blue (#0353C2), lightened to separate from IBRD/IDB/EIB's darker blues
}


def build_band_data(ideal_points: pd.DataFrame, measure: str = "fp") -> pd.DataFrame:
    """Per-year percentile bands + median of the given measure
    (`idealpoint_fp` or `idealpoint_all`) across every country with data
    that year. Split out from main() so it's directly testable against a
    small in-memory frame.

    Restricted to this project's own study window (year >= MIN_YEAR, 2002):
    unga_ideal_points.csv itself keeps 2000-2001 too (build_unga_ideal_
    points.py's own MIN_SOURCE_YEAR, kept only to sidestep a pre-1990 Yemen
    duplicate-key edge case -- see that script's docstring), but those two
    years aren't part of this study and would otherwise pull the chart's
    x-axis two years further left than intended.
    """

    col = MEASURES[measure]["ideal_point_col"]
    ideal_points = ideal_points[ideal_points["year"] >= MIN_YEAR]
    grouped = ideal_points.groupby("year")[col]
    out = pd.DataFrame({name: grouped.quantile(q) for name, q in PERCENTILES.items()})
    out = out.reset_index()
    # A year with a row for every country but zero real values for this
    # measure (e.g. idealpoint_all is entirely null for 2024 in the source
    # .dta itself -- confirmed directly, not a processing artifact: Voeten's
    # all-votes measure lags the final-passage one even within one release)
    # still shows up as a groupby key, with every percentile NaN. Drop it,
    # rather than letting a phantom trailing year widen the chart's x-axis.
    return out.dropna(subset=["p50"])


def build_bank_series(reference: pd.DataFrame, measure: str = "fp") -> pd.DataFrame:
    """One row per (bank, year) with a non-null coalition position for the
    given measure -- a bank's series simply doesn't exist before it was
    founded or after the source UNGA data stops, rather than plotting a
    misleading flat/zero line. Renamed to a measure-agnostic `coalition_ip`
    column so the rest of this module doesn't need to know which measure
    it's holding."""

    col = MEASURES[measure]["coalition_col"]
    out = reference[["bank", "year", col]].rename(columns={col: "coalition_ip"}).copy()
    return out[out["coalition_ip"].notna()].sort_values(["bank", "year"])


def build_chart_data(ideal_points: pd.DataFrame, reference: pd.DataFrame, measure: str = "fp") -> pd.DataFrame:
    """Wide (year x bank + bands) table -- the CSV written alongside the PNG."""

    bands = build_band_data(ideal_points, measure)
    bank_series = build_bank_series(reference, measure)
    wide = bank_series.pivot(index="year", columns="bank", values="coalition_ip").reset_index()
    return bands.merge(wide, on="year", how="outer").sort_values("year")


def render(bands: pd.DataFrame, bank_series: pd.DataFrame, measure: str = "fp") -> plt.Figure:
    spec = MEASURES[measure]
    fig, ax = plt.subplots(figsize=(11, 7))

    ax.fill_between(bands["year"], bands["p10"], bands["p90"], color="#d9d9d9", label="80 percentile band")
    ax.fill_between(bands["year"], bands["p25"], bands["p75"], color="#bcbcbc", label="50 percentile band")
    ax.plot(bands["year"], bands["p50"], color="black", linestyle="--", linewidth=1.5,
            label="Median UNGA ideal point estimate")

    for bank in CANONICAL_BANKS:
        series = bank_series[bank_series["bank"] == bank]
        if series.empty:
            continue
        ax.plot(series["year"], series["coalition_ip"], color=BANK_COLORS[bank],
                 linewidth=1.7, label=bank)

    year_min, year_max = int(bands["year"].min()), int(bands["year"].max())
    ax.set_title("MDB positions within the UNGA country distribution", fontsize=14, pad=28)
    ax.text(0.5, 1.02, f"{spec['ylabel']}, {year_min}-{year_max}", transform=ax.transAxes,
            ha="center", fontsize=10, color="#555555")
    ax.set_xlabel("Year")
    ax.set_ylabel(spec["ylabel"])
    ax.set_xlim(year_min, year_max)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, steps=[1, 2, 5, 10]))
    ax.grid(True, axis="y", color="#e6e6e6", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.14),
              ncol=6, frameon=False, fontsize=8, title="MDB trajectories")

    fig.text(0.01, 0.02,
              "Country distribution: light gray = P10-P90, dark gray = P25-P75; dashed black = median.\n"
              "Bank lines are each bank's shareholder-weighted (vote-power, all shareholders) UNGA position. "
              "Bands show percentiles, not confidence intervals.\n"
              f"{spec['note']}",
              fontsize=7, color="#777777")
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    return fig


def build_and_render(ideal_points: pd.DataFrame, reference: pd.DataFrame, measure: str) -> tuple[pd.DataFrame, plt.Figure]:
    """One measure's full chart-data table + rendered figure."""

    bands = build_band_data(ideal_points, measure)
    bank_series = build_bank_series(reference, measure)
    chart_data = build_chart_data(ideal_points, reference, measure)
    fig = render(bands, bank_series, measure)
    return chart_data, fig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ideal-points", type=Path, default=IDEAL_POINTS_CSV)
    parser.add_argument("--reference", type=Path, default=REFERENCE_CSV)
    parser.add_argument("--measure", choices=["fp", "all"], default=None,
                         help="Build just one measure's chart. Default: build both.")
    parser.add_argument("--png", type=Path, default=None,
                         help="Only valid together with --measure; overrides that measure's default PNG path.")
    parser.add_argument("--data-csv", type=Path, default=None,
                         help="Only valid together with --measure; overrides that measure's default data CSV path.")
    args = parser.parse_args(argv)

    if (args.png or args.data_csv) and not args.measure:
        print("error: --png/--data-csv require --measure (fp or all)", file=sys.stderr)
        return 2

    for path, hint in (
        (args.ideal_points, "python3 scripts/build_unga_ideal_points.py"),
        (args.reference, "python3 scripts/build_unga_iv.py"),
    ):
        if not path.is_file():
            print(f"error: {path} does not exist. Run: {hint}", file=sys.stderr)
            return 2

    ideal_points = pd.read_csv(args.ideal_points)
    reference = pd.read_csv(args.reference)

    measures = [args.measure] if args.measure else list(MEASURES)
    for measure in measures:
        spec = MEASURES[measure]
        png = args.png if args.measure else spec["png"]
        data_csv = args.data_csv if args.measure else spec["data_csv"]

        chart_data, fig = build_and_render(ideal_points, reference, measure)

        data_csv.parent.mkdir(parents=True, exist_ok=True)
        chart_data.to_csv(data_csv, index=False)

        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png, dpi=200)
        plt.close(fig)

        bank_series = build_bank_series(reference, measure)
        banks_plotted = sorted(bank_series["bank"].unique())
        bands = build_band_data(ideal_points, measure)
        print(f"[{spec['display_name']}] {len(bands)} years of country-distribution bands, "
              f"{len(banks_plotted)} bank trajectories ({', '.join(banks_plotted)}) -> {png}")
        print(f"-> {data_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
