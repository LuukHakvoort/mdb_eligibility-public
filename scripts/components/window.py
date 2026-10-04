"""Component D: did country j meet bank i's income/creditworthiness window
criteria in year t?

Driven by each bank's `d_basis` in `data/manual/banks.json`
(docs/architecture.md section 2, logged as a coding decision 2026-09-21):

- `no_formal_window`: `window_ok = True` unconditionally -- most banks have
  no income-based lending window at all (architecture.md: "every other bank
  is 1, with source 'no formal income window'"). Also covers AfDB, AsDB and
  IsDB (moved here from a planned `classification_spells`, 2026-09-21):
  architecture.md's Category A/B/C (Fund-only/Blend/Bank-only) distinction
  matters only once ADF/AsDF exist as their own bank codes (decision 2,
  still open) -- at this repo's current single-combined-bank-code
  granularity, every category is eligible for *some* Group financing, so
  window_ok=1 for any confirmed regional/DMC/OIC recipient is correct, not
  a guess.
- `oghist_income`: IBRD and IDA, read from two sources, the more precise one
  taking priority per year:
  1. `data/extracted/oghist_lending_category.csv` (the World Bank's *current*
     classification file, "List of economies" sheet -- a direct
     IDA/IBRD/Blend/None column, no ambiguity). Currently covers only
     calendar year 2026 (its own FY27 snapshot date) -- not projected
     backward, since a country's category can and does change year to year
     and guessing risks exactly the silent wrong data CLAUDE.md's hard rules
     warn against.
  2. `data/extracted/oghist_income.csv` (OGHIST.xlsx's "Country Analytical
     History" sheet -- income classification L/LM/UM/H per country per
     fiscal year, mapped to calendar year via decision 4). Covers 2002-2022.
     Years 2023-2025 are a known, undocumented-here gap in both sources.
- `classification_spells`: not currently used by any bank -- reserved for
  when ADF/AsDF become their own bank codes and need a real
  `window_classifications.csv`.

**IBRD/IDA rule, and its two known limitations,** both found live by
`check_revealed.py` and fixed by widening a hedge rather than by guessing:

1. **Blend countries** (CLAUDE.md Known Traps: "eligible for both arms") --
   a low-income country can be creditworthy enough for IBRD terms alongside
   IDA eligibility. Income-classification data (L/LM/UM/H) alone cannot
   distinguish a genuine "IDA-only" low-income country from a blend one --
   that distinction lives in OGHIST's separate `Operational Category Change`
   sheet (a transition-event log with its own, not-yet-verified category
   semantics across a pre-FY09/post-FY09 redefinition), not built here.
2. **Small states** -- confirmed live: Dominica and Grenada are classified
   "UM" (upper middle income) throughout 2010-2019 in `oghist_income.csv`,
   yet both have real, observed IDA lending every one of those years
   (`check_revealed.py` flagged both, among ~10 small island/small-population
   states in the same pattern -- Tuvalu, Maldives, Tonga, Marshall Islands,
   St Lucia, St Vincent). The World Bank's long-standing small-state
   exception keeps them IDA-eligible above the normal income cutoff for
   vulnerability reasons this income-group table has no way to represent.

Given both, the rule below never guesses a confident False from income group
alone -- it only ever asserts True or None:

- IDA `window_ok`: True if income group is L or LM; **None (not False) if
  UM or H** -- the small-state exception means a high income-group value
  does not reliably rule out IDA eligibility.
- IBRD `window_ok`: True if income group is LM, UM, or H; **None (not
  False) if income group is L** -- a low-income country might be a blend
  country genuinely IBRD-eligible too.
- Both: None if unclassified in the source.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _panel import EXTRACTED_DIR, read_csv  # noqa: E402
from components import recipient  # noqa: E402

OGHIST_INCOME_CSV = EXTRACTED_DIR / "oghist_income.csv"

_IDA_TRUE = {"L", "LM"}
_IBRD_TRUE = {"LM", "UM", "H"}
# income group "L" is deliberately absent from _IBRD_TRUE (blend ambiguity),
# and there is deliberately no _IDA_FALSE set (small-state exception) --
# see module docstring.


LENDING_CATEGORY_CSV = EXTRACTED_DIR / "oghist_lending_category.csv"


def load_oghist_income() -> dict[tuple[str, int], str]:
    """{(iso3, calendar_year): income_group}, already calendar-year-mapped
    (decision 4) by whatever built oghist_income.csv."""

    income: dict[tuple[str, int], str] = {}
    if not OGHIST_INCOME_CSV.is_file():
        return income
    for row in read_csv(OGHIST_INCOME_CSV):
        iso3, year = row.get("iso3", ""), row.get("calendar_year", "")
        group = row.get("income_group", "")
        if iso3 and year.isdigit() and group:
            income[(iso3, int(year))] = group
    return income


def load_oghist_lending_category() -> dict[tuple[str, int], str]:
    """{(iso3, calendar_year): lending_category ("IDA"/"IBRD"/"Blend")}."""

    categories: dict[tuple[str, int], str] = {}
    if not LENDING_CATEGORY_CSV.is_file():
        return categories
    for row in read_csv(LENDING_CATEGORY_CSV):
        iso3, year = row.get("iso3", ""), row.get("calendar_year", "")
        category = row.get("lending_category", "")
        if iso3 and year.isdigit() and category:
            categories[(iso3, int(year))] = category
    return categories


def _oghist_window_ok(
    bank: str, iso3: str, year: int,
    income: dict[tuple[str, int], str], lending_category: dict[tuple[str, int], str],
) -> bool | None:
    category = lending_category.get((iso3, year))
    if category is not None:
        # The direct, unambiguous signal -- no blend hedge needed.
        if bank == "IDA":
            return category in ("IDA", "Blend")
        if bank == "IBRD":
            return category in ("IBRD", "Blend")
        return None

    group = income.get((iso3, year))
    if group is None:
        return None
    if bank == "IDA":
        return True if group in _IDA_TRUE else None
    if bank == "IBRD":
        return True if group in _IBRD_TRUE else None
    return None


def window_ok(
    bank: str,
    iso3: str,
    year: int,
    d_basis: dict[str, str] | None = None,
    oghist_income: dict[tuple[str, int], str] | None = None,
    oghist_lending_category: dict[tuple[str, int], str] | None = None,
) -> bool | None:
    basis = (d_basis if d_basis is not None else recipient.load_d_basis()).get(bank)
    if basis == "no_formal_window":
        return True
    if basis == "oghist_income":
        income = oghist_income if oghist_income is not None else load_oghist_income()
        category = oghist_lending_category if oghist_lending_category is not None else load_oghist_lending_category()
        return _oghist_window_ok(bank, iso3, year, income, category)
    if basis == "classification_spells":
        return None  # real data not built yet -- see this module's docstring
    return None
