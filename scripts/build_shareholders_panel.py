"""Build data/extracted/shareholders_panel.csv: capital share and voting power,
kept as separate values, per (bank, iso3, year).

Two sources, combined:

- **The current cross-section** in `data/manual/shares_snapshot_2026-08-25.xlsx`
  (all 14 banks, one or two recent years each -- see `shares_snapshot_source.json`
  for what document each figure came from). This is real, sourced, non-hand-typed
  data: it was extracted once from primary documents by whoever built the
  workbook, not guessed, and this script only re-projects it into this repo's
  schema.
- **Wayback-derived historical series**, for the three banks whose real source
  is a live rendered page rather than an annual-report document (`ebrd`, `isdb`,
  `aiib` -- see `docs/architecture.md`'s Wayback plan): `data/extracted/
  wayback_shares_<bank>.csv`, if present. Read directly if `scripts/
  shares_wayback_<bank>.py` has already been run; this script doesn't fetch
  anything itself.

The other 11 banks' full 2002-2026 series needs the annual-report PDF pipeline
(architecture.md session 6) -- not attempted here. Every bank still gets at
least the current-snapshot floor.

A row for a year with no available source is simply absent -- never
interpolated, never zero-filled. Rows this script can't place on a single ISO-3
country (composite members, institutional seats) go to
`data/output/reports/shareholders_panel_unresolved.csv`, not silently dropped.

Usage:  python3 scripts/build_shareholders_panel.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from _panel import BANKS, CANONICAL_BANKS, EXTRACTED_DIR, REPORTS_DIR, REPO, write_csv
from _reference import iso3_from_name

WORKBOOK = Path(__file__).resolve().parents[1] / "data" / "manual" / "shares_snapshot_2026-08-25.xlsx"
SOURCE_MAP_JSON = Path(__file__).resolve().parents[1] / "data" / "manual" / "shares_snapshot_source.json"
TARGET = EXTRACTED_DIR / "shareholders_panel.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shareholders_panel_unresolved.csv"

FIELDS = [
    "bank", "iso3", "year", "capital_share_pct", "voting_power_pct",
    "measure_basis", "as_of_date", "source_url", "source_type", "note",
]

# Workbook institution id -> this repo's canonical bank code.
WORKBOOK_ID_TO_BANK = {bank_id: bank for bank, bank_id in BANKS.items()}

# Country_Shares' own "Member type" values that don't map to a single ISO-3
# country -- kept out of the panel, listed in the unresolved report instead of
# silently dropped or force-mapped.
NON_COUNTRY_MEMBER_TYPES = {"Composite member", "Institution", "Economy", "Private financial institutions"}


def _load_wayback_rows() -> list[dict]:
    rows = []
    for bank_id in ("ebrd", "isdb", "aiib"):
        path = EXTRACTED_DIR / f"wayback_shares_{bank_id}.csv"
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def _load_annual_report_rows() -> list[dict]:
    """data/extracted/shares_<bank>.csv, from scripts/annual_reports_<bank>.py
    parsers (financial-statement/annual-report PDFs) -- the shares-backward-
    extension plan's own historical-series source, distinct from the Wayback
    rows above (which come from rendered current-snapshot pages, not PDFs)."""

    rows = []
    for path in sorted(EXTRACTED_DIR.glob("shares_*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def _country_shares_rows(source_map: dict) -> tuple[list[dict], list[dict]]:
    from openpyxl import load_workbook

    wb = load_workbook(WORKBOOK, read_only=True, data_only=True)
    ws = wb["Country_Shares"]
    raw = [r for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)]
    header_idx = next(i for i, r in enumerate(raw) if r[0] == "ID")
    header = raw[header_idx]

    panel: list[dict] = []
    unresolved: list[dict] = []
    for values in raw[header_idx + 1 :]:
        row = dict(zip(header, values))
        bank_id = row["ID"]
        bank = WORKBOOK_ID_TO_BANK.get(bank_id)
        if bank is None:
            continue  # not one of this repo's 14 banks
        member_type = row.get("Member type") or "Country"
        member_name = str(row.get("Member") or "").strip()
        as_of = row.get("As-of date")
        year = row.get("Year") or (as_of.year if hasattr(as_of, "year") else None)
        capital = row.get("Capital share %")
        voting = row.get("Voting power %")
        basis = source_map.get(bank_id, {}).get("preferred_measure", "")
        note = str(row.get("Note") or "")
        source_url = row.get("Source URL") or ""

        if member_type in NON_COUNTRY_MEMBER_TYPES:
            unresolved.append({
                "bank": bank, "member": member_name, "member_type": member_type,
                "reason": "not a single ISO-3 country", "note": note,
            })
            continue

        iso3 = iso3_from_name(member_name)
        if not iso3:
            unresolved.append({
                "bank": bank, "member": member_name, "member_type": member_type,
                "reason": "country name did not resolve to an ISO-3 code", "note": note,
            })
            continue

        panel.append({
            "bank": bank,
            "iso3": iso3,
            "year": year,
            "capital_share_pct": _pct(capital),
            "voting_power_pct": _pct(voting),
            "measure_basis": basis,
            "as_of_date": as_of.date().isoformat() if hasattr(as_of, "date") else str(as_of or ""),
            "source_url": source_url,
            "source_type": "current_snapshot",
            "note": note,
        })
    return panel, unresolved


def _worldbank_sheet_rows(sheet_name: str, bank: str, source_map: dict) -> tuple[list[dict], list[dict]]:
    from openpyxl import load_workbook

    wb = load_workbook(WORKBOOK, read_only=True, data_only=True)
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    idx = {name.strip(): i for i, name in enumerate(header)}
    bank_id = "ibrd" if bank == "IBRD" else "ida"
    basis = source_map.get(bank_id, {}).get("preferred_measure", "")

    panel: list[dict] = []
    unresolved: list[dict] = []
    for row in rows[1:]:
        if not row or row[idx["Country"]] is None:
            continue
        name = str(row[idx["Country"]]).strip()
        date_text = str(row[idx["Date"]]).strip()
        iso3 = iso3_from_name(name)
        if not iso3:
            unresolved.append({
                "bank": bank, "member": name, "member_type": "Country",
                "reason": "country name did not resolve to an ISO-3 code", "note": "",
            })
            continue
        capital_pct = row[idx["Capital Share"]]
        vote_pct = row[idx["Vote Share"]]
        # Dates come as either "MM-DD-YYYY" or "MM/DD/YYYY" in this sheet.
        year = None
        for sep in ("-", "/"):
            if sep in date_text:
                parts = date_text.split(sep)
                if len(parts) == 3 and len(parts[2]) == 4:
                    year = int(parts[2])
                break
        panel.append({
            "bank": bank,
            "iso3": iso3,
            "year": year,
            "capital_share_pct": _round(capital_pct),
            "voting_power_pct": _round(vote_pct),
            "measure_basis": basis,
            "as_of_date": _reformat_date(date_text),
            "source_url": source_map.get(bank_id, {}).get("official_source", ""),
            "source_type": "current_snapshot",
            "note": "",
        })
    return panel, unresolved


def _pct(fraction) -> str:
    """Country_Shares stores fractions (0.00034); this file uses percentage points."""
    if fraction is None:
        return ""
    return _round(float(fraction) * 100)


def _round(value) -> str:
    if value is None:
        return ""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _reformat_date(text: str) -> str:
    for sep in ("-", "/"):
        if sep in text:
            parts = text.split(sep)
            if len(parts) == 3 and len(parts[2]) == 4:
                mm, dd, yyyy = parts
                return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
    return text


# Preference order when more than one source has a row for the same
# (bank, iso3, year) -- higher is preferred. Real duplication confirmed this
# session: the workbook's own current-snapshot rows and a freshly-built
# scripts/annual_reports_<bank>.py extraction can both cover the same year
# (e.g. BADEA 2024, already in the workbook, also newly extracted here).
# Prefer the more independently-auditable, freshly-verified sources.
_SOURCE_TYPE_PRIORITY = {"annual_report": 3, "wayback_snapshot": 2, "current_snapshot": 1}


def _dedupe_panel(panel: list[dict]) -> tuple[list[dict], list[dict]]:
    best: dict[tuple[str, str, int | str], dict] = {}
    conflicts: list[dict] = []
    for row in panel:
        key = (row["bank"], row["iso3"], row["year"])
        existing = best.get(key)
        if existing is None:
            best[key] = row
            continue
        existing_priority = _SOURCE_TYPE_PRIORITY.get(existing.get("source_type", ""), 0)
        row_priority = _SOURCE_TYPE_PRIORITY.get(row.get("source_type", ""), 0)
        winner, loser = (row, existing) if row_priority > existing_priority else (existing, row)
        # A blank on either side isn't a disagreement (a voting-only source next
        # to one that has both); only two real capital figures that differ are.
        if (existing["capital_share_pct"] not in ("", None) and row["capital_share_pct"] not in ("", None)
                and existing["capital_share_pct"] != row["capital_share_pct"]):
            conflicts.append({
                "bank": row["bank"], "iso3": row["iso3"], "year": row["year"],
                "kept_source_type": winner.get("source_type", ""),
                "kept_capital_share_pct": winner["capital_share_pct"],
                "dropped_source_type": loser.get("source_type", ""),
                "dropped_capital_share_pct": loser["capital_share_pct"],
            })
        best[key] = winner
    return list(best.values()), conflicts


def main() -> int:
    if not WORKBOOK.is_file():
        print(f"error: {WORKBOOK} does not exist.")
        return 2
    source_map = {entry["bank_id"]: entry for entry in json.loads(SOURCE_MAP_JSON.read_text())["banks"]}

    panel: list[dict] = []
    unresolved: list[dict] = []

    country_shares_panel, country_shares_unresolved = _country_shares_rows(source_map)
    panel += country_shares_panel
    unresolved += country_shares_unresolved

    # The workbook's "IDA" sheet is deliberately NOT read: found 2026-09-24 to be
    # IBRD's numbers under an IDA label -- all 189 of its rows equal IBRD's own
    # FY2026 capital and vote shares to two decimals (it has IBRD's 189 members,
    # not IDA's 174; the US shows 16.89% / 15.98% where IDA's own audited
    # statement says 9.52% of votes). IDA now comes from its own financial
    # statements (annual_reports_ida.py). See docs/coding_decisions.md.
    for sheet, bank in (("IBRD", "IBRD"),):
        wb_panel, wb_unresolved = _worldbank_sheet_rows(sheet, bank, source_map)
        panel += wb_panel
        unresolved += wb_unresolved

    wayback_rows = _load_wayback_rows()
    for row in wayback_rows:
        row.setdefault("source_type", "wayback_snapshot")
        if row["year"]:
            row["year"] = int(row["year"])  # csv.DictReader always returns strings
    panel += wayback_rows

    annual_report_rows = _load_annual_report_rows()
    for row in annual_report_rows:
        row.setdefault("source_type", "annual_report")
        if row["year"]:
            row["year"] = int(row["year"])
    panel += annual_report_rows

    panel, conflicts = _dedupe_panel(panel)

    bank_order = {bank: index for index, bank in enumerate(CANONICAL_BANKS)}
    panel.sort(key=lambda row: (bank_order.get(row["bank"], 99), row["iso3"], str(row["year"])))

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(TARGET, FIELDS, panel)

    if conflicts:
        write_csv(REPORTS_DIR / "shareholders_panel_conflicts.csv",
                   ["bank", "iso3", "year", "kept_source_type", "kept_capital_share_pct",
                    "dropped_source_type", "dropped_capital_share_pct"], conflicts)
        print(f"{len(conflicts)} (bank, iso3, year) rows had disagreeing sources -> "
              f"{(REPORTS_DIR / 'shareholders_panel_conflicts.csv').relative_to(REPO)}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(
        UNRESOLVED_REPORT,
        ["bank", "member", "member_type", "reason", "note"],
        unresolved,
    )

    banks_present = {row["bank"] for row in panel}
    print(f"{len(panel)} panel rows across {len(banks_present)} of {len(BANKS)} banks")
    missing = set(BANKS) - banks_present
    if missing:
        print(f"WARNING: no panel row at all for: {sorted(missing)}")
    print(f"{len(unresolved)} rows could not be placed -> "
          f"{UNRESOLVED_REPORT.relative_to(REPO)}")
    for bank in BANKS:
        years = sorted({row["year"] for row in panel if row["bank"] == bank and row["year"]})
        wayback_years = sorted({row["year"] for row in panel
                                 if row["bank"] == bank and row.get("source_type") == "wayback_snapshot"})
        tag = " (+ wayback)" if wayback_years else ""
        print(f"  {bank:6} years: {years or 'NONE'}{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
