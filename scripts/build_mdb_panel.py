"""Build data/output/mdb_panel.csv: the estimation panel from
docs/methods_section_draft.md sec. 1 -- one row per (bank, recipient country,
year) restricted to eligible dyad-years, zeros included, lending outcomes and
shareholder covariates attached.

**Grid = eligible.csv's `eligible` rows, plus every observed-lending dyad-year
the rules missed** (docs/architecture.md principle: revealed eligibility is
ground truth). A row's `eligibility_basis` says which:

- ``rule``: `eligibility.csv`'s `eligible` column (the not_evidenced-defaulted
  version -- see scripts/build.py's docstring) is "1".
- ``revealed``: the rules say 0/unknown/absent, but commitments.csv shows real
  lending anyway. These are exactly the rows check_revealed.py's "not yet
  coded" and "contradiction" counts describe (data/output/reports/
  revealed_violations.csv) -- never dropped, always in the panel, flagged so
  they're visible rather than silently smoothed over.

**Lending outcome.** Project counts come from data/extracted/commitments.csv.
USD amounts (nominal and constant-2025) come straight from the scraper's own
bank x country x year aggregation
(../mdbs_scraper_corrected/output/dyad_country_year.csv), which already does
the currency conversion and deflation this project deliberately never
re-derives (docs/architecture.md, "Deliberately not built" / "Currency
conversion rates" in docs/manual_data_checklist.md). A dyad-year genuinely
eligible with no observed lending is zero-filled (`any_lending = 0`, and
`usd_nominal_total`/`usd_2025_total` = "0", not blank), not dropped -- the
whole point of restricting to eligible dyad-years first is to make that zero
a real data point (methods draft sec. 1.1). A blank USD cell therefore only
ever means a real data gap (lending happened but no USD amount could be
attached) -- never "no lending happened."

**PPP-adjusted amount** (`ppp_2025_total`, 2026-10-04): the scraper's own
PPP-adjusted, constant-2025 USD figure, same deflator as `usd_2025_total`,
so the two are directly comparable. Zero-filled exactly like the USD columns
for no-lending dyad-years, but **blank** -- not zero -- for lending dyad-years
the scraper cannot price in PPP: any dyad-year with an unpriced project
(146 dyad-years in the scraper's data), and every year after 2025 (all 291
lending dyad-years of 2026, which the deflator cannot price yet). The scraper
writes 0 for both, so the blank is applied here, not read from its file. Real
zero amounts (disclosed $0 projects) stay 0. See docs/coding_decisions.md,
2026-10-04.

**AfDB's ordinary/concessional breakdown** (2026-09-28 -- AfDB and ADF were
briefly two separate bank codes, 2026-09-24 to 2026-09-28; merged back, see
docs/coding_decisions.md for why). AfDB's own `usd_nominal_total`/
`usd_2025_total` above are its combined ordinary + concessional total, same
as every other bank. Four extra columns, populated for AfDB only (blank for
every other bank), give the ordinary-vs-concessional split:
`afdb_ordinary_n`/`_usd` and `afdb_concessional_n`/`_usd`, from
`data/extracted/afdb_window_breakdown.csv` (`scripts/
build_afdb_window_breakdown.py`, which re-derives this split from the
scraper's project-level `funding_window` field, since `dyad_country_year.csv`
has no such column). A project tagged with both windows counts toward both
sub-totals -- harmless here since they're two columns on one row, not two
banks' separate grand totals that would otherwise double-count it.

**Covariates** (capital_share_pct, voting_power_pct, recipient_status,
member_since) are read straight from data/output/membership.csv -- already a
finished, standalone output (build_membership.py) -- not recomputed here.

Usage:  python3 scripts/build_mdb_panel.py [--eligibility PATH] [--membership PATH]
        [--commitments PATH] [--dyad-country-year PATH] [--afdb-window-breakdown PATH]
        [--output PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _panel import (  # noqa: E402
    BANKS, CANONICAL_BANKS, COMMITMENTS_CSV, ELIGIBILITY_CSV, OUTPUT_DIR, REPO,
    load_commitments, read_csv, write_csv,
)

from _panel import EXTRACTED_DIR as _EXTRACTED_DIR  # noqa: E402

MEMBERSHIP_CSV = OUTPUT_DIR / "membership.csv"
DYAD_COUNTRY_YEAR = Path(__file__).resolve().parents[2] / "mdbs_scraper_corrected" / "output" / "dyad_country_year.csv"
AFDB_WINDOW_BREAKDOWN_CSV = _EXTRACTED_DIR / "afdb_window_breakdown.csv"
PANEL_CSV = OUTPUT_DIR / "mdb_panel.csv"

FIELDS = [
    "bank", "iso3", "year", "eligibility_basis",
    "capital_share_pct", "voting_power_pct", "recipient_status", "member_since",
    "projects", "projects_with_positive_amount", "any_lending",
    "usd_nominal_total", "usd_2025_total", "ppp_2025_total",
    "afdb_ordinary_n", "afdb_ordinary_usd", "afdb_concessional_n", "afdb_concessional_usd",
    "note",
]


def _load_eligibility(path: Path) -> dict[tuple[str, str, int], dict]:
    rows: dict[tuple[str, str, int], dict] = {}
    if not path.is_file():
        raise SystemExit(f"error: {path} does not exist. Run: python3 scripts/build.py")
    for row in read_csv(path):
        if not row.get("year", "").isdigit():
            continue
        key = (row["bank"], row["iso3"], int(row["year"]))
        rows[key] = row
    return rows


def _load_membership(path: Path) -> dict[tuple[str, str, int], dict]:
    rows: dict[tuple[str, str, int], dict] = {}
    if not path.is_file():
        raise SystemExit(f"error: {path} does not exist. Run: python3 scripts/build_membership.py")
    for row in read_csv(path):
        if not row.get("year", "").isdigit():
            continue
        rows[(row["bank"], row["iso3"], int(row["year"]))] = row
    return rows


# The scraper prices PPP in constant 2025 USD, which needs the FRED deflator;
# that deflator has no 2026 value yet (mdbs_scraper dyad.py), so no year after
# this can be priced. Its own n_ppp_unpriced counter does not flag these years.
PPP_LAST_PRICED_YEAR = 2025


def _load_usd_amounts(path: Path) -> dict[tuple[str, str, int], tuple[str, str, str]]:
    """{(bank, iso3, year): (usd_nominal_total, usd_2025_total, ppp_2025_total)}.

    ppp_2025_total is the scraper's PPP-adjusted, constant-2025 USD figure
    (GDP price-level ratio, same deflator as usd_2025_total). Blank -- not 0 --
    where the dyad-year could not be priced: any unpriced project
    (n_ppp_unpriced > 0), or a year after PPP_LAST_PRICED_YEAR. Real zero
    amounts (disclosed $0 projects) stay 0. See docs/coding_decisions.md,
    2026-10-04."""

    amounts: dict[tuple[str, str, int], tuple[str, str, str]] = {}
    if not path.is_file():
        print(f"warning: {path} not found -- USD columns will be blank for every row.", file=sys.stderr)
        return amounts
    id_to_bank = {bank_id: bank for bank, bank_id in BANKS.items()}
    for row in read_csv(path):
        bank_id = row.get("bank_id", "")
        bank = id_to_bank.get(bank_id)
        year = row.get("year", "")
        iso3 = row.get("country_code", "")
        if not bank or not iso3 or not year.isdigit():
            continue
        unpriced = int(row.get("n_ppp_unpriced") or 0)
        ppp = "" if (unpriced > 0 or int(year) > PPP_LAST_PRICED_YEAR) else row.get("ppp_2025_total", "")
        amounts[(bank, iso3, int(year))] = (
            row.get("usd_nominal_total", ""), row.get("usd_2025_total", ""), ppp,
        )
    return amounts


def _load_afdb_window_breakdown(path: Path) -> dict[tuple[str, int], dict]:
    """{(iso3, year): {afdb_ordinary_n, afdb_ordinary_usd, afdb_concessional_n,
    afdb_concessional_usd}} -- see build_afdb_window_breakdown.py."""

    breakdown: dict[tuple[str, int], dict] = {}
    if not path.is_file():
        print(f"warning: {path} not found -- AfDB's ordinary/concessional columns will be blank.", file=sys.stderr)
        return breakdown
    for row in read_csv(path):
        year = row.get("year", "")
        iso3 = row.get("iso3", "")
        if not iso3 or not year.isdigit():
            continue
        breakdown[(iso3, int(year))] = row
    return breakdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--eligibility", type=Path, default=ELIGIBILITY_CSV)
    parser.add_argument("--membership", type=Path, default=MEMBERSHIP_CSV)
    parser.add_argument("--commitments", type=Path, default=COMMITMENTS_CSV)
    parser.add_argument("--dyad-country-year", type=Path, default=DYAD_COUNTRY_YEAR)
    parser.add_argument("--afdb-window-breakdown", type=Path, default=AFDB_WINDOW_BREAKDOWN_CSV)
    parser.add_argument("--output", type=Path, default=PANEL_CSV)
    args = parser.parse_args(argv)

    eligibility = _load_eligibility(args.eligibility)
    membership = _load_membership(args.membership)
    usd_amounts = _load_usd_amounts(args.dyad_country_year)
    afdb_windows = _load_afdb_window_breakdown(args.afdb_window_breakdown)
    commitments = {(r["bank"], r["iso3"], r["year"]): r for r in load_commitments(args.commitments)}

    grid: dict[tuple[str, str, int], str] = {}
    for key, row in eligibility.items():
        if row.get("eligible") == "1":
            grid[key] = "rule"
    for key in commitments:
        if key not in grid:
            grid[key] = "revealed"

    rows_out: list[dict] = []
    for key in sorted(grid, key=lambda k: (k[0], k[1], k[2])):
        bank, iso3, year = key
        basis = grid[key]
        elig_row = eligibility.get(key, {})
        member_row = membership.get(key, {})
        commit_row = commitments.get(key)
        projects = commit_row["projects"] if commit_row else 0
        positive = commit_row["projects_with_positive_amount"] if commit_row else 0
        any_lending = 1 if projects else 0
        if not any_lending:
            # A genuine zero, not a missing value: this dyad-year is eligible
            # (or revealed-eligible) with no observed lending at all, so
            # there is nothing for dyad_country_year.csv to report -- "0",
            # not blank, so a blank cell always means a real data gap
            # (lending happened but no USD amount could be attached), never
            # "no lending happened."
            usd_nominal, usd_2025, ppp_2025 = "0", "0", "0"
        else:
            usd_nominal, usd_2025, ppp_2025 = usd_amounts.get(key, ("", "", ""))
        note = "" if basis == "rule" else "eligible only by revealed lending; see docs/remaining_problems_checklist.md"

        window_row = afdb_windows.get((iso3, year), {}) if bank == "AfDB" else {}
        rows_out.append({
            "bank": bank,
            "iso3": iso3,
            "year": year,
            "eligibility_basis": basis,
            "capital_share_pct": member_row.get("capital_share_pct", ""),
            "voting_power_pct": member_row.get("voting_power_pct", ""),
            "recipient_status": member_row.get("recipient_status", ""),
            "member_since": elig_row.get("member_since", "") or member_row.get("accession_date", "")[:4],
            "projects": projects,
            "projects_with_positive_amount": positive,
            "any_lending": any_lending,
            "usd_nominal_total": usd_nominal,
            "usd_2025_total": usd_2025,
            "ppp_2025_total": ppp_2025,
            "afdb_ordinary_n": window_row.get("afdb_ordinary_n", ""),
            "afdb_ordinary_usd": window_row.get("afdb_ordinary_usd", ""),
            "afdb_concessional_n": window_row.get("afdb_concessional_n", ""),
            "afdb_concessional_usd": window_row.get("afdb_concessional_usd", ""),
            "note": note,
        })

    write_csv(args.output, FIELDS, rows_out)

    revealed = sum(1 for r in rows_out if r["eligibility_basis"] == "revealed")
    with_lending = sum(1 for r in rows_out if r["any_lending"])
    print(f"{'bank':6} {'rows':>7} {'rule':>7} {'revealed':>9} {'with lending':>13}")
    for bank in CANONICAL_BANKS:
        bank_rows = [r for r in rows_out if r["bank"] == bank]
        if not bank_rows:
            continue
        print(
            f"{bank:6} {len(bank_rows):7} "
            f"{sum(1 for r in bank_rows if r['eligibility_basis'] == 'rule'):7} "
            f"{sum(1 for r in bank_rows if r['eligibility_basis'] == 'revealed'):9} "
            f"{sum(1 for r in bank_rows if r['any_lending']):13}"
        )
    print(f"\n{len(rows_out)} dyad-years total ({revealed} revealed-only, {with_lending} with observed lending)")
    output_label = args.output.relative_to(REPO) if args.output.is_relative_to(REPO) else args.output
    print(f"-> {output_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
