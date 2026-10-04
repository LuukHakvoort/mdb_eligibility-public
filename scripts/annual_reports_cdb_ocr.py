"""CDB years whose subscription table is a scanned image (rotated, so OCR'd upright):
FY2014 (annual report pages 96-98) and FY2003 (page 64). Same table as annual_reports_cdb_ar.py.

OCR misreads digits ("18,354" for 48,354), so each member's share count is rebuilt from
three printed figures that must agree: shares x par value = subscribed capital (par =
USD 6.0317 per share, constant across the clean tables), and shares = % of total x
total shares. Votes are shares + 150 per member (the five UK territories share one
member's 150 votes: bloc = their shares + 150), a rule the clean tables obey on every
row -- and the rebuilt sums must equal the printed Sub-total for shares AND votes, or
the year is rejected.

Usage:  python3 scripts/annual_reports_cdb_ocr.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ocr  # noqa: E402
from _panel import EXTRACTED_DIR, REPO, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402
from annual_reports_cdb_ar import FIELDS, _clean  # noqa: E402

PAR = 6.03177  # USD thousand per share
BLOC = {"Anguilla", "Montserrat", "British Virgin Islands", "Cayman Islands", "Turks and Caicos Islands"}
# year -> (pdf, page range to OCR)
DOCS = {2014: ("cdb_2014.pdf", range(94, 101)), 2003: ("cdb_2003.pdf", range(64, 65))}
TARGET = EXTRACTED_DIR / "shares_cdb_ocr.csv"

_NUM = re.compile(r"\d[\d,.]*")


def _to_int(token: str) -> int | None:
    digits = token.replace(",", "").replace(".", "")
    return int(digits) if digits.isdigit() else None


_MEMBERS = ["Jamaica", "Trinidad and Tobago", "Bahamas", "Guyana", "Colombia", "Mexico", "Venezuela", "Barbados", "Suriname",
            "Belize", "Dominica", "Grenada", "Saint Lucia", "Saint Vincent and the Grenadines", "Antigua and Barbuda",
            "Saint Kitts and Nevis", "Anguilla", "Montserrat", "British Virgin Islands", "Cayman Islands",
            "Turks and Caicos Islands", "Haiti", "Brazil", "Canada", "United Kingdom", "Italy", "Germany", "China"]


def _resolve(raw: str) -> str | None:
    """A member name, tolerating OCR slips ("Venemela", "Tally")."""

    import difflib

    name = _clean(raw)
    if iso3_from_name(name):
        return name
    close = difflib.get_close_matches(name, _MEMBERS, n=1, cutoff=0.7)
    return close[0] if close else None


def _rows(lines: list[str]) -> tuple[list[dict], int | None, int | None]:
    members: dict[str, dict] = {}
    subtotal_shares = subtotal_votes = None
    for line in lines:
        line = line.replace("$", "").strip()
        sub = re.search(r"sub-?total\s+([\d,]+)\s+100\.0*\s+[\d,._ ]+?[\s|]+([\d,]+)\s+100\.0*", line, re.I)
        if sub:
            subtotal_shares, subtotal_votes = _to_int(sub.group(1)), _to_int(sub.group(2))
            break  # "Additional subscriptions" (shares-less rows) follow the sub-total
        match = re.match(r"^([A-Za-z][A-Za-z .,'&]*?)(?:\s*/\s*\d)?\s+(\d\S*)\s+(\d{1,2}[.,°']\d{2}|\d{3,4})\s+(\S+)", line)
        if not match:
            continue
        name = _resolve(match.group(1))
        if not name:
            continue
        raw_pct = re.sub(r"[,°']", ".", match.group(3))
        pct = float(raw_pct) if "." in raw_pct else float(raw_pct) / 100
        members.setdefault(name, {"name": name, "s0": _to_int(match.group(2)), "pct": pct, "cap": _to_int(match.group(4))})
    return list(members.values()), subtotal_shares, subtotal_votes


def rebuild(members: list[dict], total: int, known: set[int]) -> list[dict]:
    """Share counts from the figures that must agree (see the module docstring).
    `known` = share counts printed in the adjacent clean years' tables, which the
    OCR'd count may be matched against when the capital column is unreadable."""

    for member in members:
        s0, cap, pct = member["s0"], member["cap"], member["pct"]
        if s0 and cap and abs(s0 * PAR - cap) < 3.0:
            member["shares"] = s0
        elif s0 in known and abs(s0 / total * 100 - pct) <= 0.1:
            member["shares"] = s0
        elif cap and abs(round(cap / PAR) * PAR - cap) < 3.0 and abs(round(cap / PAR) / total * 100 - pct) <= 0.1:
            member["shares"] = round(cap / PAR)
        else:
            member["shares"] = round(pct * total / 100)
            member["weak"] = True
    return members


def _known_shares() -> set[int]:
    """Share counts printed (clean text layer) in other years' tables."""

    from annual_reports_cdb_ar import tables_for

    known: set[int] = set()
    for doc_year in (2012, 2013, 2016, 2018):
        for table in tables_for(doc_year).values():
            known |= {row[1] for row in table}
    return known


def main() -> int:
    all_rows = []
    for year, (pdf_name, pages) in DOCS.items():
        path = REPO / "data" / "raw" / "annual_reports" / pdf_name
        lines: list[str] = []
        for index in pages:
            text = ocr.page_text_upright(path, index, "Voting")
            page_lines = text.splitlines()
            if any(line.strip() == str(year - 1) for line in page_lines):
                break  # the prior-year comparative table starts here
            if "Jamaica" in text or (lines and "Canada" in text):
                lines += page_lines
        members, sub_shares, sub_votes = _rows(lines)
        if not members or not sub_shares:
            print(f"{year}: table not found by OCR ({len(members)} rows, sub-total {sub_shares})")
            continue
        members = rebuild(members, sub_shares, _known_shares())
        total_shares = sum(m["shares"] for m in members)
        bloc = [m for m in members if m["name"] in BLOC]
        votes = {m["name"]: m["shares"] + 150 for m in members if m["name"] not in BLOC}
        bloc_votes = sum(m["shares"] for m in bloc) + 150
        total_votes = sum(votes.values()) + bloc_votes
        ok = total_shares == sub_shares and total_votes == sub_votes
        print(f"{year}: {len(members)} members, shares {total_shares:,} vs printed {sub_shares:,}, votes {total_votes:,} vs {sub_votes}: {'OK' if ok else 'REJECTED'}")
        if not ok:
            continue
        for m in members:
            voting = round((votes.get(m["name"]) or (bloc_votes if m["name"] == "British Virgin Islands" else 0)) / total_votes * 100, 6) or ""
            all_rows.append({"bank": "CDB", "iso3": iso3_from_name(m["name"]), "year": year,
                             "capital_share_pct": round(m["shares"] / total_shares * 100, 6), "voting_power_pct": voting,
                             "source_url": f"data/raw/annual_reports/{pdf_name}",
                             "note": "OCR of a scanned table; share counts rebuilt from capital/par and % and reconciled to the printed Sub-total (shares and votes)."
                                     + (" UK-territory bloc: pooled votes shown on the British Virgin Islands row only." if m["name"] in BLOC else "")})
    all_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, all_rows)
    print(f"{len(all_rows)} rows -> {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
