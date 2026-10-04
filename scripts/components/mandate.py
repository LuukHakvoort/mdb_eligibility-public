"""Component C: was country j inside bank i's geographic mandate in year t?

Driven by each bank's `c_basis` in `data/manual/banks.json`
(docs/architecture.md section 2, logged as a coding decision 2026-09-21):

- `trivial_region`: the bank's recipient set (Component B) is already
  regionally defined, so a country confirmed a recipient is trivially inside
  the mandate too -- mirrors `components/recipient.py`'s
  `is_recipient()` directly. True for IBRD, IDA, AfDB, AsDB, IDB, IsDB, CAF,
  CDB, NDB, CABEI: each bank's own borrowing-member research (or, for
  IBRD/IDA, near-universal membership) already encodes "regional," so this
  isn't a guess -- it's reading the same fact B already established.
  **AIIB is here too**, moved from an earlier, wrong `computed` guess
  (architecture.md's "member AND NOT high-income" framing) once AIIB's own
  FAQ turned up the real rule directly: "AIIB may provide or facilitate
  financing to any member... Prospective members will only be eligible for
  financing after they become a member" -- no income or regional gate at
  all (https://www.aiib.org/en/projects/apply/faq/index.html, supplied by
  the user 2026-09-21). This also explains, after the fact, why
  `components/window.py` and this module both had to hedge AIIB's
  non-regional and high-income exclusions away from a confident False
  earlier the same session: those exclusions were never real.
- `spell_based`: needs a real dated mandate_spells.csv (EBRD's countries of
  operations, EIB's External Lending Mandate). For **EBRD**,
  `data/manual/mandate_spells.csv` covers the six well-documented expansion
  cohorts (Mongolia 2006, Turkey 2009, the 2012 SEMED round, the 2024 first
  Sub-Saharan Africa/Iraq cohort) -- for everyone else (the founding
  Central/Eastern European and former Soviet Union cohort), EBRD's own
  "Date joined" (already in `accession_dates.csv`, Wayback-reconstructed) is
  their countries-of-operations date too, since they joined EBRD
  specifically as founding operational recipients, not as later-added
  shareholders (a sourced choice, not a guess -- see
  `scripts/seed_mandate_spells_ebrd.py`'s docstring for why the founding
  cohort wasn't individually re-researched). **That accession-date fallback
  is checked against `data/manual/non_regional_shareholders.csv` first**
  (2026-10-02) -- EBRD's ~30+ non-regional donor shareholders (the US,
  Japan, Germany, and more) have an accession date that looks identical in
  shape to a founding recipient's, but were never a country of operations;
  see `components/recipient.py`'s module docstring for the full account.
  For **EIB**,
  `data/manual/eu_membership.csv` (public record, real dated accessions/
  exits) resolves the in-EU case to a confident True; for a non-EU country,
  `data/manual/mandate_spells.csv`'s `EIB` rows (`scripts/
  seed_mandate_spells_eib.py`, docs/coding_decisions.md 2026-09-27) now cover
  the External Lending Mandate's four historical regimes (2000-2006,
  2007-2013, 2014-2020, 2021+) from the actual EUR-Lex decision text the user
  supplied -- a country outside every regime's own annex for that year is
  still `None`, not a guessed False (e.g. a country only ever "potentially",
  not "actually," eligible, per that regime's own annex).
- `computed`: derived from other membership lists. Currently just
  **BADEA**: AU member AND NOT Arab League member
  (`data/manual/au_membership.csv`, `arab_league_membership.csv` --
  spell-based, but *complete* rosters: every AU/Arab League member that has
  ever existed has a row, so a country absent entirely is a confident
  False (never a member), not unknown -- unlike `components/bars.py`'s
  sparse-coverage file, where absence means "not logged yet." Always
  resolves to a definite True/False, never None, once run.

A bank absent from banks.json, or with an unrecognized c_basis, is None --
not a guess.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _panel import MANUAL_DIR, read_csv  # noqa: E402
from components import recipient  # noqa: E402

AU_MEMBERSHIP_CSV = MANUAL_DIR / "au_membership.csv"
ARAB_LEAGUE_MEMBERSHIP_CSV = MANUAL_DIR / "arab_league_membership.csv"
EU_MEMBERSHIP_CSV = MANUAL_DIR / "eu_membership.csv"
MANDATE_SPELLS_CSV = MANUAL_DIR / "mandate_spells.csv"


def _load_spells(path: Path) -> dict[str, list[tuple[int | None, int | None]]]:
    spells: dict[str, list[tuple[int | None, int | None]]] = {}
    if not path.is_file():
        return spells
    for row in read_csv(path):
        iso3 = row.get("iso3", "")
        if not iso3:
            continue
        start = row.get("start_year", "")
        end = row.get("end_year", "")
        spells.setdefault(iso3, []).append((
            int(start) if start.isdigit() else None,
            int(end) if end.isdigit() else None,
        ))
    return spells


def load_au_membership() -> dict[str, list[tuple[int | None, int | None]]]:
    return _load_spells(AU_MEMBERSHIP_CSV)


def load_arab_league_membership() -> dict[str, list[tuple[int | None, int | None]]]:
    return _load_spells(ARAB_LEAGUE_MEMBERSHIP_CSV)


def load_eu_membership() -> dict[str, list[tuple[int | None, int | None]]]:
    return _load_spells(EU_MEMBERSHIP_CSV)


def load_mandate_spells(bank: str) -> dict[str, list[tuple[int | None, int | None]]]:
    spells: dict[str, list[tuple[int | None, int | None]]] = {}
    if not MANDATE_SPELLS_CSV.is_file():
        return spells
    for row in read_csv(MANDATE_SPELLS_CSV):
        if row.get("bank") != bank:
            continue
        iso3 = row.get("iso3", "")
        if not iso3:
            continue
        start = row.get("start_year", "")
        end = row.get("end_year", "")
        spells.setdefault(iso3, []).append((
            int(start) if start.isdigit() else None,
            int(end) if end.isdigit() else None,
        ))
    return spells


def _in_closed_list(iso3: str, year: int, spells: dict[str, list[tuple[int | None, int | None]]]) -> bool:
    """For a complete, closed membership roster (every AU/Arab League member
    that has ever existed is in this dict): absence entirely is a confident
    False, not unknown -- there is no one left to still be missing."""
    for start, end in spells.get(iso3, []):
        if (start is None or year >= start) and (end is None or year <= end):
            return True
    return False


def _badea_in_mandate(iso3: str, year: int, au: dict, arab_league: dict) -> bool:
    is_au = _in_closed_list(iso3, year, au)
    not_arab_league = not _in_closed_list(iso3, year, arab_league)
    return is_au and not_arab_league


def _eib_in_mandate(iso3: str, year: int, eu_membership: dict, elm_spells: dict) -> bool | None:
    if _in_closed_list(iso3, year, eu_membership):
        return True
    rows = elm_spells.get(iso3)
    if not rows:
        return None  # never in any ELM regime's own annex -- unknown, not a guessed False
    for start, end in rows:
        if (start is None or year >= start) and (end is None or year <= end):
            return True
    return None  # outside every regime's dated spell for this country -- see module docstring


def _ebrd_in_mandate(
    iso3: str, year: int, mandate_spells: dict, membership_evidence: dict[tuple[str, str], dict] | None,
    non_regional_shareholders: set[tuple[str, str]] | None = None,
) -> bool | None:
    rows = mandate_spells.get(iso3)
    if rows:
        for start, end in rows:
            if (start is None or year >= start) and (end is None or year <= end):
                return True
            if end is not None and year > end:
                return False  # confidently after a closed spell (e.g. a later cohort's own window)
        return None  # before the formal start date -- see module docstring: not a confident False
    # A confirmed non-regional/donor-only shareholder (2026-10-02) -- never a
    # country of operations, regardless of how long ago it joined as a
    # shareholder. See recipient.py's module docstring and docs/coding_
    # decisions.md, 2026-10-02.
    non_regional = (
        non_regional_shareholders if non_regional_shareholders is not None
        else recipient.load_non_regional_shareholders()
    )
    if ("EBRD", iso3) in non_regional:
        return False
    entry = (membership_evidence or {}).get(("EBRD", iso3))
    if entry and entry.get("accession_year") is not None:
        return year >= entry["accession_year"]
    return None


def in_mandate(
    bank: str,
    iso3: str,
    year: int,
    c_basis: dict[str, str] | None = None,
    b_basis: dict[str, str] | None = None,
    recipient_status: dict[tuple[str, str], bool | None] | None = None,
    membership_evidence: dict[tuple[str, str], dict] | None = None,
    au_membership: dict | None = None,
    arab_league_membership: dict | None = None,
    eu_membership: dict | None = None,
    ebrd_mandate_spells: dict | None = None,
    eib_mandate_spells: dict | None = None,
    non_regional_shareholders: set[tuple[str, str]] | None = None,
) -> bool | None:
    basis = (c_basis if c_basis is not None else recipient.load_c_basis()).get(bank)
    if basis == "trivial_region":
        return recipient.is_recipient(bank, iso3, year, b_basis, recipient_status, membership_evidence,
                                       non_regional_shareholders)
    if basis == "spell_based":
        if bank == "EIB":
            eu = eu_membership if eu_membership is not None else load_eu_membership()
            elm = eib_mandate_spells if eib_mandate_spells is not None else load_mandate_spells("EIB")
            return _eib_in_mandate(iso3, year, eu, elm)
        if bank == "EBRD":
            spells = ebrd_mandate_spells if ebrd_mandate_spells is not None else load_mandate_spells("EBRD")
            return _ebrd_in_mandate(iso3, year, spells, membership_evidence, non_regional_shareholders)
        return None
    if basis == "computed":
        if bank == "BADEA":
            au = au_membership if au_membership is not None else load_au_membership()
            arab_league = arab_league_membership if arab_league_membership is not None else load_arab_league_membership()
            return _badea_in_mandate(iso3, year, au, arab_league)
        return None
    return None
