"""BADEA's capital share and voting power per member, 2002-2019, from the annex
"Subscription in BADEA's Capital by Member States and Distribution of Votes" of BADEA's
annual reports (data/raw/annual_reports/badea_<year>.pdf, cached text via dump_pdf_text.py).

Per member: paid-up amount, number of shares (amount / USD 100,000), % of shares, number
of votes (shares + 200 basic votes per member), % of votes. Capital share = shares over all
members'; voting power = votes over all votes -- recomputed and checked against the printed
percentages and Total row. This adds the voting power that the paid-in-contribution tables
(annual_reports_badea.py) never carried.

Panel year = the report's own year (the annex is "until 31/12/<year>").

Usage:  python3 scripts/annual_reports_badea_annex.py [year ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, REPO, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402
from annual_reports_badea import _NAME_FIXUPS  # noqa: E402

TEXT_DIR = REPO / "data" / "raw" / "text"
TARGET = EXTRACTED_DIR / "shares_badea_annex.csv"
FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_NUM = r"\d[\d,.]*"
_ROW = re.compile(rf"^(.*?)\s*({_NUM})\s+({_NUM})\s+({_NUM})\s+({_NUM})\s+({_NUM})\s*$")
_EXTRA_FIXUPS = {
    "State of the United Arab Emirates": "United Arab Emirates", "United Arab Emirates": "United Arab Emirates",
    "State of United Arab Emirates": "United Arab Emirates", "States of United Arab Emirates": "United Arab Emirates",
    "Great Arab Libyan People’s Socialist Jamahiriya": "Libya", "Great Arab Libyan People's Socialist Jamahiriya": "Libya",
    "Republic of Lebanon": "Lebanon", "Palestine": "Palestine, State of", "Syrian Arab Republic": "Syria",
    "Arab Republic of Syria": "Syria", "Republic of Mauritania": "Mauritania",
    "Islamic Republic of Mauritania": "Mauritania", "Democratic People’s Republic of Algeria": "Algeria",
    "People's Democratic Republic of Algeria": "Algeria",
}


def _num(token: str, comma_is_decimal: bool = False) -> float:
    """A printed number: commas group thousands (or, in a percentage, are a mistyped decimal
    point); some years dot-group thousands too ("4.484.807.66"), so only the last dot counts."""

    token = token.replace(",", ".") if comma_is_decimal else token.replace(",", "")
    head, dot, tail = token.rpartition(".")
    return float(head.replace(".", "") + dot + tail) if dot else float(token)


def _iso(name: str) -> str | None:
    # drop scan debris ("--", ">----", "183 ·") that OCR'd text puts in front of a name
    name = " ".join(t for t in name.split() if re.search(r"[A-Za-z]", t)).strip(" .:-|•")
    for table in (_EXTRA_FIXUPS, _NAME_FIXUPS):
        if name in table:
            name = table[name]
            break
    if iso3_from_name(name):
        return iso3_from_name(name)
    import difflib  # OCR'd annexes misspell names ("Kmgdom of Bahrain")

    known = list(_EXTRA_FIXUPS) + list(_NAME_FIXUPS)
    close = difflib.get_close_matches(re.sub(r"[^A-Za-z’' ]", "", name), known, n=1, cutoff=0.8)
    if close:
        target = _EXTRA_FIXUPS.get(close[0]) or _NAME_FIXUPS.get(close[0])
        return iso3_from_name(target) or None
    return None


def derived_from_contributions() -> dict[str, float]:
    """2012 and 2013: the votes annex is a scanned image with no usable text, but the FY2013
    report's note 13 prints each member's subscription "as at 31 December 2013 and 2012" in a
    single column (USD 000, total 2,800,000 -- unchanged since 2009; the capital increase took
    effect January 2014). Returns {iso3: amount}."""

    directory = TEXT_DIR / "badea_2013"
    for page in sorted(directory.glob("p*.txt")):
        lines = page.read_text(encoding="utf-8").splitlines()
        if not any("SUBSCRIBED AND PAID-UP CAPITAL" in l.upper() for l in lines):
            continue
        amounts: dict[str, float] = {}
        for line in lines:
            m = re.match(r"^(.*?)\s+(\d[\d,]*)$", line.strip())
            if m and _iso(m.group(1)) and _iso(m.group(1)) not in amounts:
                amounts[_iso(m.group(1))] = _num(m.group(2))
        if len(amounts) == 18 and abs(sum(amounts.values()) - 2_800_000) < 1:
            return amounts
    return {}


def contributions_2022() -> dict[str, float]:
    """FY2023 report, "Member States' Contributions as of 31 December 2023": a name line, then
    the 2023 and 2022 amounts (USD 000; total 5,000,000 both years). Returns the 2022 column."""

    lines = (TEXT_DIR / "badea_2023" / "p040.txt").read_text(encoding="utf-8").splitlines()
    amounts: dict[str, float] = {}
    for index, line in enumerate(lines):
        m = re.match(r"^(.*?)\s*(\d[\d,]*)\s+(\d[\d,]*)(?:\s|$)", line.strip())
        if m and m.group(1) and _iso(m.group(1)):
            amounts.setdefault(_iso(m.group(1)), _num(m.group(3)))
        elif re.fullmatch(r"(\d[\d,]*)\s+(\d[\d,]*)", line.strip()) and index and _iso(lines[index - 1]):
            amounts.setdefault(_iso(lines[index - 1]), _num(line.split()[1]))
    return amounts


def annex_lines(year: int) -> list[str]:
    """The lines of the page (and the next, where the table runs over) whose rows read as
    the votes annex: at least 10 member rows with five numbers each. Found by content, not
    by heading -- several years' headings are OCR-mangled or share the page with ANNEX VI."""

    directory = TEXT_DIR / f"badea_{year}"
    pages = [p.read_text(encoding="utf-8").splitlines() for p in sorted(directory.glob("p*.txt"))]
    best: list[str] = []
    best_count = 0
    for index, lines in enumerate(pages):
        text = "\n".join(lines).upper()
        if "VOTE" not in text:
            continue
        members, _, _ = parse(lines + (pages[index + 1] if index + 1 < len(pages) else []))
        if len(members) > best_count and len(members) >= 10:
            best, best_count = lines + (pages[index + 1] if index + 1 < len(pages) else []), len(members)
    return best


def parse(lines: list[str]):
    """{iso3: (shares, votes)} and the Total row's (shares, votes)."""

    members: dict[str, tuple[float, float, float, float]] = {}
    total = None
    def clean(line: str) -> str:
        line = re.sub(r"\s[·•]\s", " ", line.replace("\ufffd", "."))
        line = re.sub(r"^[\s'\-•|:]+", "", line)
        # trailing scan debris after the last number ("... 12.58 • •."); name-only fragments keep theirs
        return re.sub(r"[^\d]+$", "", line) if re.search(r"\d", line) else line.strip()

    cleaned = [clean(l) for l in lines]  # 2019's text layer renders "." as U+FFFD
    for index, line in enumerate(cleaned):
        m = _ROW.match(line)
        if not m:
            continue
        name, amount, shares, pct, votes, vpct = m.groups()
        if name.lower().startswith("total") or name.strip() == "Total":
            total = (_num(shares), _num(votes))
            continue
        iso = _iso(name)
        if not iso:
            above = cleaned[index - 1] if index else ""
            below = cleaned[index + 1] if index + 1 < len(cleaned) else ""
            for candidate in (f"{name} {below}", f"{above} {name}", f"{above} {name} {below}", f"{name}{below}"):
                iso = _iso(candidate)
                if iso:
                    break
        if not iso and not name.strip(" .:-|•"):
            # a numbers-only row: the name is on the line above / below
            for candidate in (cleaned[index - 1] if index else "", cleaned[index + 1] if index + 1 < len(cleaned) else ""):
                iso = _iso(candidate)
                if iso:
                    break
        if iso and iso not in members:
            s_val, v_val = _num(shares), _num(votes)
            if abs(v_val - s_val - 200) > 0.01 and abs(_num(votes, True) - s_val - 200) <= 0.01:
                v_val = _num(votes, True)  # 2019 prints Oman's 713.72 votes as "713,72"
            members[iso] = (s_val, v_val, _num(pct, True), _num(vpct, True))
    return members, total, None


def _extra_rows(rows: list[dict]) -> list[dict]:
    """2020 and 2022, whose votes annex is not in the text layer. 2020: the FY2020 report's
    note 12 (an image; OCR read 15 of 18 rows cleanly) shows the same contributions as 2021's
    annex (USD 4,200,000k), so 2020 carries 2021's shares, with votes = shares + 200. 2022:
    capital only, from the FY2023 report's 2022 column (USD 5,000,000k) -- the votes rule is not
    extended to the enlarged capital."""

    extra = []
    for row in rows:
        if row["year"] == 2021:
            extra.append({**row, "year": 2020, "source_url": "data/raw/annual_reports/badea_2020.pdf",
                          "note": "Contributions per FY2020 note 12 (image, OCR) equal FY2021's annex; votes = shares + 200."})
    amounts = contributions_2022()
    if len(amounts) == 18 and abs(sum(amounts.values()) - 5_000_000) < 1:
        total = sum(amounts.values())
        for iso, amount in amounts.items():
            extra.append({"bank": "BADEA", "iso3": iso, "year": 2022, "capital_share_pct": round(amount / total * 100, 6),
                          "voting_power_pct": "", "source_url": "data/raw/annual_reports/badea_2023.pdf",
                          "note": "2022 column of the FY2023 report's Member States' Contributions table."})
    return extra


def main(argv: list[str]) -> int:
    years = [int(a) for a in argv] or list(range(2002, 2025))
    rows = []
    for year in years:
        lines = annex_lines(year)
        if not lines and year in (2012, 2013):
            amounts = derived_from_contributions()
            if len(amounts) == 18:
                # votes = shares + 200 basic votes per member, the identity every printed annex obeys
                shares = {iso: a / 100 for iso, a in amounts.items()}  # USD 000 / USD 100,000 per share
                total_shares = sum(shares.values())
                total_votes = total_shares + 200 * len(shares)
                print(f"{year}: 18 members derived from the FY2013 report's note 13 (annex is an image)")
                for iso, s in shares.items():
                    rows.append({"bank": "BADEA", "iso3": iso, "year": year, "capital_share_pct": round(s / total_shares * 100, 6),
                                 "voting_power_pct": round((s + 200) / total_votes * 100, 6),
                                 "source_url": "data/raw/annual_reports/badea_2013.pdf",
                                 "note": "Votes derived as shares + 200 (the identity every printed BADEA annex obeys); the FY2012/2013 votes annex is a scanned image."})
                continue
        if not lines:
            print(f"{year}: no annex found")
            continue
        members, total, _ = parse(lines)
        shares, votes = sum(v[0] for v in members.values()), sum(v[1] for v in members.values())
        pct_shares, pct_votes = sum(v[2] for v in members.values()), sum(v[3] for v in members.values())
        # printed percentages must add to 100 (rounded to 2-6 decimals) and, where a Total
        # row was read, the sums must match it
        # every member holds 200 basic votes on top of one per share -- a row-level identity
        # that catches a misread cell; printed percentages are re-derived, not trusted
        broken = [iso for iso, v in members.items() if abs(v[1] - v[0] - 200) > 0.01]
        ok = not broken and abs(pct_shares - 100) < 0.05 and (not total or abs(votes - total[1]) <= 1)
        status = "OK" if ok and len(members) == 18 else f"CHECK broken rows {broken}, pct sums {pct_shares:.3f}/{pct_votes:.3f}, total={total}"
        print(f"{year}: {len(members)} members, shares {shares:,.2f}, votes {votes:,.2f}: {status}")
        for iso, (s, v, _, _) in members.items():
            rows.append({"bank": "BADEA", "iso3": iso, "year": year, "capital_share_pct": round(s / shares * 100, 6),
                         "voting_power_pct": round(v / votes * 100, 6),
                         "source_url": f"data/raw/annual_reports/badea_{year}.pdf", "note": ""})
    rows += _extra_rows(rows)
    rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, rows)
    print(f"{len(rows)} rows -> {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
