"""Seed data/manual/eu_membership.csv: EIB's in-EU Component C case
(docs/architecture.md section 3). EU accession dates are public record, not
research -- listed directly, not fetched. Only the 2004/2007/2013 accessions
and the UK's 2020 exit fall inside this project's 2002-2026 window; every
earlier accession (1958 founding six through the 1995 Austria/Finland/Sweden
round) is simply "a member for the whole window" (start_year left blank).

Usage:  python3 scripts/seed_eu_membership.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import MANUAL_DIR, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

SOURCE = "Public record (Treaty of Rome 1958; EU accession treaties 1973/1981/1986/1995/2004/2007/2013; Brexit 31 Jan 2020)"

MEMBERS_SINCE_BEFORE_WINDOW = [
    "Belgium", "France", "Germany", "Italy", "Luxembourg", "Netherlands",  # 1958
    "Denmark", "Ireland",  # 1973 (excl. UK, handled separately below)
    "Greece",  # 1981
    "Spain", "Portugal",  # 1986
    "Austria", "Finland", "Sweden",  # 1995
]

# (name, start_year) -- acceded inside the project's window.
JOINED_2004 = [
    "Cyprus", "Czechia", "Estonia", "Hungary", "Latvia", "Lithuania", "Malta",
    "Poland", "Slovakia", "Slovenia",
]
JOINED_2007 = ["Bulgaria", "Romania"]
JOINED_2013 = ["Croatia"]


def _resolve(name: str) -> str:
    iso3 = iso3_from_name(name)
    if not iso3:
        raise SystemExit(f"{name!r} did not resolve to an ISO-3 code -- fix the name and re-run.")
    return iso3


def main() -> int:
    rows = []
    for name in MEMBERS_SINCE_BEFORE_WINDOW:
        rows.append({"iso3": _resolve(name), "start_year": "", "end_year": "", "source": SOURCE, "note": ""})
    for name in JOINED_2004:
        rows.append({"iso3": _resolve(name), "start_year": "2004", "end_year": "", "source": SOURCE, "note": ""})
    for name in JOINED_2007:
        rows.append({"iso3": _resolve(name), "start_year": "2007", "end_year": "", "source": SOURCE, "note": ""})
    for name in JOINED_2013:
        rows.append({"iso3": _resolve(name), "start_year": "2013", "end_year": "", "source": SOURCE, "note": ""})
    rows.append({
        "iso3": _resolve("United Kingdom"), "start_year": "", "end_year": "2020",
        "source": SOURCE, "note": "Formally exited the EU 31 Jan 2020; transition period ran through 31 Dec 2020.",
    })

    write_csv(MANUAL_DIR / "eu_membership.csv", ["iso3", "start_year", "end_year", "source", "note"], rows)
    print(f"{len(rows)} rows -> data/manual/eu_membership.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
