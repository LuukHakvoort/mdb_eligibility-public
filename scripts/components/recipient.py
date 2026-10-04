"""Component B' -- recipient status: could this bank actually lend to this
country, as opposed to the country merely being a shareholder?

This is deliberately a separate question from bare membership
(``components/membership.py``). CLAUDE.md's own schema note says Component B
is "recipient status, not bare membership", and its "Known traps" section
exists specifically because the two diverge (AIIB's 111 approved members vs.
~40 with projects; IDB's 48 members vs. 26 borrowing). Bare membership is
still what a membership list should show (Germany *is* an AIIB shareholder);
recipient status is what eligibility's Component B should use.

Driven by each bank's ``b_basis`` in ``data/manual/banks.json``
(docs/architecture.md decision 3):

- ``membership_only``: the recipient/non-recipient split isn't a membership
  question for this bank at all -- it's Component C (EBRD's countries of
  operations) or Component D (IBRD/IDA's income window). Recipient status
  here just mirrors bare membership; the real restriction is applied
  elsewhere in the A-E combination.
- ``no_membership_condition``: this bank doesn't gate lending on recipient
  membership (EIB outside the EU, BADEA). Always a confident True; again, the
  real restriction is Component C.
- ``needs_recipient_research``: read from ``data/manual/recipient_status.csv``,
  a snapshot classification (borrowing/non_borrowing/unknown) researched from
  each bank's own published list. No dates: every row in that file currently
  has a blank start_year/end_year, so this is a constant-across-2002-2026
  classification, same honest-snapshot caveat as shareholders_panel.csv's
  non-Wayback banks -- not because status never changes (AIIB's non-borrowing
  Gulf states in 2002 could differ from 2026), but because no source gives a
  date to change it on.

**``data/manual/non_regional_shareholders.csv`` (2026-10-02) -- a closed
override, checked before the ``membership_only`` branch.** IBRD and EBRD
are the only two banks still on ``membership_only``, which reads bare
shareholding as recipient status. That's correct for the ~150+ genuine
borrowing members of each bank, but wrong for their non-regional donor
shareholders (the US, Japan, Germany, France, UK, Canada, and more) --
real shareholders who fund the bank but have never been, and structurally
cannot be, borrowing recipients (IBRD's own description of itself: lending
to "middle-income and creditworthy low-income countries"; EBRD's own
history page: founded for "central and eastern Europe," serving "all its
shareholders... not just those countries which receive its investments").
This is the exact bug class `scripts/build.py`'s own docstring already
names as fixed once before for AIIB/Germany and IDB/USA/Canada -- by
giving those banks a real ``recipient_status.csv`` instead of bare
membership. IBRD/EBRD's full membership (~190 and ~75 countries
respectively) is too large to individually re-research the same way in one
pass, so this is a **targeted, closed list of confirmed exceptions**
instead: every (bank, iso3) pair on it is a sourced, zero-ever-observed-
lending non-regional shareholder (see docs/coding_decisions.md,
2026-10-02) and resolves to a confident False, overriding the membership
fallback; every country *not* on the list is untouched.

A bank absent from banks.json, or a (bank, iso3) pair with no
recipient_status.csv row at all, is None -- not a guess.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _panel import MANUAL_DIR, read_csv  # noqa: E402
from components import membership  # noqa: E402

BANKS_JSON = MANUAL_DIR / "banks.json"
RECIPIENT_STATUS_CSV = MANUAL_DIR / "recipient_status.csv"
NON_REGIONAL_SHAREHOLDERS_CSV = MANUAL_DIR / "non_regional_shareholders.csv"

STATUS_TO_BOOL = {"borrowing": True, "non_borrowing": False, "unknown": None}


def load_b_basis() -> dict[str, str]:
    """{bank: b_basis}, from banks.json."""

    if not BANKS_JSON.is_file():
        return {}
    data = json.loads(BANKS_JSON.read_text(encoding="utf-8"))
    return {entry["code"]: entry["b_basis"] for entry in data.get("banks", [])}


def load_c_basis() -> dict[str, str]:
    """{bank: c_basis}, from banks.json -- see components/mandate.py."""

    if not BANKS_JSON.is_file():
        return {}
    data = json.loads(BANKS_JSON.read_text(encoding="utf-8"))
    return {entry["code"]: entry.get("c_basis", "") for entry in data.get("banks", [])}


def load_d_basis() -> dict[str, str]:
    """{bank: d_basis}, from banks.json -- see components/window.py."""

    if not BANKS_JSON.is_file():
        return {}
    data = json.loads(BANKS_JSON.read_text(encoding="utf-8"))
    return {entry["code"]: entry.get("d_basis", "") for entry in data.get("banks", [])}


def load_recipient_status() -> dict[tuple[str, str], bool | None]:
    """{(bank, iso3): True/False/None}, from recipient_status.csv."""

    status: dict[tuple[str, str], bool | None] = {}
    if not RECIPIENT_STATUS_CSV.is_file():
        return status
    for row in read_csv(RECIPIENT_STATUS_CSV):
        bank, iso3 = row.get("bank", ""), row.get("iso3", "")
        if not bank or not iso3:
            continue
        status[(bank, iso3)] = STATUS_TO_BOOL.get(row.get("status", ""))
    return status


def load_non_regional_shareholders() -> set[tuple[str, str]]:
    """{(bank, iso3)} -- confirmed non-regional/donor-only shareholders that
    are never a recipient, regardless of bare membership evidence. See the
    module docstring's "non_regional_shareholders.csv" section."""

    if not NON_REGIONAL_SHAREHOLDERS_CSV.is_file():
        return set()
    return {
        (row["bank"], row["iso3"])
        for row in read_csv(NON_REGIONAL_SHAREHOLDERS_CSV)
        if row.get("bank") and row.get("iso3")
    }


def is_recipient(
    bank: str,
    iso3: str,
    year: int,
    b_basis: dict[str, str] | None = None,
    recipient_status: dict[tuple[str, str], bool | None] | None = None,
    membership_evidence: dict[tuple[str, str], dict] | None = None,
    non_regional_shareholders: set[tuple[str, str]] | None = None,
) -> bool | None:
    basis = (b_basis if b_basis is not None else load_b_basis()).get(bank)
    if basis is None:
        return None

    if basis == "no_membership_condition":
        return True
    if basis == "membership_only":
        non_regional = (
            non_regional_shareholders if non_regional_shareholders is not None
            else load_non_regional_shareholders()
        )
        if (bank, iso3) in non_regional:
            return False
        return membership.is_member(bank, iso3, year, membership_evidence)
    if basis == "needs_recipient_research":
        table = recipient_status if recipient_status is not None else load_recipient_status()
        return table.get((bank, iso3))
    raise ValueError(f"unknown b_basis {basis!r} for bank {bank!r}")
