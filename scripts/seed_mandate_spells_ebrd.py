"""Seed data/manual/mandate_spells.csv: EBRD's countries-of-operations
timeline (docs/architecture.md section 3), the real fix for the gap already
logged in docs/coding_decisions.md ("EBRD's Date joined is Component B not
C" -- Egypt/Morocco show a 1991 shareholder date but only became countries
of operations in 2012).

**Scoped deliberately to the expansion cohorts only** -- Mongolia (2006),
Turkey (2009), the 2012 Southern and Eastern Mediterranean round (Jordan,
Tunisia, Morocco, Egypt, Kosovo), and the 2023 policy decision's first
Sub-Saharan Africa/Iraq cohort (Benin, Cote d'Ivoire, Kenya, Nigeria,
Senegal, Ghana, Iraq) -- all found and dated live via WebSearch this session,
real sources below. EBRD's ~30 founding Central/Eastern European and former
Soviet Union countries of operations are **not** individually re-researched
here: enumerating them from memory risks exactly the kind of plausible-
looking wrong date CLAUDE.md's hard rules warn against, when the far safer,
still-sourced answer already exists -- for that founding cohort, EBRD's own
"Date joined" (already in accession_dates.csv, Wayback-reconstructed,
100% dated) *is* their countries-of-operations date, since they joined
EBRD specifically as founding operational recipients, not as later-added
shareholders. `components/mandate.py`'s EBRD case uses this file for the
cohorts it covers and falls back to `accession_dates.csv` for everyone else
-- a sourced choice, not a guess, but the coverage gap is worth stating
explicitly: a founding-cohort country whose real countries-of-operations
date diverged from its membership date (if any exist) would not be caught by
this pass.

Usage:  python3 scripts/seed_mandate_spells_ebrd.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import MANUAL_DIR, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

SOURCE = "EBRD history page (ebrd.com/home/who-we-are/ebrd-history.html) and 2023-2024 expansion coverage, researched live this session"

# (name, start_year, note)
ROWS = [
    ("Mongolia", 2006, "Extended eastward to Mongolia."),
    ("Turkey", 2009, ""),
    ("Jordan", 2012, "Southern and Eastern Mediterranean (SEMED) expansion, following the Deauville Partnership G8 backing (2011)."),
    ("Tunisia", 2012, "SEMED expansion."),
    ("Morocco", 2012, "SEMED expansion."),
    ("Egypt", 2012, "SEMED expansion."),
    ("Kosovo", 2012, "SEMED expansion."),
    ("Benin", 2024, "First Sub-Saharan Africa cohort, following the 2023 Board of Governors expansion decision."),
    ("Cote d'Ivoire", 2024, "First Sub-Saharan Africa cohort."),
    ("Kenya", 2024, "First Sub-Saharan Africa cohort."),
    ("Nigeria", 2024, "First Sub-Saharan Africa cohort."),
    ("Senegal", 2024, "First Sub-Saharan Africa cohort."),
    ("Ghana", 2024, "First Sub-Saharan Africa cohort."),
    ("Iraq", 2024, "Added alongside the first Sub-Saharan Africa cohort."),
]


def _resolve(name: str) -> str:
    iso3 = iso3_from_name(name)
    if not iso3:
        raise SystemExit(f"{name!r} did not resolve to an ISO-3 code -- fix the name and re-run.")
    return iso3


def main() -> int:
    rows = [
        {"bank": "EBRD", "iso3": _resolve(name), "basis": "countries_of_operations",
         "start_year": str(start), "end_year": "", "source": SOURCE, "note": note}
        for name, start, note in ROWS
    ]
    write_csv(MANUAL_DIR / "mandate_spells.csv",
              ["bank", "iso3", "basis", "start_year", "end_year", "source", "note"], rows)
    print(f"{len(rows)} rows -> data/manual/mandate_spells.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
