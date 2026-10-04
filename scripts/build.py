"""Combine components A-E into data/output/eligibility.csv.

eligible = bank_exists & recipient & in_mandate & window_ok & ~barred, using
three-valued logic throughout (_panel.and3/not3): a definite False anywhere
makes the row False even if another component is still unknown; otherwise any
unknown component makes the row unknown. Only every component being resolved
True yields a definite True. See docs/architecture.md principle 4 -- unknown
is null, never guessed -- and components/mandate.py, window.py's docstrings
for exactly what's still missing.

**Component E's default (docs/coding_decisions.md, 2026-09-27).**
`components/bars.py` returns None for any (bank, iso3) pair with no row at
all in bar_events.csv -- correctly, since absence of a logged bar is not the
same as a confirmed non-accrual check. Left as None, that single component
propagated NULL through `and3` into ~84% of all eligibility.csv rows, most of
which have nothing to do with sanctions or non-accrual at all -- it made
`eligible` mostly unusable as a panel-construction filter. Per user decision:
`eligible` here treats an unlogged bar as *not evidenced* (False) rather than
unknown, since bar_events.csv is deliberately exhaustive for the ~20 known
sanctions/non-accrual episodes (docs/architecture.md's own "hand-maintained,
~20 events" scope) -- absence is the normal case, not a gap. `barred_evidenced`
records whether E was actually resolved (1) or defaulted (0) for that row, and
`eligible_strict` keeps the old, fully-conservative three-valued combination
(NULL wherever E was defaulted) for anyone who wants the stricter cut. Use
`eligible` for the panel; use `eligible_strict` to see exactly which rows ride
on this default.

Component B here is **recipient status** (components/recipient.py), not bare
membership -- CLAUDE.md's schema note: "member: recipient status, not bare
membership". Bare shareholder membership is a different question, answered by
data/output/membership.csv (build_membership.py), a separate, standalone
output. Run `make build` (which runs build_membership.py first) rather than
this script alone, or `eligible` will read a stale recipient_status.csv
snapshot. See docs/coding_decisions.md, 2026-09-21, for why the two were
split: reusing bare membership for B was the bug that started this rebuild
(AIIB/Germany, IDB/USA and IDB/Canada all showed member=1 as eligibility's
Component B, which would have made three well-known non-borrowers eligible
recipients the moment C and D are filled in).

The grid is every (bank, iso3) pair with at least one piece of evidence
anywhere in this repo -- accession_dates.csv, shareholders_panel.csv, or
commitments.csv -- times 2002-2026. This is narrower than the collection
plan's eventual full country-universe grid (every country x every bank,
~62,000 rows, session 1's grid.py, not built yet); it's every pair this repo
can currently say anything about at all, which is what a first real
eligibility.csv needs to be useful rather than mostly empty rows.

Usage:  python3 scripts/build.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from components import bars, existence, mandate, membership, recipient, window  # noqa: E402
from _panel import (  # noqa: E402
    COMMITMENTS_CSV, ELIGIBILITY_CSV, ELIGIBILITY_FIELDS, EXTRACTED_DIR, MANUAL_DIR,
    MAX_YEAR, MIN_YEAR, REPO, YEARS, and3, not3, read_csv, write_csv,
)


def _flag_text(value: bool | None) -> str:
    if value is None:
        return ""
    return "1" if value else "0"


def _build_grid() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for path in (MANUAL_DIR / "accession_dates.csv", EXTRACTED_DIR / "shareholders_panel.csv",
                 COMMITMENTS_CSV):
        if not path.is_file():
            continue
        for row in read_csv(path):
            bank, iso3 = row.get("bank", ""), row.get("iso3", "")
            if bank and iso3:
                pairs.add((bank, iso3))
    return pairs


def main() -> int:
    existence_windows = existence.load_existence()
    membership_evidence = membership.load_membership_evidence()
    b_basis = recipient.load_b_basis()
    c_basis = recipient.load_c_basis()
    d_basis = recipient.load_d_basis()
    recipient_status = recipient.load_recipient_status()
    non_regional_shareholders = recipient.load_non_regional_shareholders()
    oghist_income = window.load_oghist_income()
    oghist_lending_category = window.load_oghist_lending_category()
    au_membership = mandate.load_au_membership()
    arab_league_membership = mandate.load_arab_league_membership()
    eu_membership = mandate.load_eu_membership()
    ebrd_mandate_spells = mandate.load_mandate_spells("EBRD")
    eib_mandate_spells = mandate.load_mandate_spells("EIB")
    bar_events = bars.load_bar_events()

    pairs = sorted(_build_grid())
    print(f"grid: {len(pairs)} (bank, iso3) pairs with at least one piece of evidence, "
          f"x {len(YEARS)} years = {len(pairs) * len(YEARS)} rows")

    rows: list[dict] = []
    counts = {"true": 0, "false": 0, "null": 0}
    for bank, iso3 in pairs:
        member_since = None
        entry = membership_evidence.get((bank, iso3))
        if entry and entry.get("accession_year") is not None:
            member_since = entry["accession_year"]

        for year in YEARS:
            a = existence.bank_exists(bank, year, existence_windows)
            b = recipient.is_recipient(bank, iso3, year, b_basis, recipient_status, membership_evidence,
                                        non_regional_shareholders)
            c = mandate.in_mandate(bank, iso3, year, c_basis, b_basis, recipient_status, membership_evidence,
                                    au_membership, arab_league_membership, eu_membership, ebrd_mandate_spells,
                                    eib_mandate_spells, non_regional_shareholders)
            d = window.window_ok(bank, iso3, year, d_basis, oghist_income, oghist_lending_category)
            e = bars.is_barred(bank, iso3, year, bar_events)
            e_evidenced = e is not None
            eligible_strict = and3(a, b, c, d, not3(e))
            eligible = and3(a, b, c, d, not3(e if e_evidenced else False))

            counts["null" if eligible is None else ("true" if eligible else "false")] += 1
            note = "" if e_evidenced else "barred defaulted to not_evidenced (no bar_events.csv row)"
            rows.append({
                "bank": bank,
                "iso3": iso3,
                "year": year,
                "bank_exists": _flag_text(a),
                "member": _flag_text(b),
                "in_mandate": _flag_text(c),
                "window_ok": _flag_text(d),
                "barred": _flag_text(e if e_evidenced else False),
                "barred_evidenced": _flag_text(e_evidenced),
                "eligible": _flag_text(eligible),
                "eligible_strict": _flag_text(eligible_strict),
                "member_since": member_since if member_since is not None else "",
                "source": "",
                "note": note,
            })

    write_csv(ELIGIBILITY_CSV, ELIGIBILITY_FIELDS, rows)
    print(f"eligible: {counts['true']} true, {counts['false']} false, {counts['null']} unknown "
          f"(unknown is expected while Components B/C/D still have real gaps -- see "
          f"docs/manual_data_checklist.md)")
    print(f"-> {ELIGIBILITY_CSV.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
