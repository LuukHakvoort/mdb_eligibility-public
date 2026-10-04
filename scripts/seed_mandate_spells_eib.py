"""Seed data/manual/mandate_spells.csv with EIB's External Lending Mandate
(ELM): the non-EU half of Component C that components/mandate.py's
`_eib_in_mandate` has always left `None` for (see its docstring and
docs/coding_decisions.md, 2026-09-21 and 2026-09-27).

**Sources**: the four EUR-Lex decisions the user hand-downloaded into
`data/manual/EIB eligibility documents/` (this project's usual "hand-download
blocked/legal documents" pattern), read directly with pdfplumber this
session, plus the user's own accompanying research note in that same folder
("EIB eligibility caviat.rtf") for the mid-regime amendments that aren't in
the base decision text (activation/removal dates that came later, by
delegated act, and are not printed in the original Annex). Four regimes,
matching the note's own "regime anchors":

1. **2000/24/EC** (OJ L 9, 13.1.2000), Article 1(2): a single flat country
   list, no potential/actual split. In force 1 Feb 2000 (1 Jul 2000 for South
   Africa) - 31 Jan 2007. Coded here as 2000-2006 (superseded by the next
   decision from 2007).
2. **2006/1016/EC** (OJ L 414, 30.12.2006), Annex I: splits "legally
   eligible" (no asterisk) from "potentially eligible, case by case"
   (marked `*`). In force 1 Feb 2007 - 31 Dec 2013, coded as 2007-2013. Only
   the non-starred countries get a row here; starred countries (Libya,
   Belarus, Afghanistan, Bhutan, Cambodia, Iraq, Taiwan) are left unresolved
   for this regime -- no activation date is given in this decision's own
   text. **Exception**: the caveat note gives a specific date for Central
   Asia's activation ("November 2008"), so Kazakhstan/Kyrgyzstan/Tajikistan/
   Turkmenistan/Uzbekistan (all five starred in this Annex) get 2008-2013
   rather than being left unresolved.
3. **2014/466/EU** (OJ L 135, 8.5.2014), Annex III ("ELIGIBLE REGIONS AND
   COUNTRIES" -- the actual, not potential, list; Annex II's potential-only
   countries, e.g. Syria, Cuba, Taiwan, are left unresolved here for the same
   reason as regime 2's starred countries). In force 2014-2020. Three
   mid-regime amendments are documented only in the caveat note (delegated
   acts amending Annex III, not separately downloaded as PDFs -- see the
   note's own citation): Belarus added 2016; Brunei, Chile, Iceland, Israel,
   Singapore and South Korea removed 2018; Iran added 2018.
4. **2021+ (NDICI-Global Europe, Regulation (EU) 2021/947)**: the caveat note
   is explicit that this regime has **no equivalent fixed EIB country
   annex** -- coverage depends on programming, investment windows and
   guarantee agreements, not a published list. This script does not attempt
   to extract one from the 78-page regulation (there is nothing there to
   extract). Instead, every country still eligible at the end of regime 3
   (2020) is carried forward open-ended as an **approximation**, flagged in
   its own `note` -- the caveat's own framing ("broad geographical coverage")
   suggests this understates rather than overstates 2021+ eligibility, so
   this is a conservative floor, not a guess at the true rule. Countries
   removed under regime 3 (Brunei, Chile, Iceland, Israel, Singapore, South
   Korea) are not restored here -- there's no evidence either way, so they
   stay unresolved for 2021+ rather than guessed back in.

**Not attempted**: the caveat's three-way distinction between "potentially
eligible," "legally eligible" and "operationally eligible" (the last needing
a signed EIB framework agreement, per-country, undocumented here) -- this
script only encodes the legal/actual annex, the same granularity
`mandate_spells.csv` already uses for EBRD. **Also not attempted**: the
caveat's warning that EIB lending outside the ELM (ACP/Cotonou, Overseas
Countries and Territories, pre-accession instruments) uses a different legal
basis entirely and would show as "ineligible" under a pure ELM read -- worth
keeping in mind when interpreting EIB's ~980 `revealed`-only panel rows
(`docs/coding_decisions.md`, 2026-09-27), but building those instruments'
own eligibility lists is future work, not done here.

An EU member country's EIB eligibility comes from `eu_membership.csv`
already (`components/mandate.py`'s `_eib_in_mandate` checks that first) --
rows below are not filtered to non-EU countries, since checking EU status
first makes any overlap harmless, and the source decisions' own annexes
already drop each country once it joins (e.g. Croatia is in regime 2's list
but not regime 3's).

Usage:  python3 scripts/seed_mandate_spells_eib.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import MANUAL_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

MANDATE_SPELLS_CSV = MANUAL_DIR / "mandate_spells.csv"

SOURCE_2000 = "Council Decision 2000/24/EC (OJ L 9, 13.1.2000), Article 1(2) -- data/manual/EIB eligibility documents/CELEX%3A32000D0024%3AEN%3ATXT.pdf, read directly this session"
SOURCE_2006 = "Council Decision 2006/1016/EC (OJ L 414, 30.12.2006), Annex I -- data/manual/EIB eligibility documents/CELEX%3A32006D1016%3AEN%3ATXT.pdf, read directly this session"
SOURCE_2014 = "Decision No 466/2014/EU (OJ L 135, 8.5.2014), Annex III -- data/manual/EIB eligibility documents/CELEX%3A32014D0466%3AEN%3ATXT.pdf, read directly this session"
SOURCE_2014_AMEND = "Decision No 466/2014/EU, Annex III as later amended by Commission delegated acts (dates from data/manual/EIB eligibility documents/EIB eligibility caviat.rtf, a research note supplied by the user -- the amending acts themselves were not separately downloaded)"
SOURCE_2021 = "No fixed EIB country annex exists under Regulation (EU) 2021/947 (NDICI-Global Europe)/EFSD+ (see data/manual/EIB eligibility documents/EIB eligibility caviat.rtf); approximated as continuation of the 2014-2020 Annex III list, a documented floor, not an extracted fact -- see docs/coding_decisions.md, 2026-09-27"

# --- Regime 1: 2000-2006, flat list (2000/24/EC Article 1(2)) ---
_REGIME_1 = [
    "Albania", "Bosnia and Herzegovina", "Bulgaria", "Czech Republic", "Estonia",
    "North Macedonia", "Hungary", "Latvia", "Lithuania", "Poland", "Romania", "Slovak Republic", "Slovenia",
    "Algeria", "Cyprus", "Egypt", "Israel", "Jordan", "Lebanon", "Malta", "Morocco", "Syria", "Tunisia",
    "Turkey", "Palestine",
    "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Costa Rica", "Ecuador", "El Salvador",
    "Guatemala", "Honduras", "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru", "Uruguay", "Venezuela",
    "Bangladesh", "Brunei", "China", "India", "Indonesia", "Lao PDR", "Macao", "Malaysia", "Mongolia",
    "Nepal", "Pakistan", "Philippines", "Singapore", "Korea, Rep.", "Sri Lanka", "Thailand", "Vietnam", "Yemen",
    "South Africa",
]

# --- Regime 2: 2007-2013, non-starred (legally eligible) countries only ---
_REGIME_2 = [
    "Croatia", "Turkey", "North Macedonia",
    "Albania", "Bosnia and Herzegovina", "Montenegro", "Serbia", "Kosovo",
    "Algeria", "Egypt", "Palestine", "Israel", "Jordan", "Lebanon", "Morocco", "Syria", "Tunisia",
    "Moldova", "Ukraine", "Armenia", "Azerbaijan", "Georgia", "Russia",
    "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Costa Rica", "Ecuador", "El Salvador",
    "Guatemala", "Honduras", "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru", "Uruguay", "Venezuela",
    "Bangladesh", "Brunei", "China", "India", "Indonesia", "Korea, Rep.", "Lao PDR", "Malaysia", "Maldives",
    "Mongolia", "Nepal", "Pakistan", "Philippines", "Singapore", "Sri Lanka", "Thailand", "Vietnam", "Yemen",
    "South Africa",
]
# Central Asia was starred (potential) in this Annex but the caveat gives a
# specific activation date within this regime.
_REGIME_2_CENTRAL_ASIA_2008 = ["Kazakhstan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Uzbekistan"]

# --- Regime 3: 2014-2020, Annex III ("ELIGIBLE"), excluding the six
# countries the caveat says were removed in 2018 (listed separately below) ---
_REGIME_3 = [
    "North Macedonia", "Montenegro", "Serbia", "Turkey", "Albania", "Bosnia and Herzegovina", "Kosovo",
    "Algeria", "Egypt", "Jordan", "Lebanon", "Libya", "Morocco", "Palestine", "Tunisia",
    "Moldova", "Ukraine", "Armenia", "Azerbaijan", "Georgia", "Russia",
    "Argentina", "Bolivia", "Brazil", "Colombia", "Costa Rica", "Ecuador", "El Salvador", "Guatemala",
    "Honduras", "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru", "Uruguay", "Venezuela",
    "Bangladesh", "Bhutan", "Cambodia", "China", "India", "Indonesia", "Iraq", "Lao PDR", "Malaysia",
    "Maldives", "Mongolia", "Myanmar", "Nepal", "Pakistan", "Philippines", "Sri Lanka", "Thailand",
    "Vietnam", "Yemen",
    "Kazakhstan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Uzbekistan",
    "South Africa",
]
# Removed by delegated act in 2018 (caveat note) -- eligible only 2014-2017.
_REGIME_3_REMOVED_2018 = ["Brunei", "Chile", "Iceland", "Israel", "Singapore", "Korea, Rep."]
# Added by delegated act mid-regime (caveat note).
_REGIME_3_BELARUS_FROM_2016 = "Belarus"
_REGIME_3_IRAN_FROM_2018 = "Iran"

# 2021+: every country still eligible at the end of regime 3 (2020) --
# i.e. _REGIME_3 (which already includes Central Asia) plus Belarus and Iran,
# minus the six removed in 2018 (already excluded from _REGIME_3's own list
# above) -- carried forward open-ended.
_REGIME_4_CARRY_FORWARD = _REGIME_3 + [_REGIME_3_BELARUS_FROM_2016, _REGIME_3_IRAN_FROM_2018]


def _resolve(name: str) -> str:
    iso3 = iso3_from_name(name)
    if not iso3:
        raise SystemExit(f"{name!r} did not resolve to an ISO-3 code -- fix the name and re-run.")
    return iso3


def _rows(names: list[str], start: int, end: int | None, source: str, note: str = "") -> list[dict]:
    return [
        {"bank": "EIB", "iso3": _resolve(name), "basis": "external_lending_mandate",
         "start_year": str(start), "end_year": str(end) if end is not None else "",
         "source": source, "note": note}
        for name in names
    ]


def build_rows() -> list[dict]:
    rows: list[dict] = []
    rows += _rows(_REGIME_1, 2000, 2006, SOURCE_2000)
    rows += _rows(_REGIME_2, 2007, 2013, SOURCE_2006)
    rows += _rows(_REGIME_2_CENTRAL_ASIA_2008, 2008, 2013, SOURCE_2006,
                  "Starred (\"potentially eligible, case by case\") in Annex I; activated November 2008 per the caveat note.")
    rows += _rows(_REGIME_3, 2014, 2020, SOURCE_2014)
    rows += _rows(_REGIME_3_REMOVED_2018, 2014, 2017, SOURCE_2014,
                  "Removed by delegated act in 2018 per the caveat note; the amending act's own text was not downloaded.")
    rows += _rows([_REGIME_3_BELARUS_FROM_2016], 2016, 2020, SOURCE_2014_AMEND,
                  "Not in the original Annex III text (2014); added by delegated act in 2016 per the caveat note.")
    rows += _rows([_REGIME_3_IRAN_FROM_2018], 2018, 2020, SOURCE_2014_AMEND,
                  "Not in the original Annex III text (2014); added by delegated act in 2018 per the caveat note.")
    rows += _rows(_REGIME_4_CARRY_FORWARD, 2021, None, SOURCE_2021,
                  "Approximated: no fixed ELM country annex exists under NDICI-Global Europe (2021+); this is 2020's Annex III list carried forward open-ended, not an extracted fact.")
    return rows


BASIS = "external_lending_mandate"


def main() -> int:
    existing = read_csv(MANDATE_SPELLS_CSV) if MANDATE_SPELLS_CSV.is_file() else []
    # Reseed only this script's own (bank, basis) rows -- other EIB bases
    # (e.g. "acp_cotonou", "oct_association", scripts/
    # seed_mandate_spells_eib_acp.py) and other banks' rows (EBRD) are kept.
    kept = [row for row in existing if not (row.get("bank") == "EIB" and row.get("basis") == BASIS)]
    new_rows = build_rows()
    combined = kept + new_rows
    write_csv(MANDATE_SPELLS_CSV, ["bank", "iso3", "basis", "start_year", "end_year", "source", "note"], combined)
    print(f"{len(new_rows)} EIB/{BASIS} rows ({len(kept)} other rows kept) -> {MANDATE_SPELLS_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
