"""Build data/extracted/afdb_window_breakdown.csv: AfDB's ordinary-capital
vs. concessional (African Development Fund, ADF) lending, per (iso3, year),
as columns on AfDB's own row -- not as a second bank code.

**Replaces `build_afdb_adf_split.py` (2026-09-24 - 2026-09-28).** ADF was
briefly split into its own canonical bank code so its lending could be
counted separately, but it never got independent shareholding, membership,
mandate or window data of its own (`shareholders_panel.csv` has zero ADF
rows -- every other column was always copied from AfDB or left null), and a
real subset of projects (127, tagged with *both* windows in the scraper's
own `funding_window` field) had no honest way to be split between two
competing bank-level totals without double-counting or guessing -- checked
directly: these blended projects are ~4-5x larger than a typical single-
window project ($82.9M median vs. $17.5-24.4M), so the distortion would land
on exactly the biggest, most consequential lending. See
docs/coding_decisions.md, 2026-09-28, for the full account. AfDB and ADF are
merged back into one canonical `AfDB` code; this script now produces
sub-totals as *columns* instead, which sidesteps the double-counting problem
entirely -- a blended project simply adds to both sub-totals on the same
row, with nothing being divided between two separate grand totals.

**Reads `../mdbs_scraper_corrected/output/all_mdb_projects_usd.csv`** (the
project-level, currency-converted file `build_mdb_panel.py` and
`build_project_breakdown.py` already use for USD amounts), not
`afdb_projects.csv`'s raw, unconverted `total_commitment_usd` -- so these
sub-totals are on the same constant-2025-USD basis as every other USD figure
in this project, not a second, inconsistent one.

**Categorization rule for `funding_window`** (unchanged from the retired
`build_afdb_adf_split.py`, confirmed with the user 2026-09-24):

- Contains "African Development Bank" AND "African Development Fund" ->
  counts toward *both* sub-totals (ordinary and concessional) -- correct
  here, since these are independent sub-totals on one row, not two banks'
  competing totals.
- Contains "African Development Fund" (alone, or with a co-listed fund such
  as Transition Support Facility) but not "African Development Bank" ->
  concessional only.
- Contains "African Development Bank" (alone, or with a co-listed fund) but
  not "African Development Fund" -> ordinary only.
- A standalone named special/trust fund with neither substring (Transition
  Support Facility, Congo Basin Forest Fund, AfricaWater Facility Fund,
  Sustainable Energy Fund for Africa, Nigerian Trust Fund, etc.) -> ordinary
  (AfDB-administered trust funds with external co-financiers, not part of
  ADF's own capital structure -- confirmed with the user 2026-09-24).
- Blank -> unresolved, reported, not dropped or guessed.

Rows with no `country_code` (regional/multi-country projects) are excluded
here the same way `build_commitments.py` excludes them via
`dyad_unallocated_year.csv` -- not recomputed, just reported separately.

Usage:  python3 scripts/build_afdb_window_breakdown.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, REPO, REPORTS_DIR, read_csv, write_csv  # noqa: E402

REFERENCE_REPO = Path(__file__).resolve().parents[2] / "mdbs_scraper_corrected"
ALL_PROJECTS_CSV = REFERENCE_REPO / "output" / "all_mdb_projects_usd.csv"

TARGET = EXTRACTED_DIR / "afdb_window_breakdown.csv"
FIELDS = ["iso3", "year", "afdb_ordinary_n", "afdb_ordinary_usd", "afdb_concessional_n", "afdb_concessional_usd"]
UNRESOLVED_REPORT = REPORTS_DIR / "afdb_window_unresolved.csv"
UNALLOCATED_REPORT = REPORTS_DIR / "afdb_window_unallocated.csv"


def _windows_for(funding_window: str) -> list[str]:
    text = funding_window or ""
    has_afdb = "African Development Bank" in text
    has_adf = "African Development Fund" in text
    if has_afdb and has_adf:
        return ["ordinary", "concessional"]
    if has_adf:
        return ["concessional"]
    if has_afdb:
        return ["ordinary"]
    if text.strip():
        return ["ordinary"]  # standalone AfDB-administered trust fund -- see module docstring
    return []  # blank -- unresolved


def main() -> int:
    if not ALL_PROJECTS_CSV.is_file():
        print(f"error: {ALL_PROJECTS_CSV} does not exist.", file=sys.stderr)
        return 2

    totals: dict[tuple[str, int], dict[str, float]] = defaultdict(
        lambda: {"ordinary_n": 0, "ordinary_usd": 0.0, "concessional_n": 0, "concessional_usd": 0.0}
    )
    unresolved: list[dict] = []
    unallocated: list[dict] = []

    for row in read_csv(ALL_PROJECTS_CSV):
        if row.get("bank_id") != "afdb":
            continue
        iso3 = row.get("country_code", "")
        year = row.get("approval_year", "")
        funding_window = row.get("funding_window", "")
        if not year.isdigit():
            continue
        if not iso3:
            unallocated.append({"project_id": row.get("project_id", ""), "year": year,
                                 "funding_window": funding_window, "country": row.get("country", "")})
            continue

        windows = _windows_for(funding_window)
        if not windows:
            unresolved.append({"project_id": row.get("project_id", ""), "iso3": iso3, "year": year,
                                "funding_window": funding_window})
            continue

        try:
            usd = float(row.get("usd_constant_2025") or 0)
        except ValueError:
            usd = 0.0

        key = (iso3, int(year))
        for window in windows:
            totals[key][f"{window}_n"] += 1
            totals[key][f"{window}_usd"] += usd

    rows_out = [
        {
            "iso3": iso3, "year": year,
            "afdb_ordinary_n": int(measures["ordinary_n"]),
            "afdb_ordinary_usd": round(measures["ordinary_usd"], 2),
            "afdb_concessional_n": int(measures["concessional_n"]),
            "afdb_concessional_usd": round(measures["concessional_usd"], 2),
        }
        for (iso3, year), measures in totals.items()
    ]
    rows_out.sort(key=lambda r: (r["iso3"], r["year"]))

    write_csv(TARGET, FIELDS, rows_out)
    write_csv(UNRESOLVED_REPORT, ["project_id", "iso3", "year", "funding_window"], unresolved)
    write_csv(UNALLOCATED_REPORT, ["project_id", "year", "funding_window", "country"], unallocated)

    total_ordinary = sum(r["afdb_ordinary_n"] for r in rows_out)
    total_concessional = sum(r["afdb_concessional_n"] for r in rows_out)
    print(f"{len(rows_out)} AfDB (iso3, year) rows: {total_ordinary} ordinary-window projects, "
          f"{total_concessional} concessional-window projects (blended projects count toward both)")
    print(f"{len(unresolved)} projects unresolved (blank funding_window) -> {UNRESOLVED_REPORT.relative_to(REPO)}")
    print(f"{len(unallocated)} projects unallocated (no country_code) -> {UNALLOCATED_REPORT.relative_to(REPO)}")
    print(f"-> {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
