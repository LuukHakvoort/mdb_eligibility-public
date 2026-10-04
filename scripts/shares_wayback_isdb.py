"""Extract IsDB's member list and real accession dates from a Wayback snapshot
of its own `member_countries.json` data endpoint.

Unlike EBRD's shareholders page, this file has no capital/voting share --
it's a pure membership + accession-date list, straight from IsDB's own site
(`id` is already an ISO 3166-1 alpha-2 code; `joined` is a real date, not
inferred). It doesn't change what it says about *past* accessions between
captures, so this reads the single most complete available snapshot rather
than one per year the way EBRD's yearly capital table needs.

The 2005 snapshot of IsDB's old member page (`efs_members.htm`) was also
checked: it lists 26 countries participating in a specific trade-finance
scheme, in unstructured contact-directory text, not a members/shares table.
Not parsed here -- the effort-to-value ratio is poor next to this JSON file,
and it predates this repo's 2002-2026 window's early years by only a little.

Writes: data/extracted/wayback_accessions_isdb.csv

Usage:  python3 scripts/shares_wayback_isdb.py
"""

from __future__ import annotations

import json

from _panel import EXTRACTED_DIR, REPO, REPORTS_DIR, write_csv
from _reference import alpha3_from_alpha2, country_name

import wayback

URL = "https://www.isdb.org/data/defs/member_countries.json"
BANK = "IsDB"

ACCESSION_FIELDS = ["bank", "iso3", "country_name", "accession_date", "source", "note"]


def main() -> int:
    snapshots = wayback.cdx_snapshots(URL)
    if not snapshots:
        print("error: no Wayback snapshots found for IsDB's member_countries.json "
              "(CDX API may be unavailable right now)")
        return 2
    # Most recent capture = most complete member list.
    latest = max(snapshots, key=lambda s: s.timestamp)
    print(f"IsDB: using snapshot {latest.timestamp[:8]} ({len(snapshots)} captures available: "
          f"{sorted({s.year for s in snapshots})})")
    body = wayback.fetch_snapshot(latest)
    if body is None:
        print("error: fetch failed (see retry log above)")
        return 2

    try:
        members = json.loads(body)
    except json.JSONDecodeError as exc:
        print(f"error: response was not valid JSON ({exc}); the endpoint's shape may have changed")
        return 2

    rows: list[dict] = []
    unresolved: list[dict] = []
    for entry in members:
        alpha2 = (entry.get("id") or "").strip()
        iso3 = alpha3_from_alpha2(alpha2)
        name = entry.get("labels", {}).get("en", "").strip() or country_name(iso3)
        joined = (entry.get("joined") or "").strip()
        if not iso3:
            unresolved.append({
                "bank": BANK, "member": name or alpha2, "member_type": "Country",
                "reason": f"alpha-2 code {alpha2!r} did not resolve to an ISO-3 code", "note": "",
            })
            continue
        rows.append({
            "bank": BANK,
            "iso3": iso3,
            "country_name": name,
            "accession_date": joined,
            "source": latest.archive_url,
            "note": "Read directly from IsDB's own member_countries.json (\"joined\" field).",
        })

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(EXTRACTED_DIR / "wayback_accessions_isdb.csv", ACCESSION_FIELDS,
              sorted(rows, key=lambda r: r["iso3"]))
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(REPORTS_DIR / "wayback_isdb_unresolved.csv",
              ["bank", "member", "member_type", "reason", "note"], unresolved)

    print(f"{len(rows)} members with accession dates, {len(unresolved)} unresolved")
    print(f"-> {(EXTRACTED_DIR / 'wayback_accessions_isdb.csv').relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
