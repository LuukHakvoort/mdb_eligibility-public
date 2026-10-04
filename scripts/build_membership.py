"""Combine bare membership + shareholding + recipient status into
data/output/membership.csv: "who is a shareholder of this bank, and are they
a recipient" -- a standalone output, not an intermediate step toward
eligibility.csv (see docs/architecture.md and the plan this was built from).

Three signals per (bank, iso3, year), each computed by its own module so a
reader can trust each column independently:

- ``member`` (components/membership.py): bare shareholder/membership status.
  Never filtered to recipients -- a non-borrowing AIIB shareholder like
  Germany belongs in this file with member=1, exactly as much as a borrowing
  one.
- ``capital_share_pct`` / ``voting_power_pct`` (shareholders_panel.csv):
  unchanged, still separate values, still blank-not-zero.
- ``recipient_status`` (components/recipient.py): could this bank actually
  lend here, per that bank's b_basis (data/manual/banks.json). Distinct from
  `member` on purpose -- this is the column eligibility's Component B reads,
  not `member`.

Grid: every (bank, iso3) pair with at least one piece of evidence anywhere
(same scoping as build.py -- see its docstring for why this is narrower than
the eventual full country-universe grid) x 2002-2026.

Usage:  python3 scripts/build_membership.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from components import membership, recipient  # noqa: E402
from _panel import (  # noqa: E402
    COMMITMENTS_CSV, EXTRACTED_DIR, MANUAL_DIR, OUTPUT_DIR, REPO, YEARS,
    read_csv, write_csv,
)

MEMBERSHIP_CSV = OUTPUT_DIR / "membership.csv"
FIELDS = [
    "bank", "iso3", "year", "member", "capital_share_pct", "voting_power_pct",
    "accession_date", "recipient_status", "member_source", "recipient_source", "note",
]

# Banks with a Wayback-reconstructed, genuinely complete member roster
# (data/extracted/wayback_accessions_<id>.csv): absence from that roster is
# confident evidence of non-membership, stronger than the general
# lower-bound-from-observed-lending heuristic in components/membership.py.
# Without this, IsDB's 14 non-member Special-Assistance-Program recipients
# (docs/coding_decisions.md, 2026-09-21) would show member=1 from their
# observed-lending year on, which is wrong: they were never shareholders.
_AUTHORITATIVE_ROSTER_BANKS = {"EBRD": "ebrd", "IsDB": "isdb"}


def _load_authoritative_rosters() -> dict[str, set[str]]:
    rosters: dict[str, set[str]] = {}
    for bank, bank_id in _AUTHORITATIVE_ROSTER_BANKS.items():
        path = EXTRACTED_DIR / f"wayback_accessions_{bank_id}.csv"
        if path.is_file():
            rosters[bank] = {row["iso3"] for row in read_csv(path)}
    return rosters


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


def _load_shares() -> dict[tuple[str, str, int], dict]:
    shares: dict[tuple[str, str, int], dict] = {}
    path = EXTRACTED_DIR / "shareholders_panel.csv"
    if not path.is_file():
        return shares
    for row in read_csv(path):
        year = row.get("year", "")
        if not year.isdigit():
            continue
        shares[(row["bank"], row["iso3"], int(year))] = row
    return shares


def main() -> int:
    membership_evidence = membership.load_membership_evidence()
    b_basis = recipient.load_b_basis()
    recipient_status = recipient.load_recipient_status()
    rosters = _load_authoritative_rosters()
    shares = _load_shares()

    pairs = sorted(_build_grid())
    print(f"grid: {len(pairs)} (bank, iso3) pairs with at least one piece of evidence, "
          f"x {len(YEARS)} years = {len(pairs) * len(YEARS)} rows")

    rows: list[dict] = []
    counts = {"member_true": 0, "member_false": 0, "member_null": 0,
              "recipient_true": 0, "recipient_false": 0, "recipient_null": 0}
    roster_overrides = 0

    for bank, iso3 in pairs:
        entry = membership_evidence.get((bank, iso3))
        accession_date = ""
        if entry and entry.get("accession_year") is not None:
            accession_date = str(entry["accession_year"])

        member_source = "data/manual/accession_dates.csv"
        recipient_source = {
            "membership_only": "components/recipient.py (mirrors member; real split is Component C or D)",
            "no_membership_condition": "data/manual/banks.json (no_membership_condition)",
            "needs_recipient_research": "data/manual/recipient_status.csv",
        }.get(b_basis.get(bank, ""), "")

        roster = rosters.get(bank)
        note = ""

        for year in YEARS:
            member = membership.is_member(bank, iso3, year, membership_evidence)
            if roster is not None and member is True and iso3 not in roster and accession_date == "":
                # Lower-bound heuristic said True (observed lending / shares panel
                # presence), but this bank has a complete member roster and this
                # country isn't on it -- the roster is stronger evidence.
                member = False
                note = "Not on the Wayback-reconstructed member roster; observed lending is real but not shareholding."
                roster_overrides += 1

            rec = recipient.is_recipient(bank, iso3, year, b_basis, recipient_status, membership_evidence)

            counts["member_null" if member is None else ("member_true" if member else "member_false")] += 1
            counts["recipient_null" if rec is None else ("recipient_true" if rec else "recipient_false")] += 1

            share_row = shares.get((bank, iso3, year), {})
            rows.append({
                "bank": bank,
                "iso3": iso3,
                "year": year,
                "member": _flag_text(member),
                "capital_share_pct": share_row.get("capital_share_pct", ""),
                "voting_power_pct": share_row.get("voting_power_pct", ""),
                "accession_date": accession_date,
                "recipient_status": _flag_text(rec),
                "member_source": member_source,
                "recipient_source": recipient_source,
                "note": note,
            })

    write_csv(MEMBERSHIP_CSV, FIELDS, rows)
    print(f"member:            {counts['member_true']} true, {counts['member_false']} false, "
          f"{counts['member_null']} unknown ({roster_overrides} roster-corrected)")
    print(f"recipient_status:  {counts['recipient_true']} true, {counts['recipient_false']} false, "
          f"{counts['recipient_null']} unknown")
    print(f"-> {MEMBERSHIP_CSV.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
