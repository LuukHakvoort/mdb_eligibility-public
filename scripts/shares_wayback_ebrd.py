"""Reconstruct EBRD's shareholder history from Wayback snapshots of its own
shareholders page.

EBRD is the strongest Wayback case of the three checked (see docs/architecture.md's
Wayback plan): `ebrd.com/shareholders-and-board-of-governors.html` has 12 real
captures spanning 2014-2025 (confirmed live), each with a genuine server-rendered
table -- "Member country", "Date joined", "Capital subscription (EUR 000)",
"Governor", "Alternate". "Date joined" is a real accession date straight from
EBRD's own page, not something this script infers.

Two shareholders are not countries -- the European Union and the EIB -- and stay
in the capital-share denominator (EBRD's own page includes them) while being
excluded from the per-country panel, reported to the unresolved file instead of
guessed at.

Writes:
- data/extracted/wayback_shares_ebrd.csv       (bank/iso3/year capital share)
- data/extracted/wayback_accessions_ebrd.csv   (bank/iso3/accession_date, real
  dates read straight off the page -- feeds Component B directly, no hand entry)

Usage:  python3 scripts/shares_wayback_ebrd.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mdbs_scraper_corrected"))
from mdbs_scraper.parsers import parse_tables  # noqa: E402

import wayback  # noqa: E402
from _panel import EXTRACTED_DIR, MAX_YEAR, MIN_YEAR, REPO, REPORTS_DIR, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402

URL = "ebrd.com/shareholders-and-board-of-governors.html"
BANK = "EBRD"
NON_COUNTRY_SHAREHOLDERS = {"european union", "european investment bank"}
# The page's own name for North Macedonia, in a word order the shared
# resolver's alias table doesn't have (it does resolve "Macedonia, FYR").
# A narrow, page-specific spelling fix, not a change to the shared resolver.
NAME_FIXUPS = {"fyr macedonia": "North Macedonia"}

PANEL_FIELDS = [
    "bank", "iso3", "year", "capital_share_pct", "voting_power_pct",
    "measure_basis", "as_of_date", "source_url", "source_type", "note",
]
ACCESSION_FIELDS = ["bank", "iso3", "country_name", "accession_date", "source", "note"]


def _shareholder_table(html: str) -> list[list[str]] | None:
    for table in parse_tables(html):
        if table and table[0][:2] == ["Member country", "Date joined"]:
            return table
    return None


def _parse_date_joined(text: str) -> str:
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def _parse_subscription(text: str) -> float | None:
    cleaned = text.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def main() -> int:
    snapshots = wayback.cdx_snapshots(URL)
    if not snapshots:
        print("error: no Wayback snapshots found for the EBRD shareholders page "
              "(CDX API may be unavailable right now -- see wayback.py's retry log above)")
        return 2
    available_years = sorted({s.year for s in snapshots})
    print(f"EBRD: {len(snapshots)} snapshots available, years {available_years}")

    panel_rows: list[dict] = []
    accession_rows: dict[tuple[str, str], dict] = {}  # first sighting wins -- earliest real date
    unresolved: list[dict] = []
    fetched_timestamps: set[str] = set()

    for year in range(MIN_YEAR, MAX_YEAR + 1):
        snap = wayback.nearest_snapshot(URL, year, snapshots)
        if snap is None or abs(snap.year - year) > 1:
            continue  # no snapshot close enough to this year to be meaningful
        if snap.timestamp in fetched_timestamps:
            continue  # already processed this exact capture for an adjacent year
        fetched_timestamps.add(snap.timestamp)
        html = wayback.fetch_snapshot(snap)
        if html is None:
            print(f"  {snap.year}: fetch failed, skipping (see retry log above)")
            continue
        table = _shareholder_table(html)
        if table is None:
            print(f"  {snap.year}: page fetched but shareholders table not found (layout may differ)")
            continue

        # A "Chair/Vice Chair of the Board of Governors <year>-<year>" footnote
        # sometimes rides along in the same <table> as an extra row -- not a
        # real shareholder, filtered out before it can pollute either the
        # total or the unresolved report.
        rows = [row for row in table[1:] if "board of governors" not in row[0].casefold()]
        subscriptions: list[tuple[str, float]] = []
        for row in rows:
            name = row[0].strip()
            amount = _parse_subscription(row[2]) if len(row) > 2 else None
            if amount is not None:
                subscriptions.append((name, amount))
        total = sum(amount for _, amount in subscriptions)
        if not total:
            continue

        for row in rows:
            name = row[0].strip()
            if not name:
                continue
            amount = _parse_subscription(row[2]) if len(row) > 2 else None
            date_joined = _parse_date_joined(row[1]) if len(row) > 1 else ""

            if name.casefold() in NON_COUNTRY_SHAREHOLDERS:
                unresolved.append({
                    "bank": BANK, "member": name, "member_type": "Institution",
                    "reason": "not a single ISO-3 country", "note": "EBRD's own page lists it "
                    "as a shareholder alongside member countries.",
                })
                continue
            lookup_name = NAME_FIXUPS.get(name.casefold(), name)
            iso3 = iso3_from_name(lookup_name)
            if not iso3:
                unresolved.append({
                    "bank": BANK, "member": name, "member_type": "Country",
                    "reason": "country name did not resolve to an ISO-3 code",
                    "note": f"Seen in the {snap.year} snapshot.",
                })
                continue

            if amount is not None:
                panel_rows.append({
                    "bank": BANK,
                    "iso3": iso3,
                    "year": snap.year,
                    "capital_share_pct": f"{amount / total * 100:.6f}".rstrip("0").rstrip("."),
                    "voting_power_pct": "",
                    "measure_basis": "Capital-subscription share",
                    "as_of_date": f"{snap.timestamp[:4]}-{snap.timestamp[4:6]}-{snap.timestamp[6:8]}",
                    "source_url": snap.archive_url,
                    "source_type": "wayback_snapshot",
                    "note": "",
                })

            if date_joined:
                key = (BANK, iso3)
                existing = accession_rows.get(key)
                if existing is None or date_joined < existing["accession_date"]:
                    accession_rows[key] = {
                        "bank": BANK, "iso3": iso3, "country_name": name,
                        "accession_date": date_joined, "source": snap.archive_url,
                        "note": "Read directly from EBRD's own \"Date joined\" column.",
                    }
        print(f"  {snap.year} (snapshot {snap.timestamp[:8]}): {len(subscriptions)} shareholders, "
              f"total {total:,.0f}")

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(EXTRACTED_DIR / "wayback_shares_ebrd.csv", PANEL_FIELDS, panel_rows)
    write_csv(EXTRACTED_DIR / "wayback_accessions_ebrd.csv", ACCESSION_FIELDS,
              sorted(accession_rows.values(), key=lambda r: r["iso3"]))
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(REPORTS_DIR / "wayback_ebrd_unresolved.csv",
              ["bank", "member", "member_type", "reason", "note"], unresolved)

    print(f"\n{len(panel_rows)} panel rows, {len(accession_rows)} distinct accession dates, "
          f"{len(unresolved)} unresolved rows")
    print(f"-> {(EXTRACTED_DIR / 'wayback_shares_ebrd.csv').relative_to(REPO)}")
    print(f"-> {(EXTRACTED_DIR / 'wayback_accessions_ebrd.csv').relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
