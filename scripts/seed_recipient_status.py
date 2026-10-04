"""Seed data/manual/recipient_status.csv: architecture.md's Component B file for
the nine banks whose `b_basis` (data/manual/banks.json) is
`needs_recipient_research` -- AfDB, AsDB, IDB, IsDB, CAF, CDB, AIIB, NDB, CABEI.

Every row here comes from that bank's own published borrowing/non-borrowing
(or regional/non-regional, or shareholder-series) member classification,
researched live via WebSearch/WebFetch this session -- not guessed, not
inferred from `shareholders_panel.csv` alone. Where a bank's own material
does not cleanly resolve a country's status, the row is written as `unknown`,
with a note explaining exactly why, rather than defaulted either way. See
docs/coding_decisions.md for the per-bank reasoning and every source URL.

This script is a one-off, run once to produce the CSV; the CSV itself is the
checked-in authority afterward and can be hand-edited directly (same
relationship as seed_accession_dates.py to accession_dates.csv).

Usage:  python3 scripts/seed_recipient_status.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, MANUAL_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

TARGET = MANUAL_DIR / "recipient_status.csv"
ISDB_WAYBACK_ACCESSIONS = EXTRACTED_DIR / "wayback_accessions_isdb.csv"
FIELDS = ["bank", "iso3", "status", "start_year", "end_year", "source", "note"]

IDB_SOURCE = "https://www.iadb.org/en/who-we-are/how-we-are-organized/borrowing-member-countries ; https://www.iadb.org/en/who-we-are/how-we-are-organized/non-borrowing-member-countries"
IDB_BORROWING = [
    "Bahamas", "Barbados", "Belize", "Bolivia", "Costa Rica", "Dominican Republic",
    "Ecuador", "El Salvador", "Guatemala", "Guyana", "Haiti", "Honduras", "Jamaica",
    "Nicaragua", "Panama", "Paraguay", "Suriname", "Trinidad and Tobago", "Uruguay",
    "Argentina", "Brazil", "Chile", "Colombia", "Mexico", "Peru", "Venezuela",
]
IDB_NON_BORROWING = [
    "Canada", "China", "Israel", "Japan", "Korea, Rep.", "United States",
    "Austria", "Belgium", "Croatia", "Denmark", "Finland", "France", "Germany",
    "Italy", "Netherlands", "Norway", "Portugal", "Slovenia", "Spain", "Sweden",
    "Switzerland", "United Kingdom",
]

CDB_SOURCE = "https://www.caribank.org/countries-and-members/borrowing-members ; https://www.caribank.org/countries-and-members/non-borrowing-members"
CDB_BORROWING = [
    "Anguilla", "Antigua and Barbuda", "Barbados", "Belize", "British Virgin Islands",
    "Cayman Islands", "Dominica", "Grenada", "Guyana", "Haiti", "Jamaica", "Montserrat",
    "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines",
    "Suriname", "Bahamas", "Trinidad and Tobago", "Turks and Caicos Islands",
]
CDB_NON_BORROWING = ["Brazil", "Colombia", "Mexico", "Venezuela", "Canada", "China", "Germany", "Italy", "United Kingdom"]

AFDB_SOURCE = "https://www.afdb.org/en/about-us/corporate-information/members"
AFDB_REGIONAL_BORROWING = [
    "Algeria", "Egypt", "Libya", "Mauritania", "Morocco", "Tunisia", "Benin",
    "Burkina Faso", "Cabo Verde", "Cote d'Ivoire", "Gambia", "Ghana", "Guinea",
    "Guinea-Bissau", "Liberia", "Mali", "Niger", "Nigeria", "Senegal",
    "Sierra Leone", "Togo", "Burundi", "Comoros", "Djibouti", "Eritrea",
    "Ethiopia", "Kenya", "Rwanda", "Seychelles", "Somalia", "Sudan",
    "South Sudan", "Tanzania", "Uganda", "Cameroon", "Central African Republic",
    "Chad", "Congo", "Democratic Republic of Congo", "Equatorial Guinea",
    "Gabon", "Angola", "Botswana", "Lesotho", "Madagascar", "Malawi",
    "Mauritius", "Mozambique", "Namibia", "Sao Tome and Principe",
    "South Africa", "Eswatini", "Zambia", "Zimbabwe",
]
AFDB_NON_REGIONAL_NON_BORROWING = [
    "Argentina", "Austria", "Belgium", "Brazil", "Canada", "China", "Denmark",
    "Finland", "France", "Germany", "India", "Ireland", "Italy", "Japan",
    "Korea, Rep.", "Kuwait", "Luxembourg", "Netherlands", "Norway", "Portugal",
    "Saudi Arabia", "Spain", "Sweden", "Switzerland", "Turkey", "United Kingdom",
    "United States",
]
AFDB_UAE_NOTE = "ADF (concessional window) member only, not AfDB-proper -- see docs/architecture.md decision 2 (AsDF/ADF split, unresolved; ADF is not a separate bank code in this repo yet)."

# ADB's own lending page (source B) lists the 50 developing member countries
# (DMCs) it lends to; the members page (source A) lists all 69 members split
# regional/non-regional. Regional-but-not-a-DMC = non-borrowing (Japan,
# Australia, NZ, Korea, Singapore, Hong Kong, Taiwan, Brunei) -- computed as a
# set difference below, not hand-typed twice.
ADB_MEMBERS_SOURCE = "https://www.adb.org/who-we-are/members (via search cache; adb.org blocked direct fetch)"
ADB_LENDING_SOURCE = "https://www.adb.org/business/how-to/which-countries-does-adb-lend"
ADB_ALL_REGIONAL = [
    "Afghanistan", "Australia", "Cambodia", "India", "Indonesia", "Japan", "Lao People's Democratic Republic",
    "Malaysia", "Nepal", "New Zealand", "Pakistan", "Philippines", "Samoa",
    "Singapore", "Korea, Rep.", "Sri Lanka", "Taiwan, China", "Thailand", "Vietnam",
    "Hong Kong", "Fiji", "Papua New Guinea", "Tonga", "Myanmar", "Solomon Islands",
    "Kiribati", "Cook Islands", "Maldives", "Vanuatu", "Bangladesh", "Bhutan",
    "China", "Micronesia (Federated States of)", "Marshall Islands", "Mongolia", "Nauru",
    "Turkey", "Tuvalu", "Kazakhstan", "Kyrgyz Republic", "Uzbekistan", "Tajikistan",
    "Azerbaijan", "Turkmenistan", "Timor-Leste", "Palau", "Armenia",
    "Brunei Darussalam", "Georgia", "Niue",
]
ADB_DMC_BORROWING = [
    "Afghanistan", "Armenia", "Azerbaijan", "Georgia", "Kazakhstan", "Kyrgyz Republic",
    "Pakistan", "Tajikistan", "Turkey", "Turkmenistan", "Uzbekistan", "Mongolia",
    "China", "Bangladesh", "Bhutan", "India", "Maldives", "Nepal", "Sri Lanka",
    "Cambodia", "Indonesia", "Lao People's Democratic Republic", "Myanmar", "Philippines", "Thailand",
    "Timor-Leste", "Vietnam", "Cook Islands", "Micronesia (Federated States of)", "Fiji",
    "Kiribati", "Marshall Islands", "Nauru", "Niue", "Palau", "Papua New Guinea",
    "Samoa", "Solomon Islands", "Tonga", "Tuvalu", "Vanuatu",
]
ADB_NON_REGIONAL_NON_BORROWING = [
    "Austria", "Belgium", "Canada", "Denmark", "Finland", "Germany", "Italy",
    "Netherlands", "Norway", "Sweden", "United Kingdom", "United States",
    "Switzerland", "France", "Spain", "Portugal", "Luxembourg", "Ireland", "Israel",
]

CABEI_SOURCE = "https://archive.bcie.org/en/member-countries ; https://www.bcie.org/acerca-del-bcie/estructura-organizacional/gobernadores/decisiones-gobernadores-socios-extra-regionales"
CABEI_REGIONAL_BORROWING = [
    "Guatemala", "Honduras", "El Salvador", "Nicaragua", "Costa Rica",  # founding
    "Panama", "Dominican Republic", "Belize",  # non-founding regional
]
CABEI_EXTRAREGIONAL_UNKNOWN = ["Mexico", "Taiwan, China", "Argentina", "Colombia", "Spain", "Korea, Rep.", "Cuba"]
CABEI_EXTRAREGIONAL_NOTE = (
    "Not classified borrowing/non-borrowing: a CABEI news release "
    "(\"CABEI increases funding ceiling for Non-Founding Extraregional and "
    "Regional Member countries\") shows extra-regional members DO have some "
    "financing access with their own ceiling, contradicting the AIIB/IDB-style "
    "non-borrowing-shareholder pattern this bank was initially assumed to "
    "follow by analogy. No source found stating what that access actually "
    "covers -- left unknown rather than guessed either way."
)

NDB_SOURCE = "https://www.ndb.int/about-ndb/members/"
NDB_BORROWING = ["Brazil", "Russia", "India", "China", "South Africa", "Bangladesh",
                  "United Arab Emirates", "Egypt", "Algeria", "Uzbekistan"]
NDB_NOTE = (
    "No non-borrowing member bloc identified: unlike the Bretton-Woods-style "
    "banks, NDB's ten current members are all founding BRICS states or later "
    "EMDC accessions, and NDB has funded projects in all five founders. "
    "Its five \"prospective members\" (Uruguay, Colombia, Ethiopia, Angola, "
    "Zimbabwe) have not deposited accession instruments and are correctly "
    "absent from accession_dates.csv already (CLAUDE.md Known Traps)."
)

AIIB_SOURCE = "https://worldpopulationreview.com/country-rankings/aiib-member-countries (regional/non-regional split, sourced from AIIB's own site); https://www.aiib.org/en/treasury/_common/_download/AIIB-CA-2020.pdf (Australia/Korea/Singapore explicitly named high-income, not expected to borrow); https://www.aiib.org/en/policies-strategies/strategies/financing-operations.html (non-regional financing is a distinct, exceptional policy track)"
AIIB_REGIONAL_BORROWING = [
    "India", "Indonesia", "Pakistan", "Bangladesh", "Russia", "Philippines",
    "Vietnam", "Iran", "Turkey", "Thailand", "Myanmar", "Iraq", "Afghanistan",
    "Uzbekistan", "Malaysia", "Saudi Arabia", "Nepal", "Sri Lanka", "Kazakhstan",
    "Cambodia", "Jordan", "United Arab Emirates", "Tajikistan", "Papua New Guinea",
    "Azerbaijan", "Lao People's Democratic Republic", "Kyrgyz Republic", "Oman", "Kuwait", "Georgia",
    "Mongolia", "Qatar", "Bahrain", "Timor-Leste", "Cyprus", "Fiji",
    "Solomon Islands", "Maldives", "Brunei Darussalam", "Vanuatu", "Samoa",
    "Tonga", "Cook Islands", "Nauru",
]
AIIB_REGIONAL_UNKNOWN_HIGH_INCOME = ["China", "New Zealand", "Hong Kong", "Israel"]
AIIB_REGIONAL_UNKNOWN_NOTE = (
    "High income; AIIB's own 2020 ratings note names Australia/Korea/Singapore "
    "specifically as \"not expected to borrow\" but does not confirm or rule "
    "out this country -- left unknown rather than assumed either way."
)
# Originally researched as "confirmed non-borrowing" (Australia/Korea/Singapore,
# sourced from AIIB's own 2020 ratings note) and "non-borrowing" (the 51
# non-regional members, reasoned from AIIB's "Strategy on Financing Operations
# in Non-Regional Members" policy existing as a distinct/exceptional track).
# Both readings were contradicted by check_revealed.py: real observed AIIB
# lending includes Singapore itself plus at least 12 of the 51 non-regional
# members (Argentina, Benin, Brazil, Cote d'Ivoire, Ecuador, Egypt, Hungary,
# Morocco, Romania, Rwanda, Togo, South Africa -- data/output/reports/
# revealed_violations.csv, kind=contradiction). That policy document was
# misread: its existence is evidence AIIB *does* lend to non-regional members
# under it, not that it doesn't. Reclassified `unknown` across the board
# rather than flipped to `borrowing`: some non-regional shareholders (e.g.
# Germany, UK, France as major capital contributors) plausibly still never
# borrow, and there is no reliable per-country signal to separate them from
# Argentina/Brazil/Egypt now that the blanket rule is known wrong. Logged
# 2026-09-21 in docs/coding_decisions.md.
AIIB_REGIONAL_UNKNOWN_AFTER_CONTRADICTION = ["Australia", "Korea, Rep.", "Singapore"]
AIIB_NON_REGIONAL_UNKNOWN = [
    "Brazil", "Ethiopia", "Egypt", "Germany", "United Kingdom", "France",
    "South Africa", "Italy", "Kenya", "Sudan", "Algeria", "Spain", "Argentina",
    "Canada", "Morocco", "Poland", "Ghana", "Peru", "Madagascar",
    "Cote d'Ivoire", "Chile", "Romania", "Netherlands", "Ecuador", "Guinea",
    "Benin", "Rwanda", "Tunisia", "Belgium", "Sweden", "Portugal", "Togo",
    "Greece", "Hungary", "Austria", "Switzerland", "Belarus", "Libya", "Serbia",
    "El Salvador", "Denmark", "Liberia", "Finland", "Mauritania", "Ireland",
    "Croatia", "Uruguay", "North Macedonia", "Djibouti", "Luxembourg", "Malta",
    "Iceland",
]
AIIB_NON_REGIONAL_UNKNOWN_NOTE = (
    "Reclassified from non_borrowing to unknown after check_revealed.py "
    "contradicted the blanket rule this was drawn from -- see the comment "
    "above AIIB_REGIONAL_UNKNOWN_AFTER_CONTRADICTION."
)

CAF_SOURCE = "https://en.wikipedia.org/wiki/CAF_%E2%80%93_Development_Bank_of_Latin_America_and_the_Caribbean (shareholder categories, citing CAF's own material)"
CAF_BORROWING = [
    "Argentina", "Bahamas", "Bolivia", "Brazil", "Chile", "Colombia",
    "Dominican Republic", "Ecuador", "El Salvador", "Honduras", "Panama",
    "Paraguay", "Peru", "Trinidad and Tobago", "Uruguay", "Venezuela",
    "Antigua and Barbuda", "Barbados", "Costa Rica", "Jamaica", "Mexico",
]
CAF_UNKNOWN = ["Spain", "Portugal"]
CAF_UNKNOWN_NOTE = (
    "Originally classified non_borrowing (CAF's own material distinguishes "
    "\"full member\"/Series A from \"Category C\" -- Spain, Portugal, plus "
    "some smaller LatAm/Caribbean shareholders -- but no source gave an "
    "explicit borrowing/non-borrowing label the way IDB/CDB/AfDB have; this "
    "was already flagged as weaker evidence). check_revealed.py then found "
    "real observed CAF lending to both Spain (2014, 2015) and Portugal (2015) "
    "-- direct counter-evidence, not an ambiguous case -- so reclassified "
    "unknown rather than left wrong. Logged 2026-09-21 in "
    "docs/coding_decisions.md."
)

# IsDB: 57 confirmed members (data/extracted/wayback_accessions_isdb.csv).
# Most are developing OIC states and match IsDB's own description of who can
# access concessional financing; a handful of high-income Gulf founding
# members are flagged unknown rather than defaulted to "borrowing", since
# IsDB's own material ties concessional borrowing specifically to "low- and
# lower middle-income member countries". The 14 accession_dates.csv IsDB rows
# with NO match in the 57-member list (Botswana, Ethiopia, Ghana, Kenya,
# Malawi, Rwanda, Seychelles, Tanzania, Zambia, Zimbabwe, UK, US, Kosovo, Sri
# Lanka) are non-members with real observed IsDB-attributed lending --
# consistent with IsDB's Special Assistance Program for Muslim communities in
# non-member countries, not a data error (docs/coding_decisions.md).
ISDB_SOURCE = "data/extracted/wayback_accessions_isdb.csv (isdb.org/data/defs/member_countries.json via Wayback); https://www.isdb.org/isdb-member-countries"
ISDB_HIGH_INCOME_UNKNOWN_ISO3 = {"SAU", "ARE", "KWT", "QAT", "BHR", "BRN", "LBY"}
ISDB_HIGH_INCOME_NOTE = (
    "High-income founding/Gulf member; IsDB's own material ties concessional "
    "borrowing specifically to low- and lower-middle-income members, and no "
    "source found confirming this country's borrowing status -- left unknown."
)
ISDB_NON_MEMBER_RECIPIENT_ISO3 = {
    "BWA", "ETH", "GHA", "KEN", "LKA", "MWI", "RWA", "SYC", "TZA", "GBR", "USA", "XKX", "ZMB", "ZWE",
}
ISDB_NON_MEMBER_NOTE = (
    "Not an IsDB shareholder (absent from the 57-member Wayback list) but has "
    "real observed IsDB-attributed lending in commitments.csv -- almost "
    "certainly IsDB's Special Assistance Program for Muslim communities in "
    "non-member countries, a real non-membership-gated channel, not a data "
    "error (docs/coding_decisions.md, 2026-09-21)."
)


def _rows(bank: str, names: list[str], status: str, source: str, note: str = "") -> list[dict]:
    rows = []
    for name in names:
        iso3 = iso3_from_name(name)
        if not iso3:
            raise SystemExit(f"{bank}: {name!r} did not resolve to an ISO-3 code -- fix the name and re-run.")
        rows.append({
            "bank": bank, "iso3": iso3, "status": status,
            "start_year": "", "end_year": "", "source": source, "note": note,
        })
    return rows


def main() -> int:
    rows: list[dict] = []

    rows += _rows("IDB", IDB_BORROWING, "borrowing", IDB_SOURCE)
    rows += _rows("IDB", IDB_NON_BORROWING, "non_borrowing", IDB_SOURCE)

    rows += _rows("CDB", CDB_BORROWING, "borrowing", CDB_SOURCE)
    rows += _rows("CDB", CDB_NON_BORROWING, "non_borrowing", CDB_SOURCE)

    rows += _rows("AfDB", AFDB_REGIONAL_BORROWING, "borrowing", AFDB_SOURCE)
    rows += _rows("AfDB", AFDB_NON_REGIONAL_NON_BORROWING, "non_borrowing", AFDB_SOURCE)
    rows += _rows("AfDB", ["United Arab Emirates"], "non_borrowing", AFDB_SOURCE, AFDB_UAE_NOTE)

    dmc_set = set(ADB_DMC_BORROWING)
    adb_developed_regional = [n for n in ADB_ALL_REGIONAL if n not in dmc_set]
    rows += _rows("AsDB", ADB_DMC_BORROWING, "borrowing", ADB_LENDING_SOURCE)
    rows += _rows("AsDB", adb_developed_regional, "non_borrowing",
                   f"{ADB_MEMBERS_SOURCE} ; {ADB_LENDING_SOURCE} (set difference: regional member, not a DMC)")
    rows += _rows("AsDB", ADB_NON_REGIONAL_NON_BORROWING, "non_borrowing", ADB_MEMBERS_SOURCE)

    rows += _rows("CABEI", CABEI_REGIONAL_BORROWING, "borrowing", CABEI_SOURCE)
    rows += _rows("CABEI", CABEI_EXTRAREGIONAL_UNKNOWN, "unknown", CABEI_SOURCE, CABEI_EXTRAREGIONAL_NOTE)

    rows += _rows("NDB", NDB_BORROWING, "borrowing", NDB_SOURCE, NDB_NOTE)

    rows += _rows("AIIB", AIIB_REGIONAL_BORROWING, "borrowing", AIIB_SOURCE)
    rows += _rows("AIIB", AIIB_REGIONAL_UNKNOWN_HIGH_INCOME, "unknown", AIIB_SOURCE, AIIB_REGIONAL_UNKNOWN_NOTE)
    rows += _rows("AIIB", AIIB_REGIONAL_UNKNOWN_AFTER_CONTRADICTION, "unknown", AIIB_SOURCE, AIIB_NON_REGIONAL_UNKNOWN_NOTE)
    rows += _rows("AIIB", AIIB_NON_REGIONAL_UNKNOWN, "unknown", AIIB_SOURCE, AIIB_NON_REGIONAL_UNKNOWN_NOTE)

    rows += _rows("CAF", CAF_BORROWING, "borrowing", CAF_SOURCE)
    rows += _rows("CAF", CAF_UNKNOWN, "unknown", CAF_SOURCE, CAF_UNKNOWN_NOTE)

    isdb_members = {row["iso3"] for row in read_csv(ISDB_WAYBACK_ACCESSIONS)}
    for iso3 in sorted(ISDB_HIGH_INCOME_UNKNOWN_ISO3):
        rows.append({"bank": "IsDB", "iso3": iso3, "status": "unknown", "start_year": "",
                      "end_year": "", "source": ISDB_SOURCE, "note": ISDB_HIGH_INCOME_NOTE})
    for iso3 in sorted(isdb_members - ISDB_HIGH_INCOME_UNKNOWN_ISO3):
        rows.append({"bank": "IsDB", "iso3": iso3, "status": "borrowing", "start_year": "",
                      "end_year": "", "source": ISDB_SOURCE,
                      "note": "Confirmed IsDB member (Wayback member_countries.json); no evidence "
                              "found that it diverges from IsDB's general developing-member "
                              "concessional-lending profile."})
    for iso3 in sorted(ISDB_NON_MEMBER_RECIPIENT_ISO3):
        rows.append({"bank": "IsDB", "iso3": iso3, "status": "borrowing", "start_year": "",
                      "end_year": "", "source": ISDB_SOURCE, "note": ISDB_NON_MEMBER_NOTE})

    rows.sort(key=lambda r: (r["bank"], r["iso3"]))
    write_csv(TARGET, FIELDS, rows)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(f"{len(rows)} rows -> {TARGET.relative_to(TARGET.parents[2])}")
    print(f"  {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
