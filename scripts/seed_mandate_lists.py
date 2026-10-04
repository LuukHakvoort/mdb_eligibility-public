"""Seed data/manual/au_membership.csv and data/manual/arab_league_membership.csv:
architecture.md section 3's Component C inputs for BADEA's computed rule
("AU member AND NOT Arab League member") and AIIB's computed rule (member
AND NOT high-income, via OGHIST -- built separately, components/mandate.py
still returns None for AIIB's `computed` c_basis until that combination is
wired in).

**AU membership**: the AU (est. 2002, continuing the OAU, est. 1963) had
already absorbed virtually every African state before this project's 2002
window even starts -- so rather than research 55 individual accession dates
(most of which predate 2002 and are irrelevant to a start_year within this
project's window), this list defaults every one of the 55 current AU members
to "member for the whole 2002-2026 window" (start_year left blank -- ongoing
since before the window), with the two real, dated exceptions researched
directly: **South Sudan** (didn't exist as a country until 2011) and
**Morocco** (withdrew from the OAU in 1984 over Western Sahara's admission,
rejoined the AU 30 January 2017 -- not a member 2002-2016).

**Arab League membership**: all 22 current members plus a spell for each of
the three suspensions found live -- Syria (16 Nov 2011 - 7 May 2023), Egypt
(26 Mar 1979 - 23 May 1989, entirely before this project's window), Libya
(22 Feb 2011 - 25 Aug 2011, a single-year blip). North Yemen/South Yemen are
collapsed to YEM (unified 1990, well before this project's window).

Usage:  python3 scripts/seed_mandate_lists.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import MANUAL_DIR, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

AU_SOURCE = "https://en.wikipedia.org/wiki/Member_states_of_the_African_Union"
AU_EXCEPTION_SOURCE = "https://en.wikipedia.org/wiki/List_of_African_Union_member_states_by_accession"

# The 55 current AU members (CLAUDE.md's own bank-membership research already
# resolves most of these names; South Sudan and Morocco are excluded here and
# added separately below with their real dated spells).
AU_MEMBERS_MINUS_EXCEPTIONS = [
    "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
    "Cameroon", "Cabo Verde", "Central African Republic", "Chad", "Comoros",
    "Congo, Dem. Rep.", "Congo", "Djibouti", "Egypt", "Equatorial Guinea",
    "Eritrea", "Eswatini", "Ethiopia", "Gabon", "Gambia", "Ghana", "Guinea",
    "Cote d'Ivoire", "Kenya", "Lesotho", "Liberia", "Libya", "Madagascar",
    "Malawi", "Mali", "Mauritania", "Mauritius", "Mozambique", "Namibia",
    "Niger", "Nigeria", "Rwanda", "Sao Tome and Principe", "Senegal",
    "Seychelles", "Sierra Leone", "Somalia", "South Africa", "Sudan",
    "Tanzania", "Togo", "Tunisia", "Uganda", "Zambia", "Zimbabwe",
    "Guinea-Bissau",
]

ARAB_LEAGUE_SOURCE = "https://en.wikipedia.org/wiki/Member_states_of_the_Arab_League"
# name -> (start_year, note)
ARAB_LEAGUE_FOUNDING = {
    "Egypt": 1945, "Iraq": 1945, "Lebanon": 1945, "Saudi Arabia": 1945,
    "Syria": 1945, "Jordan": 1945, "Yemen": 1945, "Libya": 1953,
    "Sudan": 1956, "Morocco": 1958, "Tunisia": 1958, "Kuwait": 1961,
    "Algeria": 1962, "United Arab Emirates": 1971, "Oman": 1971,
    "Qatar": 1971, "Bahrain": 1971, "Mauritania": 1973, "Somalia": 1974,
    "Djibouti": 1977, "Comoros": 1993,
}
# Palestine is excluded: not a single ISO-3 sovereign-state code in this
# repo's codelist, and not an AU/BADEA-relevant case either way.

# (iso3, start_year, end_year, note) -- dated suspension spells.
ARAB_LEAGUE_SUSPENSIONS = [
    ("SYR", 2011, 2023, "Suspended 16 Nov 2011 (civilian-protester violence); readmitted 7 May 2023."),
    ("EGY", 1979, 1989, "Suspended 26 Mar 1979 (Egypt-Israel peace treaty); readmitted 23 May 1989. Entirely before this project's 2002 window."),
    ("LBY", 2011, 2011, "Suspended 22 Feb 2011 (civil conflict); readmitted 25 Aug 2011."),
]


def _resolve(name: str) -> str:
    iso3 = iso3_from_name(name)
    if not iso3:
        raise SystemExit(f"{name!r} did not resolve to an ISO-3 code -- fix the name and re-run.")
    return iso3


def build_au() -> list[dict]:
    rows = []
    for name in AU_MEMBERS_MINUS_EXCEPTIONS:
        rows.append({
            "iso3": _resolve(name), "start_year": "", "end_year": "",
            "source": AU_SOURCE, "note": "AU/OAU member since well before this project's 2002 window.",
        })
    rows.append({
        "iso3": "SSD", "start_year": "2011", "end_year": "",
        "source": AU_EXCEPTION_SOURCE, "note": "Did not exist as a country until independence in 2011.",
    })
    rows.append({
        "iso3": "MAR", "start_year": "2017", "end_year": "",
        "source": AU_EXCEPTION_SOURCE,
        "note": "Withdrew from the OAU in 1984 over the Sahrawi Arab Democratic Republic's admission; "
                "rejoined the AU 30 January 2017. Not a member 2002-2016.",
    })
    return rows


def build_arab_league() -> list[dict]:
    rows = []
    suspended_iso3 = {row[0] for row in ARAB_LEAGUE_SUSPENSIONS}
    for name, start_year in ARAB_LEAGUE_FOUNDING.items():
        iso3 = _resolve(name)
        if iso3 in suspended_iso3:
            continue  # written as explicit spells below instead
        rows.append({
            "iso3": iso3, "start_year": str(start_year), "end_year": "",
            "source": ARAB_LEAGUE_SOURCE, "note": "",
        })
    for iso3, start, end, note in ARAB_LEAGUE_SUSPENSIONS:
        founding_year = next(y for n, y in ARAB_LEAGUE_FOUNDING.items() if _resolve(n) == iso3)
        rows.append({
            "iso3": iso3, "start_year": str(founding_year), "end_year": str(start - 1),
            "source": ARAB_LEAGUE_SOURCE, "note": note,
        })
        rows.append({
            "iso3": iso3, "start_year": str(end + 1), "end_year": "",
            "source": ARAB_LEAGUE_SOURCE, "note": f"Reinstated after the {start}-{end} suspension.",
        })
    return rows


def main() -> int:
    au_rows = build_au()
    write_csv(MANUAL_DIR / "au_membership.csv", ["iso3", "start_year", "end_year", "source", "note"], au_rows)
    print(f"{len(au_rows)} rows -> data/manual/au_membership.csv")

    al_rows = build_arab_league()
    write_csv(MANUAL_DIR / "arab_league_membership.csv", ["iso3", "start_year", "end_year", "source", "note"], al_rows)
    print(f"{len(al_rows)} rows -> data/manual/arab_league_membership.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
