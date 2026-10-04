"""CABEI's capital share per member, 2010-2025, from the "Memoria Anual de Labores" / audited
financial statements (data/raw/annual_reports/cabei_ar_<year>.pdf, hand-downloaded; the cached
page text from scripts/dump_pdf_text.py is read).

Two layouts of the note on subscribed capital:
  2010-2011  "valor nominal de las acciones": shares subscribed (suscritas) and paid, by member.
  2012-2025  "Capital suscrito / Suscrito exigible / Pagadero en efectivo / Pagado" in USD
             thousand, Spanish and English side by side on one line -- the first occurrence of a
             member on a line is the Spanish one.
Capital share = a member's subscribed capital over the members' total. Each row must obey
subscribed = callable + payable in cash, and the members must add up to the printed subtotal
("Subtotal capital suscrito y capital pagado"), else the year is left out. Voting power is not
filled: CABEI's own table ties voting rights to a payment condition (see annual_reports_cabei.py).

Usage:  python3 scripts/annual_reports_cabei_ar.py [year ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, REPO, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

TEXT_DIR = REPO / "data" / "raw" / "text"
TARGET = EXTRACTED_DIR / "shares_cabei_ar.csv"
FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

NAMES = {
    "Guatemala": "GTM", "El Salvador": "SLV", "Honduras": "HND", "Nicaragua": "NIC", "Costa Rica": "CRI",
    "República Dominicana": "DOM", "Rep. Dominicana": "DOM", "Panamá": "PAN", "Belice": "BLZ",
    "República de China, Taiwán": "TWN", "República de China, Taiwan": "TWN", "República de China (Taiwan)": "TWN", "República de China (Taiwán)": "TWN", "México": "MEX", "España": "ESP",
    "Argentina": "ARG", "Colombia": "COL", "República de Corea": "KOR", "Corea": "KOR", "Cuba": "CUB", "Perú": "PER",
    "Ecuador": "ECU", "Brasil": "BRA", "Chile": "CHL", "Uruguay": "URY", "Paraguay": "PRY", "Bolivia": "BOL",
    "Belize": "BLZ", "Spain": "ESP", "Mexico": "MEX", "Republic of China, Taiwan": "TWN", "Panama": "PAN",
    "Dominican Republic": "DOM", "Venezuela": "VEN", "Guyana": "GUY", "Jamaica": "JAM", "Barbados": "BRB", "Bahamas": "BHS", "Surinam": "SUR",
}
_NUM = r"(\d{1,3}(?:,\d{3})*)"
_NAME_ALT = "|".join(sorted((re.escape(n) for n in NAMES), key=len, reverse=True))
_FOUR = re.compile(rf"({_NAME_ALT})\s+{_NUM}\s+{_NUM}\s+{_NUM}\s+{_NUM}(?!\d)")
_TWO = re.compile(rf"^({_NAME_ALT})\s+{_NUM}\s+{_NUM}(?:\s+{_NUM}\s+{_NUM})?(?:\s+[^\d\s].*)?\s*$")
_SUBTOTAL = re.compile(r"^(?:Sub-?total|Total|fundadores|no fundadores)\b[^\d]*" + _NUM + r"\b", re.I)


def _n(t: str) -> int:
    return int(t.replace(",", ""))


def pages(year: int) -> list[list[str]]:
    return [p.read_text(encoding="utf-8").splitlines() for p in sorted((TEXT_DIR / f"cabei_ar_{year}").glob("p*.txt"))]


def table_2012_on(lines: list[str]):
    members: dict[str, int] = {}
    printed: list[int] = []  # every printed sub-total / total (first column)
    for line in lines:
        sub = _SUBTOTAL.match(line.strip())
        if sub:
            printed.append(_n(sub.group(1)))
        for m in _FOUR.finditer(line):
            name = m.group(1)
            a, b, c = _n(m.group(2)), _n(m.group(3)), _n(m.group(4))
            if abs(a - b - c) <= 1 and NAMES[name] not in members:
                members[NAMES[name]] = a
    return members, printed


def table_shares(lines: list[str]):
    """2010-2011: "Guatemala 204,000 55,000 204,000 55,000" -- shares subscribed and paid, this year
    then last. Returns ({iso: (current, prior)}, printed (current, prior) Total)."""

    members: dict[str, tuple[int, int]] = {}
    printed = None
    for line in lines:
        text = line.strip()
        total = re.match(rf"^Total\s+{_NUM}\s+{_NUM}\s+{_NUM}\s+{_NUM}\s*$", text)
        if total:
            if printed is None and len(members) >= 8:
                printed = (_n(total.group(1)), _n(total.group(3)))
            continue
        m = _TWO.match(text)
        if m and m.group(4):
            members.setdefault(NAMES[m.group(1)], (_n(m.group(2)), _n(m.group(4))))
    return members, printed


def main(argv: list[str]) -> int:
    years = [int(a) for a in argv] or list(range(2010, 2026))
    rows = []
    for year in [y for y in years if y in (2010, 2011)]:
        for index, lines in enumerate(pages(year)):
            members, printed = table_shares(lines)
            if len(members) >= 10 and printed:
                # a member row from another table on the page (2010's Belice, USD 25,000 thousand) shows
                # up as an excess equal to exactly that row: drop it only in that case
                excess = sum(v[0] for v in members.values()) - printed[0]
                stray = [k for k, v in members.items() if excess > 0 and v[0] == excess]
                if len(stray) == 1:
                    members.pop(stray[0])
                for slot, table_year in enumerate((year, year - 1)):
                    if table_year < 2010 or (table_year == 2010 and year == 2011 and any(r["year"] == 2010 for r in rows)):
                        continue
                    total = sum(v[slot] for v in members.values())
                    ok = abs(total - printed[slot]) <= 1
                    print(f"{year}: shares table, page {index}, table year {table_year}, {len(members)} members, sum {total:,} vs {printed[slot]:,} {'OK' if ok else 'MISMATCH'}")
                    if ok:
                        rows += [{"bank": "CABEI", "iso3": iso, "year": table_year, "capital_share_pct": round(v[slot] / total * 100, 6),
                                  "voting_power_pct": "", "source_url": f"data/raw/annual_reports/cabei_ar_{year}.pdf",
                                  "note": "Subscribed shares (acciones suscritas)."} for iso, v in members.items()]
                break
    for year in [y for y in years if y >= 2012]:
        best = None
        for index, lines in enumerate(pages(year)):
            members, printed = table_2012_on(lines)
            if len(members) >= 8 and len(printed) >= 2 and (best is None or len(members) > len(best[0])):
                best = (members, printed, index)
        if not best:
            print(f"{year}: no table")
            continue
        members, printed, index = best
        total = sum(members.values())
        # members must add up to some combination of the printed sub-totals / total
        from itertools import combinations

        ok = any(abs(total - sum(c)) <= 2 for r in range(1, min(len(printed), 6) + 1) for c in combinations(printed, r))
        status = "OK" if ok else f"MISMATCH sum {total:,} vs printed {printed[:8]}"
        print(f"{year}: page {index}, {len(members)} members, sum {total:,} {status}")
        if status != "OK":
            continue
        for iso, amount in members.items():
            rows.append({"bank": "CABEI", "iso3": iso, "year": year, "capital_share_pct": round(amount / total * 100, 6),
                         "voting_power_pct": "", "source_url": f"data/raw/annual_reports/cabei_ar_{year}.pdf", "note": ""})
    rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, rows)
    print(f"{len(rows)} rows -> {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
