"""Seed data/manual/mandate_spells.csv with EIB's second, non-EU-non-ELM
geographic mandate: the ACP/Cotonou instrument and the Overseas Countries and
Territories (OCT) association.

**Why this exists** (docs/coding_decisions.md, 2026-09-27): after
`scripts/seed_mandate_spells_eib.py` built the External Lending Mandate (ELM)
regimes, 418 EIB dyad-years with real observed lending still showed
`in_mandate = None` (`check_revealed.py`'s "not yet coded"). The user's own
research note (`data/manual/EIB eligibility documents/EIB eligibility
caviat.rtf`) had already flagged exactly this: "ACP/Cotonou lending, OCT
operations, pre-accession instruments and some own-risk facilities operated
under other legal bases [than the ELM]." Checking the actual 418 countries
confirmed it -- the overwhelming majority are African, Caribbean and Pacific
states (Kenya, Zambia, Nigeria, Senegal, ... 75 distinct countries in all)
plus a handful of French/Dutch/Danish Overseas Countries and Territories
(French Polynesia, New Caledonia, Sint Maarten, Greenland).

**Two country lists, each its own legal basis, recorded with its own
`basis` value so the two never get confused with the ELM or each other**:

1. **`acp_cotonou`**: the Cotonou Partnership Agreement (signed June 2000,
   entered into force 1 April 2003), extended to 31 October 2023, succeeded
   by the Samoa Agreement (OACPS-EU Partnership Agreement, text agreed April
   2021, signing began November 2023). Covers the ACP states -- confirmed
   list live via the current OACPS roster (oacps.org / Wikipedia,
   "Organisation of African, Caribbean and Pacific States") -- **except**:
   - **Cuba**, an OACPS member but never a Cotonou signatory (confirmed).
   - **South Africa**, which has its own dedicated line and ceiling in every
     ELM decision this project already parsed (2000/24/EC, 2006/1016/EC,
     2014/466/EU) under a separate Trade, Development and Cooperation
     Agreement, not full Cotonou membership -- already covered by the ELM
     track, not duplicated here.
   Two accession dates are dated specifically (not defaulted to 2003):
   **South Sudan** (joined ACP 2011, on independence) and **Timor-Leste**
   (a more recent OACPS joiner -- its own 2000/24/EC-era ELM Asia listing
   already covers it from 2007 on regardless, so this row is mostly
   redundant insurance, not the only source). Every other listed country
   gets 2003-2023 flat, then carried forward open-ended under the Samoa
   Agreement (2023+) as an approximation, the same "no fixed annex, coverage
   didn't narrow" reasoning `seed_mandate_spells_eib.py` already applied to
   the ELM's own 2021+ regime.
2. **`oct_association`**: the Overseas Countries and Territories Association
   (continuously in force across the whole study window under successive
   Council Decisions -- 2001/822/EC, 2013/755/EU, 2021/1764/EU -- a
   continuity, not four separate regimes the way the ELM had real gaps
   between decisions). 13 OCTs are linked to France, the Netherlands and
   Denmark (international-partnerships.ec.europa.eu); only those with a
   distinct ISO-3 code this project's country codelist resolves are added
   (French Polynesia, New Caledonia, Aruba, Curaçao, Greenland) -- Saint
   Barthélemy resolves too and is included; Saint Pierre and Miquelon,
   Wallis and Futuna, the French Southern and Antarctic Territories, and the
   Dutch Caribbean municipalities (Bonaire, Saba, Sint Eustatius) and Sint
   Maarten do not resolve via `iso3_from_name` and are left out rather than
   guessed -- Sint Maarten specifically still shows 2 "not yet coded" rows
   because of this; its real ISO-3 code (SXM) is added directly since the
   scraper's own project data already uses it, without relying on name
   resolution.

**Explicitly not modeled here**: the caveat note's third category, EIB
"own-risk" lending (no EU budget guarantee, no country-list mandate at all,
case-by-case Board approval) -- this explains the *other* structural share of
the 418 gap rows that neither list above closes: Norway, Switzerland,
Andorra, and post-2018 Iceland/Israel/Chile (removed from the ELM, not
restored). There is no country list to encode for this category; it is left
`in_mandate = None`, correctly, and those dyad-years stay in the panel only
via `eligibility_basis = revealed`.

Usage:  python3 scripts/seed_mandate_spells_eib_acp.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import MANUAL_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

MANDATE_SPELLS_CSV = MANUAL_DIR / "mandate_spells.csv"

SOURCE_ACP = ("Cotonou Partnership Agreement (signed 06/2000, in force 1 April 2003, extended to 31 October 2023) "
              "and its OACPS membership roster (oacps.org, cross-checked against Wikipedia's "
              "\"Organisation of African, Caribbean and Pacific States\"), researched live this session; "
              "2023+ is the Samoa Agreement, approximated as a continuation -- see this script's docstring")
SOURCE_OCT = ("Overseas Countries and Territories Association, continuous under Council Decisions 2001/822/EC, "
              "2013/755/EU and 2021/1764/EU (international-partnerships.ec.europa.eu/countries/"
              "overseas-countries-and-territories_en), researched live this session")

BASIS_ACP = "acp_cotonou"
BASIS_OCT = "oct_association"

# Every OACPS member except Cuba (never ratified Cotonou) and South Africa
# (its own ELM line, a different agreement -- see docstring). Two members
# get their own accession year instead of the flat 2003 start.
_ACP_FLAT_2003 = [
    "Angola", "Antigua and Barbuda", "Bahamas", "Barbados", "Belize", "Benin", "Botswana",
    "Burkina Faso", "Burundi", "Cameroon", "Cape Verde", "Central African Republic", "Chad",
    "Comoros", "Congo", "Congo, Dem. Rep.", "Cote d'Ivoire", "Djibouti", "Dominica",
    "Dominican Republic", "Equatorial Guinea", "Eritrea", "Eswatini", "Ethiopia", "Fiji",
    "Gabon", "Gambia", "Ghana", "Grenada", "Guinea", "Guinea-Bissau", "Guyana", "Haiti",
    "Jamaica", "Kenya", "Kiribati", "Lesotho", "Liberia", "Madagascar", "Malawi", "Mali",
    "Marshall Islands", "Mauritania", "Mauritius", "Micronesia (Federated States of)", "Mozambique",
    "Namibia", "Nauru", "Niger", "Nigeria", "Niue", "Palau", "Papua New Guinea", "Rwanda",
    "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa",
    "Sao Tome and Principe", "Senegal", "Seychelles", "Sierra Leone", "Solomon Islands",
    "Somalia", "Sudan", "Suriname", "Tanzania", "Togo", "Tonga", "Trinidad and Tobago",
    "Tuvalu", "Uganda", "Vanuatu", "Zambia", "Zimbabwe", "Cook Islands",
]
_ACP_SOUTH_SUDAN_FROM_2011 = "South Sudan"
_ACP_TIMOR_LESTE_FROM_2003 = "Timor-Leste"  # OACPS Pacific member; also covered via the ELM Asia list from 2007

# OCT territories that resolve via iso3_from_name.
_OCT_NAMES = ["French Polynesia", "New Caledonia", "Aruba", "Curaçao", "Greenland", "Saint Barthélemy"]
# Real ISO-3 codes added directly (name resolution fails for these small
# territories, but the scraper's own project data already uses these codes).
_OCT_DIRECT_ISO3 = {"SXM": "Sint Maarten"}


def _resolve(name: str) -> str:
    iso3 = iso3_from_name(name)
    if not iso3:
        raise SystemExit(f"{name!r} did not resolve to an ISO-3 code -- fix the name and re-run.")
    return iso3


def build_rows() -> list[dict]:
    rows: list[dict] = []
    for name in _ACP_FLAT_2003:
        rows.append({
            "bank": "EIB", "iso3": _resolve(name), "basis": BASIS_ACP,
            "start_year": "2003", "end_year": "", "source": SOURCE_ACP, "note": "",
        })
    rows.append({
        "bank": "EIB", "iso3": _resolve(_ACP_SOUTH_SUDAN_FROM_2011), "basis": BASIS_ACP,
        "start_year": "2011", "end_year": "", "source": SOURCE_ACP,
        "note": "Joined ACP on independence (2011), not the flat 2003 start.",
    })
    rows.append({
        "bank": "EIB", "iso3": _resolve(_ACP_TIMOR_LESTE_FROM_2003), "basis": BASIS_ACP,
        "start_year": "2003", "end_year": "", "source": SOURCE_ACP,
        "note": "OACPS Pacific member; exact accession year within 2003-2023 not independently dated here.",
    })
    for name in _OCT_NAMES:
        rows.append({
            "bank": "EIB", "iso3": _resolve(name), "basis": BASIS_OCT,
            "start_year": "2000", "end_year": "", "source": SOURCE_OCT, "note": "",
        })
    for iso3, name in _OCT_DIRECT_ISO3.items():
        rows.append({
            "bank": "EIB", "iso3": iso3, "basis": BASIS_OCT,
            "start_year": "2000", "end_year": "", "source": SOURCE_OCT,
            "note": f"{name}; iso3 given directly (does not resolve via iso3_from_name).",
        })
    return rows


def main() -> int:
    existing = read_csv(MANDATE_SPELLS_CSV) if MANDATE_SPELLS_CSV.is_file() else []
    kept = [row for row in existing if not (row.get("bank") == "EIB" and row.get("basis") in (BASIS_ACP, BASIS_OCT))]
    new_rows = build_rows()
    combined = kept + new_rows
    write_csv(MANDATE_SPELLS_CSV, ["bank", "iso3", "basis", "start_year", "end_year", "source", "note"], combined)
    print(f"{len(new_rows)} EIB/{BASIS_ACP}+{BASIS_OCT} rows ({len(kept)} other rows kept) -> {MANDATE_SPELLS_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
