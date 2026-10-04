"""Component B: was country j a member (recipient) of bank i in year t?

Three signals, in order of authority:

1. A real `accession_date` in accession_dates.csv -- read from the bank's own
   member/shareholder page or financial statements (Wayback-derived for EBRD
   and IsDB; from the shares workbook's own sourced current lists otherwise).
   This is a genuine date: a year before it is a confident False, not unknown.
2. `earliest_observed_year` -- the first year the project scraper observed
   this bank lending to this country. A hard *upper bound* on accession
   (collection plan section 2.1): year >= this is a confident True (they must
   have been a member to receive that loan); year before it is unknown, not
   False -- they may well have joined earlier and simply not borrowed yet.
3. Presence in shareholders_panel.csv for some year Y -- the same upper-bound
   logic as (2): confirmed member by Y, unknown before it.

Whichever gives the earliest confirmed-member year wins. A (bank, iso3) pair
absent from every source is `None` (no evidence either way), never False.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _panel import EXTRACTED_DIR, MANUAL_DIR, read_csv  # noqa: E402

ACCESSION_CSV = MANUAL_DIR / "accession_dates.csv"
PANEL_CSV = EXTRACTED_DIR / "shareholders_panel.csv"


def load_membership_evidence() -> dict[tuple[str, str], dict]:
    """{(bank, iso3): {"accession_year": int|None, "earliest_observed_year": int|None,
    "earliest_panel_year": int|None}}"""

    evidence: dict[tuple[str, str], dict] = {}

    for row in read_csv(ACCESSION_CSV):
        bank, iso3 = row["bank"], row["iso3"]
        if not bank or not iso3:
            continue
        key = (bank, iso3)
        entry = evidence.setdefault(key, {
            "accession_year": None, "earliest_observed_year": None, "earliest_panel_year": None,
        })
        date = row.get("accession_date", "")
        if date and date[:4].isdigit():
            entry["accession_year"] = int(date[:4])
        observed = row.get("earliest_observed_year", "")
        if observed.isdigit():
            entry["earliest_observed_year"] = int(observed)

    if PANEL_CSV.is_file():
        for row in read_csv(PANEL_CSV):
            bank, iso3, year = row["bank"], row["iso3"], row.get("year", "")
            if not (bank and iso3 and year.isdigit()):
                continue
            key = (bank, iso3)
            entry = evidence.setdefault(key, {
                "accession_year": None, "earliest_observed_year": None, "earliest_panel_year": None,
            })
            year_int = int(year)
            current = entry["earliest_panel_year"]
            if current is None or year_int < current:
                entry["earliest_panel_year"] = year_int

    return evidence


def is_member(
    bank: str, iso3: str, year: int, evidence: dict[tuple[str, str], dict] | None = None,
) -> bool | None:
    entry = (evidence if evidence is not None else load_membership_evidence()).get((bank, iso3))
    if entry is None:
        return None

    if entry["accession_year"] is not None:
        return year >= entry["accession_year"]

    lower_bounds = [v for v in (entry["earliest_observed_year"], entry["earliest_panel_year"]) if v is not None]
    if not lower_bounds:
        return None
    threshold = min(lower_bounds)
    return True if year >= threshold else None
