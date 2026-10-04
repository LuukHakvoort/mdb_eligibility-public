"""CAF's subscribed capital per stockholder, from the notes to CAF's financial
statements (data/raw/annual_reports/caf_<year>.pdf, hand-downloaded: caf.com sits behind
an Incapsula bot wall). Two tables per year-end:

  "Subscribed and paid-in capital ... at December 31, Y" -- shares and nominal amount by
      series (A, B, C) and the row total (USD thousand);
  "the distribution/detail of unpaid subscribed capital and of subscribed callable
      capital" -- unpaid and callable shares/amounts of series B and C.

Subscribed capital of a member = paid-in total + unpaid subscribed + callable; capital
share = that over all member countries' (the "Commercial banks" line, Series B shares
held by banks that are not members, is left out of the denominator, matching the
2024 investor-presentation figures already in the panel). Voting power is NOT filled:
CAF's per-member power is board seats by share class, which the panel reconstructs only
for the current snapshot.

**Kerning artifact** (2018-2020 text layers): the first digit of a number is split off
("1 00,404" for 100,404). Handled as in the ADB parser -- by structure and arithmetic,
not guessing: every cell may be one token or a lone digit plus the next token, and only
the partition satisfying the table's identities is accepted (nominal amounts are exact
multiples of the share counts: A 1,200/share, B and C 5/share; row total = A+B+C).

Usage:  python3 scripts/annual_reports_caf.py [year ...]
"""

from __future__ import annotations

import re
import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, REPO, REPORTS_DIR, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

TEXT_DIR = REPO / "data" / "raw" / "text"
TARGET = EXTRACTED_DIR / "shares_caf.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_caf_unresolved.csv"
FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_NAME_FIXUPS = {"Trinidad & Tobago": "Trinidad and Tobago", "Trinidad y Tobago": "Trinidad and Tobago", "Brasil": "Brazil"}
_PAID_HEADING = re.compile(r"subscribed and paid-in capital.*?december 31,? (\d{4})", re.I)
_UNPAID_HEADING = re.compile(r"(?:at|as of) december 31,? (\d{4}),? the (?:distribution|detail) of unpaid subscribed capital", re.I)
_NUMBER = re.compile(r"^\d[\d,.]*$")


def _value(token: str) -> int | None:
    if token == "-":
        return 0
    cleaned = token.replace(",", "").replace(".", "")
    return int(cleaned) if cleaned.isdigit() else None


def _partitions(tokens: list[str], slots: int):
    """Every way to read `tokens` as `slots` cells, each one token or a lone digit
    (or a lone digit followed by a comma-led/short fragment) plus the next token."""

    def rec(index: int, remaining: int):
        if remaining == 0:
            if index == len(tokens):
                yield []
            return
        for width in (1, 2):
            if index + width > len(tokens):
                continue
            pieces = tokens[index:index + width]
            if width == 2 and not (len(pieces[0]) == 1 and pieces[0].isdigit() and pieces[1] != "-"):
                continue
            value = _value("".join(pieces))
            if value is None:
                continue
            for tail in rec(index + width, remaining - 1):
                yield [value] + tail

    yield from rec(0, slots)


def _near(a: int, b: int) -> bool:
    return abs(a - b) <= 1  # amounts are in rounded thousands


def _cells(tokens: list[str]) -> list[list[int]]:
    """Every reading of `tokens` as cells (see _partitions), any number of cells."""

    results: list[list[int]] = []

    def rec(index: int, acc: list[int]) -> None:
        if index == len(tokens):
            results.append(acc)
            return
        for width in (1, 2):
            if index + width > len(tokens):
                continue
            pieces = tokens[index:index + width]
            if width == 2 and not (len(pieces[0]) == 1 and pieces[0].isdigit() and pieces[1] != "-"):
                continue
            value = _value("".join(pieces))
            if value is not None:
                rec(index + width, acc + [value])

    rec(0, [])
    return results


def _solve(tokens: list[str], kind: str) -> list[int] | None:
    """paid: [A#, B#, C#, A$, B$, C$, total] with the amounts obeying the table's
    identities (A 1,200 per share, B and C 5 per share; the *printed* total is
    replaced by A$+B$+C$ -- 2014's table prints two totals in the wrong cells).
    unpaid: [B#, B$, C#, C$, callable B#, B$, C#, C$] read as (shares, amount) pairs
    with amount = 5 x shares, a missing pair being blank; only its amounts matter."""

    if kind == "paid":
        good = []
        for cells in _cells(tokens):
            if len(cells) != 7:
                # 2023-2025 drop the dash cells of a series the member doesn't hold: a series-C-only
                # row reads [C shares, C amount, total] and a series-B-only row likewise
                if len(cells) >= 3 and cells[-1] == cells[-2] and _near(cells[-2], 5 * cells[-3]) and cells[-3] > 0:
                    good.append((0, 0, 0, 0, 0, cells[-2], cells[-1]))
                continue
            a, b, c, a_amt, b_amt, c_amt, _ = cells
            if a_amt == 1200 * a and _near(b_amt, 5 * b) and _near(c_amt, 5 * c):
                good.append((a, b, c, a_amt, b_amt, c_amt, a_amt + b_amt + c_amt))
        return list(good[0]) if len(set(good)) == 1 else None
    good = []
    for cells in _cells(tokens):
        if len(cells) % 2 or not cells:
            continue
        if all(_near(cells[i + 1], 5 * cells[i]) for i in range(0, len(cells), 2)):
            good.append(tuple(cells))
    if len({sum(g[1::2]) for g in good}) != 1:
        return None
    return [sum(good[0][1::2])]


def _lines(year: int) -> list[str]:
    lines: list[str] = []
    for page in sorted((TEXT_DIR / f"caf_{year}").glob("p*.txt")):
        lines += page.read_text(encoding="utf-8").splitlines()
    return lines


def parse_document(year: int) -> tuple[dict, dict, list[str]]:
    """({year: {name: paid total}}, {year: {name: unpaid+callable amount}}, problems).
    A table ends at its total row, and is accepted only if the member rows (with the
    non-member "Commercial banks" line) add up to that printed total on every column."""

    paid: dict[int, dict[str, int]] = {}
    unpaid: dict[int, dict[str, int]] = {}
    problems: list[str] = []
    kind = table_year = None
    rows: dict[str, list[int]] = {}

    def close(total_values: list[int]) -> None:
        nonlocal kind
        columns = [[v[6]] if kind == "paid" else [v[0]] for v in rows.values()]
        column = sum(c[0] for c in columns)
        expected = total_values[6] if kind == "paid" else total_values[0]
        if abs(column - expected) > 3:
            problems.append(f"{table_year} {kind}: member rows do not add up to the printed total")
        else:
            target = paid if kind == "paid" else unpaid
            target.setdefault(table_year, {})
            for name, values in rows.items():
                if name.lower().startswith("commercial"):
                    continue
                target[table_year][name] = values[6] if kind == "paid" else values[0]
        kind = None

    all_lines = [l.strip() for l in _lines(year)]
    for index, text in enumerate(all_lines):
        heading = _PAID_HEADING.search(text)
        if heading:
            kind, table_year, rows = "paid", int(heading.group(1)), {}
            continue
        heading = _UNPAID_HEADING.search(text)
        if heading:
            kind, table_year, rows = "unpaid", int(heading.group(1)), {}
            continue
        if kind is None:
            continue
        tokens = text.split()
        cut = next((i for i, t in enumerate(tokens) if _NUMBER.match(t) or t == "-"), None)
        if cut is None:
            continue
        name = " ".join(tokens[:cut]).rstrip(":")
        values = _solve(tokens[cut:], kind)
        if not name and index and index + 1 < len(all_lines):
            # a name wrapped around its numbers ("Trinidad &" / numbers / "Tobago")
            above, below = all_lines[index - 1], all_lines[index + 1]
            if above and below and not re.search(r"\d", above + below) and len(above) < 25 and len(below) < 25:
                wrapped = _NAME_FIXUPS.get(f"{above} {below}".replace(" & ", " and "), f"{above} {below}".replace(" & ", " and "))
                if iso3_from_name(wrapped) or wrapped.lower().startswith("commercial"):
                    name = wrapped
        name = _NAME_FIXUPS.get(name, name)
        if not name:  # the total row
            if values is not None and rows:
                # the paid table's total row counts stockholders in column 1 (series A holders)
                close(values)
            continue
        if not (iso3_from_name(name) or name.lower().startswith("commercial")):
            continue
        if values is None:
            problems.append(f"{table_year} {kind}: could not resolve the cells of '{text}'")
            continue
        rows[name] = values
    return paid, unpaid, problems


def main(argv: list[str]) -> int:
    years = [int(a) for a in argv] or list(range(2002, 2026))
    chosen: dict[int, tuple[dict[str, int], int]] = {}  # table year -> (subscribed by member, document year)
    for doc in years:
        if not (TEXT_DIR / f"caf_{doc}").is_dir():
            continue
        paid, unpaid, problems = parse_document(doc)
        for year in sorted(set(paid) & set(unpaid)):
            members = {n: paid[year][n] + unpaid[year].get(n, 0) for n in paid[year]}
            missing = sorted(set(unpaid[year]) - set(paid[year]))
            print(f"{doc}: table {year}: {len(members)} members, total subscribed {sum(members.values()):,}"
                  f"{'  unpaid-only rows: ' + ', '.join(missing) if missing else ''}"
                  f"{'  PROBLEMS: ' + '; '.join(problems[:2]) if problems else ''}")
            if year not in chosen or year == doc:
                chosen[year] = (members, doc)
        if not (set(paid) & set(unpaid)):
            print(f"{doc}: no paired paid-in / unpaid tables found ({len(paid)} paid, {len(unpaid)} unpaid){'  ' + problems[0] if problems else ''}")
    rows, unresolved = [], []
    for year, (members, doc) in sorted(chosen.items()):
        total = sum(members.values())
        for name, amount in members.items():
            iso3 = iso3_from_name(name)
            rows.append({"bank": "CAF", "iso3": iso3, "year": year, "capital_share_pct": round(amount / total * 100, 6),
                         "voting_power_pct": "", "source_url": f"data/raw/annual_reports/caf_{doc}.pdf",
                         "note": "Subscribed capital = paid-in + unpaid subscribed + callable, over member countries."})
    rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, rows)
    print(f"\n{len(rows)} rows -> {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
