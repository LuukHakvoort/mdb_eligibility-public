"""Build data/extracted/commitments.csv from the project scraper's dyad file.

As of 2026-09-16 the scraper ships its own bank x country x year aggregation
(output/dyad_country_year.csv), already using approval_year (not
commitment_year), reconciled against official portfolio-file backbones for
ADB/AfDB/IsDB/CABEI/World Bank, and checked by its own backstop.py. Re-deriving
the same aggregation independently from the 14 per-bank CSVs would only
duplicate that logic and drift out of sync with it -- both approaches read the
same underlying rows downstream, so independent re-derivation buys no real
verification, only maintenance cost. See docs/architecture.md's "Decisions to
log" and the plan behind this rewrite for the reasoning.

This script is a thin re-projection: it does not re-derive country/year
placement itself. Rows the scraper's own pipeline could not place on a single
country (regional groupings, no disclosed year) are read from its
dyad_unallocated_year.csv rather than recomputed here.

**AfDB reads straight from `dyad_country_year.csv` like every other bank**
(2026-09-28 -- previously routed through a separate AfDB/ADF split; see
docs/coding_decisions.md for why that split was undone). Its
ordinary-vs-concessional breakdown is a separate file,
`data/extracted/afdb_window_breakdown.csv` (`scripts/
build_afdb_window_breakdown.py`), joined onto AfDB's row as extra columns by
`build_mdb_panel.py` -- not a second row here.

Usage:  python3 scripts/build_commitments.py [--positive-only]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from _panel import (
    BANK_COVERAGE_CSV, BANKS, CANONICAL_BANKS, COMMITMENTS_CSV, COMMITMENTS_FIELDS,
    EXTRACTED_DIR, REPO, REPORTS_DIR, read_csv, write_csv,
)

REFERENCE_REPO = Path(__file__).resolve().parents[2] / "mdbs_scraper_corrected"
REFERENCE_OUTPUT = REFERENCE_REPO / "output"

DYAD_COUNTRY_YEAR = REFERENCE_OUTPUT / "dyad_country_year.csv"
DYAD_UNALLOCATED = REFERENCE_OUTPUT / "dyad_unallocated_year.csv"
BANKS_JSON = REFERENCE_REPO / "mdbs_scraper" / "banks.json"

BANK_COVERAGE_FIELDS = ["bank", "coverage_start_year", "coverage_end_year", "note"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scraper_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(REFERENCE_REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def build_bank_coverage() -> list[dict]:
    """Re-project banks.json's coverage_start_year/coverage_end_year for each bank.

    These mark data-coverage gaps in the source, not bank non-existence (see
    _panel.load_bank_coverage's docstring). Written here, not hand-maintained,
    since it's read straight off the scraper's own registry -- a fact about
    that source, not a judgement call.
    """

    payload = json.loads(BANKS_JSON.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in payload["banks"]}
    rows = []
    for bank, bank_id in BANKS.items():
        entry = by_id.get(bank_id, {})
        start = entry.get("coverage_start_year")
        end = entry.get("coverage_end_year")
        if start is None and end is None:
            continue
        rows.append({
            "bank": bank,
            "coverage_start_year": start or "",
            "coverage_end_year": end or "",
            "note": (entry.get("coverage_notes") or "")[:200],
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--positive-only", action="store_true",
        help="Count a dyad-year only when a positive amount is disclosed (n_with_amount)",
    )
    args = parser.parse_args(argv)

    for path in (DYAD_COUNTRY_YEAR, DYAD_UNALLOCATED, BANKS_JSON):
        if not path.is_file():
            print(f"error: missing {path}. Run the scraper first: "
                  f"main.py --all-banks --combine, then main.py --dyad", file=sys.stderr)
            return 2

    id_to_bank = {bank_id: bank for bank, bank_id in BANKS.items()}
    dyad_rows = read_csv(DYAD_COUNTRY_YEAR)

    rows_out: list[dict] = []
    skipped_banks: set[str] = set()
    for row in dyad_rows:
        bank_id = row["bank_id"]
        bank = id_to_bank.get(bank_id)
        if bank is None:
            skipped_banks.add(bank_id)  # a bank in the dyad file we don't track (e.g. imf, if ever enabled)
            continue
        iso3 = row["country_code"]
        year = row["year"]
        if not iso3 or not year.isdigit():
            continue
        n_operations = int(row.get("n_operations") or 0)
        n_with_amount = int(row.get("n_with_amount") or 0)
        if args.positive_only and n_with_amount == 0:
            continue
        rows_out.append({
            "bank": bank,
            "iso3": iso3,
            "year": int(year),
            "projects": n_operations,
            "projects_with_positive_amount": n_with_amount,
        })

    bank_order = {bank: index for index, bank in enumerate(CANONICAL_BANKS)}
    rows_out.sort(key=lambda row: (bank_order.get(row["bank"], len(CANONICAL_BANKS)), row["iso3"], row["year"]))

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(COMMITMENTS_CSV, COMMITMENTS_FIELDS, rows_out)

    coverage_rows = build_bank_coverage()
    write_csv(BANK_COVERAGE_CSV, BANK_COVERAGE_FIELDS, coverage_rows)

    unallocated_rows = read_csv(DYAD_UNALLOCATED)
    unallocated_out = [
        {
            "bank": id_to_bank.get(row["bank_id"], row["bank_id"]),
            "year": row["year"],
            "countries": row.get("countries", ""),
            "n_operations": row.get("n_operations", ""),
        }
        for row in unallocated_rows
    ]
    unallocated_path = REPORTS_DIR / "commitments_unallocated.csv"
    write_csv(
        unallocated_path,
        ["bank", "year", "countries", "n_operations"],
        unallocated_out,
    )

    manifest = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "definition": (
            "a dyad-year with at least one operation disclosing a positive amount (n_with_amount)"
            if args.positive_only
            else "a dyad-year with at least one operation (n_operations), from the scraper's own "
                 "dyad_country_year.csv"
        ),
        "scraper_commit": scraper_commit(),
        "banks": len(CANONICAL_BANKS),
        "dyad_years": len(rows_out),
        "unallocated_bank_years": len(unallocated_out),
        "sources": {
            str(path.relative_to(REFERENCE_REPO)): sha256(path)
            for path in (DYAD_COUNTRY_YEAR, DYAD_UNALLOCATED, BANKS_JSON)
        },
    }
    manifest_path = EXTRACTED_DIR / "commitments_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"{'bank':6} {'dyad-years':>10}  coverage window")
    for bank in CANONICAL_BANKS:
        count = sum(1 for row in rows_out if row["bank"] == bank)
        coverage = next((r for r in coverage_rows if r["bank"] == bank), None)
        window = (
            f"{coverage['coverage_start_year'] or '...'}-{coverage['coverage_end_year'] or '...'}"
            if coverage else "full 2002-2026"
        )
        print(f"{bank:6} {count:10}  {window}")
    print(
        f"\n{len(rows_out)} dyad-years across {len(CANONICAL_BANKS)} banks -> "
        f"{COMMITMENTS_CSV.relative_to(REPO)}"
    )
    print(f"{len(unallocated_out)} unallocated bank-years -> {unallocated_path.relative_to(REPO)}")
    if skipped_banks:
        print(f"note: dyad file also carries {sorted(skipped_banks)}, not in this repo's bank list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
