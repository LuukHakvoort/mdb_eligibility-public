"""Build data/extracted/unga_ideal_points.csv: a clean country-year table of
Erik Voeten's UNGA ideal-point estimates, from ``../Final dataset/Datasets/
dataverse_files (1)/IdealpointsJuly2025.dta`` (not git-tracked, sibling to
this repo -- same pattern as ``../Control variables/``, see
docs/coding_decisions.md).

**Both idealpointall and idealpointfp are kept**, as parallel columns
(`idealpoint_all`, `idealpoint_fp`) -- the user's own choice, since the two
measures answer slightly different questions (all votes vs. final-passage
votes only) and both see use in the literature. `idealpointlegacy` (the
session-based predecessor measure) is dropped; this project uses the
year-based file throughout.

**`idealpoint_fp` is extended to 2025** via the companion
`IdealpointestimatesFP_2026FP.csv` release, which has one more year of
`idealpointfp` than the main `.dta` (through 2024). This is a deliberate,
explicit trade-off the user chose after being shown the alternative: that
CSV and the `.dta` are two different *releases* of Voeten's jointly-
estimated dynamic ideal-point model, not the same estimates in a different
shape -- highly correlated (r=0.9996 over the 1946-2024 overlap) but not
identical (median absolute difference ~0.012, ~0.024 for 2015-2024 alone),
so the spliced-in 2025 value is on a very slightly different vintage than
2002-2024. See docs/coding_decisions.md, 2026-09-28, for the full numbers
and for an earlier, wrong version of this same comparison that was
corrected before this extension was added.

**`idealpoint_all` still stops at 2024** -- not a judgement call, a hard
data limit: nothing in this bundle has an `idealpointall` value past 2024
(the "All" companion CSV only reaches year 2023, a year *behind* the
`.dta`, not ahead of it). Any consumer of this file that wants both
measures on a comparable footing for a given year should keep that in mind
-- 2025 rows have `idealpoint_fp` populated and `idealpoint_all` genuinely
null, not a coincidence.

**Cleaning applied**, all directly verified against the raw file:
- Drops 17 rows with blank `iso3c`/`countryname` (legacy placeholder rows,
  scattered 1948-2000).
- Restricts to `year >= 2000`, which also sidesteps the one real duplicate-
  key problem in this file (North Yemen, ccode 678, and South Yemen, ccode
  680, both coded `iso3c="YAR"` for 1967-1989) -- irrelevant to this
  project's 2002-2026 study window either way.
- Asserts `(iso3, year)` uniqueness after filtering; fails loudly rather
  than silently picking one row if that assumption is ever wrong.

`--input` accepts either the real `.dta` file or a `.csv` with the same
column names (lowercase `ccode`/`iso3c`/`countryname`/`year`/`idealpointall`
/`idealpointfp`/`nvotesall`/`nvotesfp`) -- the CSV path exists purely so
tests can exercise this script's cleaning logic without needing a real
Stata file as a fixture.

Usage:  python3 scripts/build_unga_ideal_points.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, REPO  # noqa: E402

FINAL_DATASET_REPO = REPO.parent / "Final dataset"
SOURCE_DTA = (
    FINAL_DATASET_REPO / "Datasets" / "dataverse_files (1)" / "IdealpointsJuly2025.dta"
)
FP_EXTENSION_CSV = (
    FINAL_DATASET_REPO / "Datasets" / "dataverse_files (1)" / "IdealpointestimatesFP_2026FP.csv"
)
TARGET = EXTRACTED_DIR / "unga_ideal_points.csv"

MIN_SOURCE_YEAR = 2000

_EXTENSION_COLUMNS = ["iso3", "year", "idealpoint_all", "idealpoint_fp", "nvotes_all", "nvotes_fp"]

_COLUMNS = {
    "iso3c": "iso3",
    "year": "year",
    "idealpointall": "idealpoint_all",
    "idealpointfp": "idealpoint_fp",
    "nvotesall": "nvotes_all",
    "nvotesfp": "nvotes_fp",
}


def _load(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_stata(path, convert_categoricals=False)
    df.columns = [c.lower() for c in df.columns]
    return df


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Apply this module's cleaning rules to an already-loaded DataFrame.

    Split out from main() so tests can exercise it directly against a small
    in-memory frame, without needing a real .dta fixture.
    """

    df = raw.copy()
    df["iso3c"] = df["iso3c"].astype(str).str.strip()
    df["countryname"] = df["countryname"].astype(str).str.strip()
    df = df[(df["iso3c"] != "") & (df["iso3c"].str.lower() != "nan")]
    df = df[(df["countryname"] != "") & (df["countryname"].str.lower() != "nan")]

    df["year"] = df["year"].astype(int)
    df = df[df["year"] >= MIN_SOURCE_YEAR]

    df = df[list(_COLUMNS)].rename(columns=_COLUMNS)
    df = df.sort_values(["iso3", "year"]).reset_index(drop=True)

    dupes = df[df.duplicated(subset=["iso3", "year"], keep=False)]
    if not dupes.empty:
        raise SystemExit(
            "error: duplicate (iso3, year) rows survived cleaning -- "
            f"{sorted(dupes['iso3'].unique())}. This should not happen for "
            f"year >= {MIN_SOURCE_YEAR}; investigate before trusting this output.\n"
            f"{dupes}"
        )
    return df


def load_fp_extension(path: Path, after_year: int) -> pd.DataFrame:
    """idealpoint_fp-only rows for years past `after_year` (i.e. past what
    the main .dta covers), from the FP-only companion release. There is no
    idealpointall in this file at all -- those columns come back null, not
    guessed. Split out from main() so it's directly testable.
    """

    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    df["iso3c"] = df["iso3c"].astype(str).str.strip()
    df = df[(df["iso3c"] != "") & (df["iso3c"].str.lower() != "nan")]
    df["year"] = df["year"].astype(int)
    df = df[df["year"] > after_year]
    if df.empty:
        return pd.DataFrame(columns=_EXTENSION_COLUMNS)

    out = df[["iso3c", "year", "idealpointfp", "nvotesfp"]].rename(
        columns={"iso3c": "iso3", "idealpointfp": "idealpoint_fp", "nvotesfp": "nvotes_fp"}
    )
    out["idealpoint_all"] = pd.NA
    out["nvotes_all"] = pd.NA
    out = out.sort_values(["iso3", "year"]).reset_index(drop=True)

    dupes = out[out.duplicated(subset=["iso3", "year"], keep=False)]
    if not dupes.empty:
        raise SystemExit(
            f"error: duplicate (iso3, year) rows in the FP extension -- {sorted(dupes['iso3'].unique())}"
        )
    return out[_EXTENSION_COLUMNS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=SOURCE_DTA)
    parser.add_argument("--fp-extension", type=Path, default=FP_EXTENSION_CSV,
                         help="FP-only companion release used to extend idealpoint_fp past the .dta's own "
                              "last year. Optional: if missing, idealpoint_fp simply stays capped like "
                              "idealpoint_all.")
    parser.add_argument("--output", type=Path, default=TARGET)
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(
            f"error: {args.input} does not exist. Expected Erik Voeten's UNGA "
            "ideal-point .dta file (see this module's docstring).",
            file=sys.stderr,
        )
        return 2

    raw = _load(args.input)
    df = clean(raw)

    last_year = int(df["year"].max())
    if args.fp_extension.is_file():
        extension = load_fp_extension(args.fp_extension, after_year=last_year)
        if not extension.empty:
            df = pd.concat([df, extension], ignore_index=True).sort_values(["iso3", "year"]).reset_index(drop=True)
            print(f"extended idealpoint_fp with {len(extension)} rows from {args.fp_extension.name} "
                  f"(years {int(extension['year'].min())}-{int(extension['year'].max())}); "
                  f"idealpoint_all stays capped at {last_year}.")
    else:
        print(f"note: {args.fp_extension} not found -- idealpoint_fp stays capped at {last_year} too.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    print(f"{len(df)} country-year rows, {df['iso3'].nunique()} countries, "
          f"years {df['year'].min()}-{df['year'].max()} -> {args.output}")
    for col in ("idealpoint_all", "idealpoint_fp"):
        non_null = int(df[col].notna().sum())
        print(f"  {col:16} {non_null:6} / {len(df)} non-null")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
