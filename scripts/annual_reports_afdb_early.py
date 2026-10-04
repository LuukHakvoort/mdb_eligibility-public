"""AfDB's capital share and voting power per member at 31 December 2002, 2003 and 2004,
from the plain-text "Statement of Subscriptions to the Capital Stock and Voting Power(s)"
in the annual reports (Information Statements) AfDB filed on EDGAR in Dec 2003, Aug 2004 and
Aug 2005. annual_reports_afdb_sec.py reads the 2005+ filings, which are HTML tables; these
three are fixed-width text whose one table is split into 3-4 side-by-side blocks.

Per member: total shares and "% of total" (capital) and number of votes and "voting
power" (each member holds 625 votes plus one per share). Both percentages are recomputed
from the counts and checked against the printed GRAND TOTAL rows.

Usage:  python3 scripts/annual_reports_afdb_early.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, REPO, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402
from annual_reports import fetch  # noqa: E402

TARGET = EXTRACTED_DIR / "shares_afdb_early.csv"
FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

FILINGS = {
    2002: "https://www.sec.gov/Archives/edgar/data/785677/000100515003002008/annlrpt.txt",
    2003: "https://www.sec.gov/Archives/edgar/data/785677/000114523604000037/d2986.txt",
    2004: "https://www.sec.gov/Archives/edgar/data/785677/000116923205004110/globalinformationstatement.txt",
}
_NAME_FIXUPS = {
    "CENT.AFR.REP": "Central African Republic", "DEM.REP.CONGO": "Congo, Dem. Rep.", "CONGO": "Congo, Rep.",
    "EQ.GUINEA": "Equatorial Guinea", "SAO TOME & P": "Sao Tome and Principe", "SAO TOME & P.": "Sao Tome and Principe", "SAO TOME & PRINCIPE": "Sao Tome and Principe",
    "GUINEA BISSAU": "Guinea-Bissau", "COTE D'IVOIRE": "Cote d'Ivoire", "U.K": "United Kingdom", "U.K.": "United Kingdom",
    "U.S.A": "United States", "U.S.A.": "United States", "KOREA": "Korea, Rep.", "EQ. GUINEA": "Equatorial Guinea", "NIG ER": "Niger", "KOWAIT": "Kuwait", "GAMBIA": "Gambia, The",
    "SOUTH AFRICA": "South Africa", "TANZANIA": "Tanzania",
}
_ROW = re.compile(r"^\s*(\d{1,2})\s+([A-Z][A-Z .,'&\-]*?)\s{2,}(.*\S)\s*$")
_DECIMAL3 = re.compile(r"^\d+\.\d{3}$")


def _int(token: str) -> int | None:
    token = token.replace(",", "")
    return int(token) if token.isdigit() else None


def parse(text: str):
    """{name: {"shares", "pct", "votes", "vpct"}} and the GRAND TOTAL's decimals."""

    start = re.search(r"(?i)statement of subscriptions to the capital stock and voting power", text)
    end = text.find("NOTES:", start.start()) if start else -1
    region = text[start.start(): end if end > 0 else None] if start else ""
    members: dict[str, dict] = {}
    kind = "both"
    for line in region.splitlines():
        upper = line.upper()
        if not _ROW.match(line) and ("VOTING" in upper or "% OF" in upper):
            kind = "votes" if "VOTING" in upper and "% OF" not in upper else "shares" if "% OF" in upper and "VOTING" not in upper else "both"
        row = _ROW.match(line)
        if not row:
            continue
        raw_name = re.sub(r"\s+-+$", "", row.group(2).strip())  # a leading "-" cell can glue onto the name
        name = _NAME_FIXUPS.get(raw_name, raw_name.title())
        tokens = row.group(3).split()
        decimals = [i for i, t in enumerate(tokens) if _DECIMAL3.match(t)]
        if not decimals or not (iso3_from_name(name) or iso3_from_name(name.replace("&", "and"))):
            continue
        entry = members.setdefault(name, {})
        if kind in ("shares", "both") and decimals and "shares" not in entry:
            i = decimals[0]
            if i >= 1 and _int(tokens[i - 1]):
                entry["shares"], entry["pct"] = _int(tokens[i - 1]), float(tokens[i])
        if kind in ("votes", "both"):
            i = decimals[-1]
            if i >= 1 and _int(tokens[i - 1]) and (kind == "votes" or len(decimals) > 1):
                entry["votes"], entry["vpct"] = _int(tokens[i - 1]), float(tokens[i])
    return members


def main() -> int:
    rows = []
    for year, url in FILINGS.items():
        path = fetch(url, f"sec_785677_{url.split('/')[-2]}_{url.split('/')[-1]}", expect="any", delay=0.4, timeout=120)
        members = parse(open(path, errors="replace").read())
        complete = {n: m for n, m in members.items() if len(m) == 4}
        shares = sum(m["shares"] for m in complete.values())
        votes = sum(m["votes"] for m in complete.values())
        pct = sum(m["pct"] for m in complete.values())
        vpct = sum(m["vpct"] for m in complete.values())
        print(f"{year}: {len(members)} rows read, {len(complete)} complete; printed % sum {pct:.3f} / {vpct:.3f}")
        if len(complete) != len(members) or not (99.9 <= pct <= 100.1 and 99.9 <= vpct <= 100.1):
            print("   incomplete:", sorted(set(members) - set(complete))[:12])
            continue
        for name, m in complete.items():
            iso3 = iso3_from_name(name) or iso3_from_name(name.replace("&", "and"))
            rows.append({"bank": "AfDB", "iso3": iso3, "year": year, "capital_share_pct": round(m["shares"] / shares * 100, 6),
                         "voting_power_pct": round(m["votes"] / votes * 100, 6), "source_url": url, "note": ""})
    rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, rows)
    print(f"{len(rows)} rows -> {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
