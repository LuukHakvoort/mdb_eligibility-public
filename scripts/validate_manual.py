"""Validate the hand-maintained CSVs under data/manual/.

Shared checks, applied to every file below:

- a column is missing from the header, or a row has a missing/extra field;
- ``bank`` is not one of the canonical codes;
- ``iso3`` (where the schema has one) is not a valid ISO 3166-1 alpha-3 code;
- a required value is blank;
- a filled-in date needs a non-blank ``source`` -- every coded value needs a
  citation (CLAUDE.md: "Every row needs a source");
- a date column holds something other than YYYY, YYYY-MM, or YYYY-MM-DD, or
  falls outside 1944-2026.

Per file:

- ``accession_dates.csv``: no duplicate (bank, iso3) pair; ``country_name``
  mismatching the codelist name for its ``iso3`` is a warning, not an error.
- ``bank_existence.csv``: no duplicate ``bank`` (one row per bank).
- ``bar_events.csv``: duplicate (bank, iso3, event_type, start_date) rows
  only -- recurring event types and repeated blank placeholder rows for the
  same country are expected, not an error.
- ``recipient_status.csv``: no duplicate (bank, iso3) pair; ``status`` must be
  one of borrowing/non_borrowing/unknown.

Also checks ``banks.json``: every canonical bank code is present exactly
once, and every ``b_basis`` is one of the three values components/build.py
understands.

Every problem is reported with its line number, not just the first one.

Usage:  python3 scripts/validate_manual.py [path ...]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from _panel import CANONICAL_BANKS, MANUAL_DIR
from _reference import CODE_TO_NAME, ISO3_CODES

VALID_B_BASIS = {"membership_only", "no_membership_condition", "needs_recipient_research"}
VALID_C_BASIS = {"trivial_region", "spell_based", "computed"}
VALID_D_BASIS = {"oghist_income", "classification_spells", "no_formal_window"}

REPO = Path(__file__).resolve().parents[1]

DATE_PATTERN = re.compile(r"^(\d{4})(?:-\d{2}(?:-\d{2})?)?$")
EARLIEST_YEAR = 1944  # Bretton Woods; no MDB fact in this project predates it.
LATEST_YEAR = 2026


@dataclass(frozen=True)
class Schema:
    fieldnames: list[str]
    required: list[str]
    date_fields: list[str] = field(default_factory=list)  # each needs a non-blank `source` if filled
    dedupe_key: tuple[str, ...] | None = None
    has_country_name: bool = False
    allowed_values: dict[str, frozenset[str]] = field(default_factory=dict)


SCHEMAS: dict[str, Schema] = {
    "accession_dates.csv": Schema(
        fieldnames=["bank", "iso3", "country_name", "accession_date", "source", "note",
                    "earliest_observed_year"],
        required=["bank", "iso3", "country_name"],
        date_fields=["accession_date"],
        dedupe_key=("bank", "iso3"),
        has_country_name=True,
    ),
    "bank_existence.csv": Schema(
        fieldnames=["bank", "start_year", "end_year", "source", "note"],
        required=["bank", "start_year", "source"],
        date_fields=["start_year", "end_year"],
        dedupe_key=("bank",),
    ),
    "bar_events.csv": Schema(
        fieldnames=["bank", "iso3", "event_type", "start_date", "end_date", "source", "note"],
        required=["bank", "iso3", "event_type"],
        date_fields=["start_date", "end_date"],
        dedupe_key=("bank", "iso3", "event_type", "start_date"),
    ),
    "recipient_status.csv": Schema(
        fieldnames=["bank", "iso3", "status", "start_year", "end_year", "source", "note"],
        required=["bank", "iso3", "status"],
        date_fields=["start_year", "end_year"],
        dedupe_key=("bank", "iso3"),
        allowed_values={"status": frozenset({"borrowing", "non_borrowing", "unknown"})},
    ),
    "non_regional_shareholders.csv": Schema(
        # A closed override for IBRD/EBRD's membership_only Component B
        # (2026-10-02) -- a confirmed non-regional/donor-only shareholder,
        # never a recipient; see components/recipient.py's module docstring.
        fieldnames=["bank", "iso3", "source", "note"],
        required=["bank", "iso3", "source", "note"],
        dedupe_key=("bank", "iso3"),
    ),
    "au_membership.csv": Schema(
        fieldnames=["iso3", "start_year", "end_year", "source", "note"],
        required=["iso3"],
        date_fields=["start_year", "end_year"],
    ),
    "arab_league_membership.csv": Schema(
        fieldnames=["iso3", "start_year", "end_year", "source", "note"],
        required=["iso3"],
        date_fields=["start_year", "end_year"],
    ),
    "eu_membership.csv": Schema(
        fieldnames=["iso3", "start_year", "end_year", "source", "note"],
        required=["iso3"],
        date_fields=["start_year", "end_year"],
    ),
    "mandate_spells.csv": Schema(
        fieldnames=["bank", "iso3", "basis", "start_year", "end_year", "source", "note"],
        required=["bank", "iso3", "basis"],
        date_fields=["start_year", "end_year"],
        dedupe_key=("bank", "iso3", "basis", "start_year"),
    ),
    "accepted_revealed_exceptions.csv": Schema(
        # check_revealed.py's allowlist of already-reviewed, already-decided
        # revealed-eligibility violations (2026-09-30) -- see docs/coding_
        # decisions.md. A judgement-call ledger, not computed data: each row
        # names the specific (bank, iso3, year) a prior session already
        # investigated and decided not to change, with its own reasoning.
        # Not `date_fields`: that check demands a `source` column this file
        # doesn't have -- the citation lives in `note` itself here instead.
        fieldnames=["bank", "iso3", "year", "reason", "decided_date", "note"],
        required=["bank", "iso3", "year", "reason", "decided_date", "note"],
        dedupe_key=("bank", "iso3", "year"),
        allowed_values={"reason": frozenset({
            "graduated_transitional_lending", "asdb_graduated_dmc_technical_assistance",
            "eib_own_risk_no_country_list", "state_succession_pre_independence",
            "regional_facility_attribution_confirmed", "humanitarian_channel_exception_confirmed",
            "confirmed_blended_financing_exception",
        })},
    ),
    "annual_reports.csv": Schema(
        # No `iso3` column (this indexes documents, not countries) and no
        # `date_fields` -- `url` is this file's citation, there's no separate
        # `source` column for the date_fields "needs a source" check to read.
        # `document` distinguishes a bank's two documents for the same year
        # (AIIB: year-end financial statements for capital, annual report
        # for voting power); blank for every bank with just one.
        fieldnames=["bank", "year", "url", "document", "note"],
        required=["bank", "year", "url"],
        dedupe_key=("bank", "year", "document"),
    ),
}

DEFAULT_TARGETS = [MANUAL_DIR / name for name in SCHEMAS]


def validate(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not path.is_file():
        return [f"{path}: file does not exist"], []

    schema = SCHEMAS.get(path.name)
    if schema is None:
        return [f"{path.name}: no known schema for this file (add one to SCHEMAS)"], []

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [name for name in schema.fieldnames if name not in header]
        extra = [name for name in header if name not in schema.fieldnames]
        if missing:
            errors.append(f"{path.name}: header is missing column(s): {', '.join(missing)}")
        if extra:
            errors.append(f"{path.name}: header has unexpected column(s): {', '.join(extra)}")
        if missing:
            return errors, warnings  # row checks would report the same fault repeatedly

        seen: dict[tuple[str, ...], int] = {}
        for line, row in enumerate(reader, start=2):
            if None in row:  # more fields on this line than in the header
                errors.append(f"{path.name}:{line}: row has more fields than the header")
                continue
            if any(value is None for value in row.values()):
                errors.append(f"{path.name}:{line}: row has fewer fields than the header")
                continue
            values = {key: (value or "").strip() for key, value in row.items()}

            for name in schema.required:
                if not values[name]:
                    errors.append(f"{path.name}:{line}: {name} is blank")

            bank = values.get("bank", "")
            iso3 = values.get("iso3", "")
            if bank and bank not in CANONICAL_BANKS:
                errors.append(
                    f"{path.name}:{line}: unknown bank {bank!r}; expected one of "
                    f"{', '.join(CANONICAL_BANKS)}"
                )
            if "iso3" in schema.fieldnames and iso3 and iso3 not in ISO3_CODES:
                errors.append(f"{path.name}:{line}: {iso3!r} is not a valid ISO 3166-1 alpha-3 code")

            for field_name, allowed in schema.allowed_values.items():
                value = values.get(field_name, "")
                if value and value not in allowed:
                    errors.append(
                        f"{path.name}:{line}: {field_name} {value!r} is not one of "
                        f"{', '.join(sorted(allowed))}"
                    )

            if schema.dedupe_key:
                key = tuple(values.get(field_name, "") for field_name in schema.dedupe_key)
                if all(key):  # a blank component (e.g. no start_date yet) never counts as a duplicate
                    previous = seen.get(key)
                    if previous:
                        errors.append(
                            f"{path.name}:{line}: duplicate {schema.dedupe_key} {key}; "
                            f"first seen on line {previous}"
                        )
                    else:
                        seen[key] = line

            for date_field in schema.date_fields:
                date = values.get(date_field, "")
                if not date:
                    continue
                match = DATE_PATTERN.match(date)
                if not match:
                    errors.append(
                        f"{path.name}:{line}: {date_field} {date!r} is not YYYY, YYYY-MM, or "
                        "YYYY-MM-DD"
                    )
                elif not EARLIEST_YEAR <= int(match.group(1)) <= LATEST_YEAR:
                    errors.append(
                        f"{path.name}:{line}: {date_field} {date!r} is outside "
                        f"{EARLIEST_YEAR}-{LATEST_YEAR}"
                    )
                if not values.get("source"):
                    errors.append(
                        f"{path.name}:{line}: {date_field} is filled in but source is blank"
                    )

            if schema.has_country_name:
                expected_name = CODE_TO_NAME.get(iso3, "")
                if expected_name and values["country_name"] and values["country_name"] != expected_name:
                    warnings.append(
                        f"{path.name}:{line}: country_name {values['country_name']!r} does not "
                        f"match the codelist name for {iso3} ({expected_name!r})"
                    )

    return errors, warnings


def validate_banks_json(path: Path) -> list[str]:
    if not path.is_file():
        return [f"{path.name}: file does not exist"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path.name}: invalid JSON ({exc})"]

    errors: list[str] = []
    seen: dict[str, int] = {}
    for index, entry in enumerate(data.get("banks", [])):
        code = entry.get("code", "")
        if code in seen:
            errors.append(f"{path.name}: duplicate bank code {code!r}")
        seen[code] = index
        if code not in CANONICAL_BANKS:
            errors.append(f"{path.name}: unknown bank code {code!r}")
        b_basis = entry.get("b_basis", "")
        if b_basis not in VALID_B_BASIS:
            errors.append(
                f"{path.name}: {code!r} has b_basis {b_basis!r}, not one of {sorted(VALID_B_BASIS)}"
            )
        if not entry.get("b_basis_source"):
            errors.append(f"{path.name}: {code!r} is missing b_basis_source")
        c_basis = entry.get("c_basis", "")
        if c_basis not in VALID_C_BASIS:
            errors.append(
                f"{path.name}: {code!r} has c_basis {c_basis!r}, not one of {sorted(VALID_C_BASIS)}"
            )
        if not entry.get("c_basis_source"):
            errors.append(f"{path.name}: {code!r} is missing c_basis_source")
        d_basis = entry.get("d_basis", "")
        if d_basis not in VALID_D_BASIS:
            errors.append(
                f"{path.name}: {code!r} has d_basis {d_basis!r}, not one of {sorted(VALID_D_BASIS)}"
            )
        if not entry.get("d_basis_source"):
            errors.append(f"{path.name}: {code!r} is missing d_basis_source")

    missing_banks = set(CANONICAL_BANKS) - set(seen)
    if missing_banks:
        errors.append(f"{path.name}: no entry for: {sorted(missing_banks)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", type=Path, default=DEFAULT_TARGETS)
    args = parser.parse_args(argv)

    all_errors: list[str] = []
    for path in args.paths or DEFAULT_TARGETS:
        errors, warnings = validate(path)
        all_errors += errors
        for warning in warnings:
            print(f"warning: {warning}")
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if not errors:
            print(f"{path.name}: OK ({len(warnings)} warning(s))")

    if args.paths == DEFAULT_TARGETS or not args.paths:
        banks_json_errors = validate_banks_json(MANUAL_DIR / "banks.json")
        all_errors += banks_json_errors
        for error in banks_json_errors:
            print(f"error: {error}", file=sys.stderr)
        if not banks_json_errors:
            print("banks.json: OK")

    if all_errors:
        print(f"\n{len(all_errors)} error(s)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
