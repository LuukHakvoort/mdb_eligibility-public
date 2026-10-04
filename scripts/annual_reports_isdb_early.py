"""IsDB's capital share per member for 1423H-1425H (panel years 2002-2004), from
"Appendix III: Subscription to IDB Share Capital" in the annual reports for those years
(data/raw/annual_reports/isdb_ar_<year>.pdf). These reports predate the annex layout that
annual_reports_isdb.py reads (2006 on), and carry subscribed capital only -- Islamic
dinars million by tranche (initial, 1st additional, 2nd and 3rd general increase) and the
total -- with no votes column, so voting power stays blank.

Capital share = a member's total subscribed over the members' total, checked against the
printed Total row. Year assignment follows annual_reports_isdb.py: the table is dated 30
Dhul Hijjah (03 Mar 2003 / 20 Feb 2004 / 09 Feb 2005), and each Hijri year-end goes to the
calendar year whose 31 December is nearest: 2002, 2003, 2004.

Usage:  python3 scripts/annual_reports_isdb_early.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, REPO, REPORTS_DIR, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

TEXT_DIR = REPO / "data" / "raw" / "text"
TARGET = EXTRACTED_DIR / "shares_isdb_early.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_isdb_early_unresolved.csv"
FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_NAME_FIXUPS = {"U.A.E": "United Arab Emirates", "UAE": "United Arab Emirates", "Kyrghyz": "Kyrgyzstan", "Guinea Bissau": "Guinea-Bissau", "Cote d’Ivoire": "Cote d'Ivoire"}
_ROW = re.compile(r"^(?:\d+\.?\s+)?([A-Za-z][A-Za-z ’'.\-]*?)\s+((?:[\d,]+\.\d\d|[-*])(?:\s+(?:[\d,]+\.\d\d|[-*]))*)\s*$")
_TOTAL = re.compile(r"^(?:grand\s+|sub\s*)?total:?\s+((?:[\d,]+\.\d\d|[-*])(?:\s+(?:[\d,]+\.\d\d|[-*]))*)\s*$", re.I)


def _amount(token: str) -> float:
    return float(token.replace(",", ""))


def parse_appendix(lines: list[str]):
    """({name: total subscribed}, printed total or None). The total subscribed is the
    last amount before the percentage (or, on the 2004 total row, the last amount)."""

    members: dict[str, float] = {}
    printed = None
    for line in lines:
        text = line.strip()
        total = _TOTAL.match(text)
        if total:
            numbers = [t for t in total.group(1).split() if re.match(r"[\d,]+\.\d\d", t)]
            value = _amount(numbers[-2] if len(numbers) >= 2 and numbers[-1] == "100.00" else numbers[-1])
            # 2004 also prints "Uncommitted" (unallocated ID 139.29m) and a Grand Total above the
            # members' Sub total -- the members must reconcile to the Sub total
            if printed is None or re.match(r"^sub", text, re.I):
                printed = value
            continue
        row = _ROW.match(text)
        if not row:
            continue
        name = _NAME_FIXUPS.get(row.group(1).strip(), row.group(1).strip())
        numbers = [t for t in row.group(2).split() if re.match(r"[\d,]+\.\d\d", t)]
        if len(numbers) < 2 or not iso3_from_name(name):
            continue
        members.setdefault(name, _amount(numbers[-2]))  # ... total subscribed, percentage
    return members, printed


def main() -> int:
    rows, unresolved = [], []
    for year, page in ((2002, "p252"), (2003, "p281"), (2004, "p295")):
        lines = (TEXT_DIR / f"isdb_ar_{year}" / f"{page}.txt").read_text(encoding="utf-8").splitlines()
        lines += (TEXT_DIR / f"isdb_ar_{year}" / f"p{int(page[1:]) + 1:03d}.txt").read_text(encoding="utf-8").splitlines()
        members, printed = parse_appendix(lines)
        total = sum(members.values())
        ok = printed is not None and abs(total - printed) <= 0.05 * len(members)
        print(f"{year}: {len(members)} members, total {total:,.2f} vs printed {printed}: {'OK' if ok else 'CHECK'}")
        if not ok:
            continue
        for name, amount in members.items():
            rows.append({"bank": "IsDB", "iso3": iso3_from_name(name), "year": year,
                         "capital_share_pct": round(amount / total * 100, 6), "voting_power_pct": "",
                         "source_url": f"data/raw/annual_reports/isdb_ar_{year}.pdf",
                         "note": "Total subscribed share capital (ID million); the report predates the votes annex."})
    rows += isdb_1426h()
    rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, rows)
    print(f"{len(rows)} rows -> {TARGET.relative_to(REPO)}")
    return 0




# ---------------------------------------------------------------- 1426H (panel year 2005)
def isdb_1426h() -> list[dict]:
    """"Appendix III Statement of Subscriptions to Capital Stock and Voting Power, as on
    30.12.1426H (30.01.2006)" of the FY1426H report (page image with a garbled font layer, so
    OCR'd). Rows: serial, member, shares, % of total, par value (= shares / 100 in ID million),
    callable, paid-in, ..., number of votes, % of votes. Shares are repaired by the par-value
    identity; a vote count whose share of the printed vote total disagrees with the printed
    percentage (OCR: "B,975" for 8,975) is replaced by the printed percentage times the vote
    total and flagged. The members must add up to the printed Sub-Total of shares."""

    from pathlib import Path as _P

    import ocr

    pdf = REPO / "data" / "raw" / "annual_reports" / "IsDB-Annual Report-2005.pdf"
    lines = ocr.page_text(pdf, 268).splitlines()
    total_votes = 694951
    members: dict[str, dict] = {}
    for line in lines:
        m = re.match(r"^\s*\w{1,3}[.%]?\s+([A-Za-z][A-Za-z '’-]*?)\s+([\d,]+)\s+[\d.]+\s*%?\s+([\d,.]+)\s+.*?([\dB,]+)\s+([\d.]+)\s*%?\s*$", line)
        if not m:
            continue
        name = {"Tran": "Iran", "Kyrgyz": "Kyrgyzstan", "Cote D'Ivoire": "Cote d'Ivoire", "Guinea-Bissau": "Guinea-Bissau"}.get(m.group(1).strip(), m.group(1).strip())
        iso = iso3_from_name(_NAME_FIXUPS.get(name, name))
        if not iso:
            continue
        par = float(m.group(3).replace(",", ""))
        shares = int(m.group(2).replace(",", ""))
        if abs(shares / 100 - par) > 0.02:
            shares = round(par * 100)
        votes_token = m.group(4).replace("B", "8").replace(",", "")
        votes = int(votes_token) if votes_token.isdigit() else None
        pct = float(m.group(5))
        flag = ""
        if votes is None or abs(votes / total_votes * 100 - pct) > 0.02:
            votes, flag = round(pct / 100 * total_votes), " Votes from the printed % (OCR)."
        members[iso] = {"shares": shares, "votes": votes, "flag": flag}
    total_shares = sum(v["shares"] for v in members.values())
    if len(members) != 56 or total_shares != 798940:
        raise SystemExit(f"IsDB 1426H: {len(members)} members, {total_shares:,} shares (printed 798,940)")
    total_v = sum(v["votes"] for v in members.values())
    return [{"bank": "IsDB", "iso3": iso, "year": 2005, "capital_share_pct": round(v["shares"] / total_shares * 100, 6),
             "voting_power_pct": round(v["votes"] / total_v * 100, 6), "source_url": "data/raw/annual_reports/IsDB-Annual Report-2005.pdf",
             "note": "Appendix III, 1426H (OCR); shares repaired by par = shares/100." + v["flag"]} for iso, v in members.items()]


if __name__ == "__main__":
    raise SystemExit(main())
