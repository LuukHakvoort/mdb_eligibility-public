"""Merge hand-entered accession data into data/manual/accession_dates.csv.

accession_dates.csv is regenerated wholesale by seed_accession_dates.py
whenever the underlying commitments data changes -- which would silently
destroy any accession_date/source/note a person had already typed in,
anywhere those three columns are non-blank. This script is the other half:
it overlays hand-entered work from a second file (a CSV, or an Apple Numbers
file with one table shaped the same way) back onto the current
accession_dates.csv, keyed on (bank, iso3), and:

- **updates** accession_date/source/note on a matching row when the source
  file has something in at least one of them;
- **adds** a row for a (bank, iso3) pair the source file has but the current
  seed doesn't -- typically a member with no observed lending in the project
  data, which the dyad-derived seed can never produce on its own (AIIB/NDB
  members added by hand from the bank's own member list are exactly this
  case). Its earliest_observed_year is left blank, correctly: there is no
  observed lending to derive it from.
- **never removes or blanks** a row. A pair present only in the current file
  keeps its earliest_observed_year hint untouched.

Usage:  python3 scripts/merge_accession_dates.py SOURCE_FILE [--apply]

Without --apply, prints a summary and changes nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _panel import MANUAL_DIR, REPO, read_csv, write_csv
from _reference import country_name

TARGET = MANUAL_DIR / "accession_dates.csv"
FIELDNAMES = [
    "bank", "iso3", "country_name", "accession_date", "source", "note",
    "earliest_observed_year",
]


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))  # Numbers stores "2021" as 2021.0
    return str(value).strip()


def load_source_rows(path: Path) -> list[dict[str, str]]:
    """Read SOURCE_FILE as a list of {bank, iso3, country_name, accession_date,
    source, note} dicts, from either a CSV or a single-table .numbers file."""

    if path.suffix.lower() == ".numbers":
        try:
            from numbers_parser import Document
        except ImportError as exc:
            raise SystemExit(
                "Reading a .numbers file requires: pip install numbers-parser"
            ) from exc
        doc = Document(str(path))
        tables = [table for sheet in doc.sheets for table in sheet.tables]
        if len(tables) != 1:
            raise SystemExit(
                f"{path} has {len(tables)} tables; expected exactly one "
                "(pass a CSV export instead if it has more)."
            )
        rows = tables[0].rows(values_only=True)
        header = [str(cell).strip() for cell in rows[0]]
        return [
            {header[i]: _clean(cell) for i, cell in enumerate(row)}
            for row in rows[1:]
        ]
    return read_csv(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="A CSV or .numbers file with the same columns")
    parser.add_argument("--apply", action="store_true", help="Write the merge; otherwise dry-run")
    args = parser.parse_args(argv)

    if not TARGET.is_file():
        print(f"error: {TARGET} does not exist. Run scripts/seed_accession_dates.py first.",
              file=sys.stderr)
        return 2
    if not args.source.is_file():
        print(f"error: {args.source} does not exist.", file=sys.stderr)
        return 2

    current_rows = read_csv(TARGET)
    current_by_key = {(row["bank"], row["iso3"]): row for row in current_rows}

    source_rows = load_source_rows(args.source)
    updated = 0
    added = 0
    unchanged_conflicts: list[tuple[str, str]] = []

    for row in source_rows:
        bank, iso3 = row.get("bank", "").strip(), row.get("iso3", "").strip()
        if not bank or not iso3:
            continue
        filled = {
            field: row.get(field, "").strip()
            for field in ("accession_date", "source", "note")
            if row.get(field, "").strip()
        }
        if not filled:
            continue  # a blank worklist row in the source file; nothing to overlay
        key = (bank, iso3)
        if key in current_by_key:
            target_row = current_by_key[key]
            changed = any(target_row.get(field, "") != value for field, value in filled.items())
            existing_conflict = any(
                target_row.get(field) and target_row.get(field) != value
                for field, value in filled.items()
            )
            if existing_conflict:
                unchanged_conflicts.append(key)
                continue
            if changed:
                target_row.update(filled)
                updated += 1
        else:
            new_row = {
                "bank": bank,
                "iso3": iso3,
                "country_name": row.get("country_name", "").strip() or country_name(iso3),
                "accession_date": "",
                "source": "",
                "note": "",
                "earliest_observed_year": "",
            }
            new_row.update(filled)
            current_by_key[key] = new_row
            current_rows.append(new_row)
            added += 1

    print(f"source: {args.source} ({len(source_rows)} rows read)")
    print(f"{updated} row(s) would be updated, {added} row(s) would be added")
    if unchanged_conflicts:
        print(f"{len(unchanged_conflicts)} row(s) already had different data in a filled field "
              "and were left untouched -- resolve by hand:", file=sys.stderr)
        for bank, iso3 in unchanged_conflicts:
            print(f"  {bank} {iso3}", file=sys.stderr)

    if not args.apply:
        print("\nDry run; nothing written. Re-run with --apply to write the merge.")
        return 0

    from _panel import CANONICAL_BANKS
    order = {bank: index for index, bank in enumerate(CANONICAL_BANKS)}
    current_rows.sort(key=lambda row: (order.get(row["bank"], 99), row["iso3"]))
    write_csv(TARGET, FIELDNAMES, current_rows)
    print(f"\nWrote {TARGET.relative_to(REPO)}: {updated} updated, {added} added.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
