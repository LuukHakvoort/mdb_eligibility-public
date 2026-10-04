"""Extend EBRD's shareholder history to 2000-2013, via EBRD's own annual
financial-statement PDFs -- `scripts/shares_wayback_ebrd.py` already covers
2014-2025 from Wayback captures of ebrd.com's shareholders page, but that
page has **zero captures before Dec 2014** (confirmed live via the Wayback
CDX API: no hit for any "shareholders*" URL prefix on ebrd.com in
2000-2013), a genuine dead end, not an unexplored option. This uses the
plan's own documented fallback for that case: PDF governance/financial
documents.

Unusually clean, compared to every other bank parsed this pass: the
"Statement of capital subscriptions" note gives **both** capital share and
voting share directly in one table (Total shares / Resulting votes / Total
capital / Callable capital / Paid-in capital), every column comma-grouped
(never space-grouped, unlike EIB's older documents) -- confirmed stable
across the whole 2000-2013 range fetched, so a single per-line regex
suffices, no word-position clustering needed.

The table can span two PDF pages once EBRD's membership grew (SEMED
accessions, 2013); both carry the same heading, so every page with it is
concatenated before parsing, rather than assuming one page like CDB needed
a next-page special case for. That heading itself varies by one letter --
"Statement of capital subscription**s**" every year except 2011, where
EBRD's own document drops the final "s" (confirmed live) -- matched with a
small regex, not an exact string.

**The document's own printed total row is a cross-check, not the
denominator.** 2007's total-votes cell has a single corrupted glyph baked
into the PDF's own character stream (confirmed via `extract_words()`, not
an extraction-setting problem: the token literally decodes to
`"1,969,\x1871"`) -- unreadable in any year-2007 run, not just this one.
The denominator used throughout is the *summed* per-member total instead,
checked against the document's own total wherever that total did parse
cleanly (every other year).

Two real, narrow number-format cases, both confirmed live and handled
explicitly rather than by loosening the row pattern generally: a lone dash
means zero (2011's brand-new member, "Jordan 100 100 1 1 –", had
negligible paid-in capital that year, not a missing value); and 2000's
table alone carries one genuinely unattributable reserve line --
"Unallocated shares reserved for countries previously forming part of
Yugoslavia" -- with a footnote digit glued directly onto its shares figure
and a dash where votes would be (voting rights on it were suspended
pending reallocation, a real fact). It's counted in the year's total like
the two non-country shareholders below, excluded from the country panel.
By the 2001 document this reserve had already been reallocated to a
normal "Federal Republic of Yugoslavia" member row.

Two shareholders are not countries (European Union -- "European Community"
in earlier years -- and the European Investment Bank), same non-country
set `shares_wayback_ebrd.py` already excludes. The Yugoslav successor
state under whatever name it carries in a given year's document ("FR
Yugoslavia," "Federal Republic of Yugoslavia," "Serbia and Montenegro" --
resolved back to two separate countries from the 2006 document onward) is
a genuine predecessor state the shared resolver deliberately leaves
unmapped (`reference_conventions.md` section 7) -- left unresolved here
too, not guessed at.

Usage:  python3 scripts/annual_reports_ebrd.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, MANUAL_DIR, REPO, REPORTS_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402
from annual_reports import fetch  # noqa: E402

ANNUAL_REPORTS_CSV = MANUAL_DIR / "annual_reports.csv"
TARGET = EXTRACTED_DIR / "shares_ebrd.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_ebrd_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

# "Statement of capital subscription**s**" in every year except 2011,
# where EBRD's own document drops the final "s" -- confirmed live, not
# a typo introduced here.
_TABLE_HEADING = re.compile(r"Statement of capital subscriptions?")
_TOTAL_ROW_NAME = "capital subscribed by members"
_NON_COUNTRY = {"european union", "european community", "european investment bank", "__unallocated__"}

# Names as EBRD's own PDFs render them across 2000-2013 -> what
# _reference.iso3_from_name() needs. Everything else in this table
# (Russian Federation, United States of America, Slovak Republic, Kyrgyz
# Republic, Korea, Republic of, ...) already resolves directly -- checked
# live against every name in the 2002 and 2013 documents before deciding
# this short list was actually all that was needed.
_NAME_FIXUPS = {
    "Former Yugoslav Republic of Macedonia": "North Macedonia",
    "FYR Macedonia": "North Macedonia",
    "FYR Macedonia84": "North Macedonia",  # footnote digits glued on (2018)
    "Republic of Korea": "Korea, Rep.",
}

# name, then exactly 5 trailing numbers: shares, votes (always whole
# numbers), then total/callable/paid-in capital (whole € million in most
# years, but with one decimal place in 2003's document specifically --
# confirmed live, "19,789.5" not "19,789"). An optional short trailing
# token tolerates a page-footer number pdfplumber occasionally merges onto
# the table's last line (confirmed live on 2000's Croatia row: "... 19,140
# 87", 87 being the page number, not a sixth data column -- this table
# only ever has five).
_ROW = re.compile(
    r"^(.+?)\s+([\d,]+)\s+([\d,]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)(?:\s+\d{1,3})?(?:\s+[A-Za-z]{1,4})*$"
)

# 2000's document only (confirmed: by the 2001 document this had been
# reallocated to a proper "Federal Republic of Yugoslavia" member row,
# which parses normally) -- a genuinely unattributable reserve, not a
# country: "forming part of Yugoslavia 4,6753 – 46,750 32,730 14,020"
# wraps from a "Unallocated shares reserved for countries previously"
# line above it, has a footnote digit glued directly onto the shares
# figure with no separator, and an em dash instead of a votes number
# (accurately: voting rights on this reserve were suspended, a real fact,
# not a missing value). Counted in the denominator like EU/EIB, excluded
# from the country panel.
_UNALLOCATED_YUGOSLAVIA = re.compile(
    r"forming part of Yugoslavia\s+([\d,]+?)\d?\s+[–‒-]\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)"
)


def _resolve(name_raw: str) -> str:
    return iso3_from_name(_NAME_FIXUPS.get(name_raw, name_raw))


_LONE_DASH = re.compile(r"(?<=\s)[–‒-](?=\s|$)")


def _parse_row(line: str) -> tuple[str, float, float] | None:
    # A lone dash means zero in this table (confirmed real: 2011's
    # "Jordan 100 100 1 1 –" -- a brand-new member with negligible
    # paid-in capital that year, not a missing value).
    match = _ROW.match(_LONE_DASH.sub("0", line.strip()))
    if not match:
        return None
    name = match.group(1).strip()
    if not name or name[0].isdigit():
        return None
    shares = float(match.group(2).replace(",", ""))
    votes = float(match.group(3).replace(",", ""))
    return name, shares, votes


_TWO_COLUMN_YEARS = (2014, 2015)


def _upright_text(page) -> str:
    """Page text from upright words only, rebuilt line by line from word positions: the 2018-2025
    reports carry vertical margin text (a rotated chapter tab) whose characters the plain text
    layer interleaves into the table, scrambling rows ("France" vanishes in 2023)."""

    words = [w for w in page.extract_words(extra_attrs=["upright"]) if w["upright"]]
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= 2.5:
            lines[-1].append(word)
        else:
            lines.append([word])
    return "\n".join(" ".join(w["text"] for w in sorted(line, key=lambda w: w["x0"])) for line in lines)


def _right_column_text(page) -> str:
    """Text of the table column on 2014-2015's two-column pages, rebuilt from word positions:
    the words sit at x beyond the page's nominal width, so a crop cannot reach them. The
    column starts at the "Members" header word."""

    words = page.extract_words()
    header = next((w for w in words if w["text"] == "Members"), None)
    if header is None:
        return ""
    column = [w for w in words if w["x0"] >= header["x0"] - 2]
    lines: list[list[dict]] = []
    for word in sorted(column, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= 3:
            lines[-1].append(word)
        else:
            lines.append([word])
    return "\n".join(" ".join(w["text"] for w in sorted(line, key=lambda w: w["x0"])) for line in lines)


def parse_pdf(path: Path, year: int, source_url: str) -> tuple[list[dict], list[dict]]:
    import pdfplumber

    lines: list[str] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if not _TABLE_HEADING.search(text):
                continue
            if year in _TWO_COLUMN_YEARS:
                # 2014-2015 set the table in the right-hand column beside running narrative, the
                # text layer merging the two into one line; read that column alone, and follow
                # the table onto the next page(s) (no heading there) up to its Total row.
                block = _right_column_text(page)
                lines += block.splitlines()
                following = number + 1
                while not any(l.strip().lower().startswith("total") for l in block.splitlines()) and following < len(pdf.pages):
                    block = _right_column_text(pdf.pages[following])
                    lines += block.splitlines()
                    following += 1
                break
            if year >= 2016:
                # later years' table is longer than a page: read on, past the heading-less
                # continuation, to its Total row (pages that merely mention the heading are skipped)
                if sum(1 for l in text.splitlines() if _parse_row(l)) < 5:
                    continue
                block = _upright_text(page).splitlines()
                following = number + 1
                while not any(re.match(r"^\s*Total\b", l) and _parse_row(l) for l in block) and following < min(len(pdf.pages), number + 4):
                    block += _upright_text(pdf.pages[following]).splitlines()
                    following += 1
                lines += block
                break
            lines += text.splitlines()

    candidates: list[tuple[str, float, float]] = []
    stated_shares = stated_votes = None
    for line in lines:
        if year >= 2016:
            # 2016+ tables print no Total row. Each row is instead checked against the identity
            # shares x EUR 10,000 = total capital (EUR million; whole millions before 2022, so
            # +-50 shares), and the table ends at the first non-member row after 30+ members.
            match = _ROW.match(_LONE_DASH.sub("0", line.strip()))
            if not match:
                continue
            name = match.group(1).strip()
            if not (_resolve(name) or name.lower() in _NON_COUNTRY):
                if len(candidates) >= 30:
                    break
                continue
            shares_v, votes_v = float(match.group(2).replace(",", "")), float(match.group(3).replace(",", ""))
            capital = float(match.group(4).replace(",", ""))
            tolerance = 110 if "." not in match.group(4) else 2
            if abs(shares_v - capital * 100) > tolerance:
                raise SystemExit(f"error: {path} for {year}: row '{line.strip()}' breaks shares x EUR 10,000 = capital")
            candidates.append((name, shares_v, votes_v))
            continue
        unallocated = _UNALLOCATED_YUGOSLAVIA.search(line)
        if unallocated:
            candidates.append(("__unallocated__", float(unallocated.group(1).replace(",", "")), 0.0))
            continue
        parsed = _parse_row(line)
        if parsed is None:
            continue
        name, shares, votes = parsed
        if name.lower() == _TOTAL_ROW_NAME:
            stated_shares, stated_votes = shares, votes
            break  # 2015 on print the prior year's table below this one; the first Total closes ours
        candidates.append((name, shares, votes))

    if not candidates:
        raise SystemExit(f"error: no member rows found in {path} for {year}")
    if year >= 2016 and len(candidates) < 60:
        # (2023's table prints the France row letter-spaced -- "F r a n c e 25 5 , 6 51" -- so the
        # read ends early; a partial table must never be normalised into shares)
        raise SystemExit(f"error: {path} for {year}: only {len(candidates)} member rows read before the table broke off")

    # The denominator is the *summed* candidate total, not the document's
    # own printed total row -- more robust, and required for one real
    # document: 2007's total-votes figure has a single corrupted glyph
    # baked into the PDF's own character stream ("1,969,\x1871", confirmed
    # live via extract_words(), not an extraction setting to fix), so that
    # cell can never be read reliably. The printed total is still used as
    # a cross-check wherever it *did* parse cleanly.
    total_shares = sum(shares for _, shares, _ in candidates)
    total_votes = sum(votes for _, _, votes in candidates)
    if stated_shares is None and 2014 <= year < 2016:
        raise SystemExit(f"error: {path} for {year}: no Total row read, so the table can't be reconciled")
    if stated_shares is not None:
        shares_pct = total_shares / stated_shares * 100
        votes_pct = total_votes / stated_votes * 100
        if not (99.9 <= shares_pct <= 100.1 and 99.9 <= votes_pct <= 100.1):
            raise SystemExit(
                f"error: {path} for {year}: summed candidates are {shares_pct:.2f}% of stated "
                f"shares and {votes_pct:.2f}% of stated votes, not ~100% ({len(candidates)} rows found)"
            )

    rows: list[dict] = []
    unresolved: list[dict] = []
    for name, shares, votes in candidates:
        if name.lower() in _NON_COUNTRY:
            continue
        iso3 = _resolve(name)
        if not iso3:
            unresolved.append({"year": year, "name_raw": name})
            continue
        rows.append({
            "bank": "EBRD", "iso3": iso3, "year": year,
            "capital_share_pct": round(shares / total_shares * 100, 6),
            "voting_power_pct": round(votes / total_votes * 100, 6),
            "source_url": source_url,
            "note": "",
        })
    return rows, unresolved


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "EBRD":
            continue
        year = int(row["year"])
        url = row["url"]
        path = fetch(url, f"ebrd_fs_{year}.pdf")
        try:
            rows, unresolved = parse_pdf(path, year, url)
        except SystemExit as failure:
            if year < 2014:
                raise
            print(f"{year}: SKIPPED -- {failure}")  # 2014+ layouts vary; only years that reconcile are kept
            continue
        all_rows += rows
        all_unresolved += unresolved
        # parse_pdf() already validated the full extraction (including the
        # two non-country shareholders) sums to ~100% before returning --
        # country-only rows here deliberately don't, by design (see
        # module docstring), so just report what was resolved.
        print(f"{year}: {len(rows)} country rows ({len(unresolved)} unresolved this document)")

    all_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, all_rows)
    write_csv(UNRESOLVED_REPORT, ["year", "name_raw"], all_unresolved)
    print(f"\n{len(all_rows)} rows -> {TARGET.relative_to(REPO)}")
    print(f"{len(all_unresolved)} unresolved names -> {UNRESOLVED_REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
