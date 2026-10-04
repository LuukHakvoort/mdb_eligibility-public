"""Build data/extracted/project_breakdown.csv: per (bank, iso3, year), how
many projects fell in each sector category, how many were loans/grants/
technical assistance/etc., and how many were sovereign vs. non-sovereign
lending -- with USD amounts for the instrument-type and sovereign-status
splits. Reads the same source `build_mdb_panel.py` already joins USD amounts
from: `../mdbs_scraper_corrected/output/all_mdb_projects_usd.csv`
(61,014 project-level rows) -- no new source, just a different aggregation
of one already-used file.

Three pivots, one row per (bank, iso3, year) in the end:

- `sector_<category>`: project **counts** by `sector_category` (~30 real
  values -- Banking & Financial Services, Transport & Storage, Agriculture,
  Energy, Health, Education, ...; ~16% of projects have no sector recorded
  at all, kept as `sector__unspecified`, not silently dropped).
- `instrument_<type>_n` / `instrument_<type>_usd`: counts and
  `usd_constant_2025` sums by `instrument_category` (`loan`,
  `technical_assistance`, `grant`, `trade_finance`, `equity`, `guarantee`,
  `other`; ~34% blank, kept as `instrument_unspecified_*`).
- `sovereign_n` / `sovereign_usd` and `non_sovereign_n` / `non_sovereign_usd`:
  counts and amounts by `loan_type` (`Sovereign`/`Non-sovereign`; ~37% blank
  across the whole source -- real, uneven non-disclosure, not random, so also
  kept as its own `sovereign_unknown_n`/`_usd` rather than merged into either
  side).

**AfDB is included like every other bank** (2026-09-28 -- AfDB and ADF were
briefly two separate bank codes, 2026-09-24 to 2026-09-28, and this script
used to skip AfDB's project rows entirely since there was no honest way to
split a combined-window project's sector/instrument category between two
competing bank codes; see docs/coding_decisions.md). Now that AfDB/ADF are
merged back into one code, every AfDB project counts toward this one code's
sector/instrument/sovereign breakdown directly, the same as any other bank --
its own ordinary-vs-concessional lending split lives separately, as columns
on `mdb_panel.csv`'s AfDB row (`scripts/build_afdb_window_breakdown.py`), not
here.

Usage:  python3 scripts/build_project_breakdown.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import BANKS, EXTRACTED_DIR, REPO, read_csv, write_csv  # noqa: E402

ALL_PROJECTS_CSV = Path(__file__).resolve().parents[2] / "mdbs_scraper_corrected" / "output" / "all_mdb_projects_usd.csv"
TARGET = EXTRACTED_DIR / "project_breakdown.csv"

_INSTRUMENT_TYPES = ["loan", "technical_assistance", "grant", "trade_finance", "equity", "guarantee", "other"]
_SECTOR_UNSPECIFIED = "__unspecified"
_INSTRUMENT_UNSPECIFIED = "unspecified"


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.strip().lower()).strip("_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all-projects", type=Path, default=ALL_PROJECTS_CSV)
    parser.add_argument("--output", type=Path, default=TARGET)
    args = parser.parse_args(argv)

    if not args.all_projects.is_file():
        print(f"error: {args.all_projects} does not exist.", file=sys.stderr)
        return 2

    id_to_bank = {bank_id: bank for bank, bank_id in BANKS.items()}
    sector_values: set[str] = set()

    # keyed by (bank, iso3, year)
    sector_counts: dict[tuple, dict[str, int]] = {}
    instrument_counts: dict[tuple, dict[str, int]] = {}
    instrument_usd: dict[tuple, dict[str, float]] = {}
    sovereign_counts: dict[tuple, dict[str, int]] = {}
    sovereign_usd: dict[tuple, dict[str, float]] = {}

    for row in read_csv(args.all_projects):
        bank_id = row.get("bank_id", "")
        bank = id_to_bank.get(bank_id)
        iso3 = row.get("country_code", "")
        year_text = row.get("approval_year", "")
        if not bank or not iso3 or not year_text.isdigit():
            continue
        key = (bank, iso3, int(year_text))

        sector = row.get("sector_category", "").strip() or _SECTOR_UNSPECIFIED
        sector_values.add(sector)
        sector_counts.setdefault(key, {})
        sector_counts[key][sector] = sector_counts[key].get(sector, 0) + 1

        instrument = row.get("instrument_category", "").strip() or _INSTRUMENT_UNSPECIFIED
        usd = float(row.get("usd_constant_2025") or 0)
        instrument_counts.setdefault(key, {})
        instrument_counts[key][instrument] = instrument_counts[key].get(instrument, 0) + 1
        instrument_usd.setdefault(key, {})
        instrument_usd[key][instrument] = instrument_usd[key].get(instrument, 0.0) + usd

        loan_type = row.get("loan_type", "").strip()
        sovereign_key = "sovereign" if loan_type == "Sovereign" else "non_sovereign" if loan_type == "Non-sovereign" else "unknown"
        sovereign_counts.setdefault(key, {})
        sovereign_counts[key][sovereign_key] = sovereign_counts[key].get(sovereign_key, 0) + 1
        sovereign_usd.setdefault(key, {})
        sovereign_usd[key][sovereign_key] = sovereign_usd[key].get(sovereign_key, 0.0) + usd

    all_keys = set(sector_counts) | set(instrument_counts) | set(sovereign_counts)
    sector_columns = sorted(sector_values)
    instrument_columns = [t for t in _INSTRUMENT_TYPES] + [_INSTRUMENT_UNSPECIFIED]

    fields = ["bank", "iso3", "year"]
    fields += [f"sector_{_slug(s)}_n" for s in sector_columns]
    for t in instrument_columns:
        fields += [f"instrument_{t}_n", f"instrument_{t}_usd"]
    for t in ("sovereign", "non_sovereign", "unknown"):
        fields += [f"{t}_n", f"{t}_usd"]

    rows_out: list[dict] = []
    for key in sorted(all_keys):
        bank, iso3, year = key
        row_out = {"bank": bank, "iso3": iso3, "year": year}
        for s in sector_columns:
            row_out[f"sector_{_slug(s)}_n"] = sector_counts.get(key, {}).get(s, 0)
        for t in instrument_columns:
            row_out[f"instrument_{t}_n"] = instrument_counts.get(key, {}).get(t, 0)
            row_out[f"instrument_{t}_usd"] = round(instrument_usd.get(key, {}).get(t, 0.0), 2)
        for t in ("sovereign", "non_sovereign", "unknown"):
            row_out[f"{t}_n"] = sovereign_counts.get(key, {}).get(t, 0)
            row_out[f"{t}_usd"] = round(sovereign_usd.get(key, {}).get(t, 0.0), 2)
        rows_out.append(row_out)

    write_csv(args.output, fields, rows_out)
    output_label = args.output.relative_to(REPO) if args.output.is_relative_to(REPO) else args.output
    print(f"{len(rows_out)} bank-country-year rows, {len(sector_columns)} sector categories, "
          f"{len(instrument_columns)} instrument types -> {output_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
