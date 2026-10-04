"""Parse CABEI's "Estructura de Capital" table (Capital Structure) out of
CABEI's own investor presentation.

A real, richer, three-block table (Países Fundadores / Founders / Serie A;
Países Regionales No Fundadores / Non-Founding Regional / Serie B;
Países Extrarregionales / Extra-regional / Serie B), confirmed by inspection.
Two distinct trailing percentage columns per row: "% del Capital Autorizado"
(share of *authorized* capital, including CABEI's own unsubscribed shares --
sums to 98.90% among members, 1.10% unsubscribed) and "% Participación
Accionaria" (share of *subscribed* capital -- sums to exactly 100.00% among
members). `capital_share_pct` here is the second one (subscribed-capital
share, the standard concept the other banks' parsers also compute).
**`voting_power_pct` is left blank on purpose**, not mapped to either
column: the table's own footnote ties actual voting rights to a vesting
condition ("El derecho a votar... entrará en vigor una vez que se haya
recibido el primer pago de capital..."), so neither percentage column is
cleanly "voting power" without further verification this pass doesn't do.

Real name-extraction quirk found live: some country names in this specific
document render with **no space** between words ("RepúblicaDominicana",
"PaísesFundadores" as a section label) -- a PDF text-extraction artifact,
not a typo in the source. Fixups are narrow and confirmed against the real
document, not guessed.

Usage:  python3 scripts/annual_reports_cabei.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, MANUAL_DIR, REPO, REPORTS_DIR, read_csv, write_csv  # noqa: E402
from _reference import iso3_from_name  # noqa: E402
from annual_reports import fetch  # noqa: E402

ANNUAL_REPORTS_CSV = MANUAL_DIR / "annual_reports.csv"
TARGET = EXTRACTED_DIR / "shares_cabei.csv"
UNRESOLVED_REPORT = REPORTS_DIR / "shares_cabei_unresolved.csv"

FIELDS = ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]

_TABLE_TITLE = "estructura de capital a"
_ROW = re.compile(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'()-]*?)\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+([\d.]+)%\s+([\d.]+)%$")
_SKIP_SUBSTRINGS = (
    "Acciones", "Capital Suscrito", "Países", "Total Fundadores", "Sub-total", "(*)",
    "Estructura de Capital", "suscrito por países", "AccionesNo Suscritas", "Total Autorizado",
)

# Real text-extraction glomming and long-form names found in this specific document.
_NAME_FIXUPS = {
    "RepúblicaDominicana": "República Dominicana",
    "República de China (Taiwán)": "Taiwan, China",
    "República de Corea": "Korea, Rep.",
    "España": "Spain",
    "México": "Mexico",
    "Panamá": "Panama",
    "Belice": "Belize",
}


def _resolve(name: str) -> str:
    return iso3_from_name(_NAME_FIXUPS.get(name, name))


def parse_pdf(path: Path, year: int, source_url: str) -> tuple[list[dict], list[dict]]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        page_index = next(
            (i for i, page in enumerate(pdf.pages) if _TABLE_TITLE in (page.extract_text() or "").lower()),
            None,
        )
        if page_index is None:
            raise SystemExit(f"error: could not find \"{_TABLE_TITLE}\" in {path}")
        text = pdf.pages[page_index].extract_text() or ""

    raw_rows: list[tuple[str, float]] = []
    total: float | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if any(s in stripped for s in _SKIP_SUBSTRINGS):
            continue
        match = _ROW.match(stripped)
        if not match:
            continue
        name, _pct_authorized, pct_subscribed = match.groups()
        pct = float(pct_subscribed)
        if name.strip() == "Total Suscrito":
            total = pct
        else:
            raw_rows.append((name.strip(), pct))

    if total is None:
        raise SystemExit(f"error: no 'Total Suscrito' row found on page {page_index} of {path}")
    if abs(total - 100.0) > 0.5:
        raise SystemExit(f"error: 'Total Suscrito' is {total}%, not ~100% -- table shape assumption is wrong")

    rows: list[dict] = []
    unresolved: list[dict] = []
    for name, pct in raw_rows:
        iso3 = _resolve(name)
        if not iso3:
            unresolved.append({"year": year, "name_raw": name})
            continue
        rows.append({
            "bank": "CABEI", "iso3": iso3, "year": year,
            "capital_share_pct": pct,
            "voting_power_pct": "",
            "source_url": source_url,
            "note": "Table's own 'accionaria' percentage is conditional on a capital-payment "
                    "vesting footnote -- not mapped to voting_power_pct without further verification.",
        })
    return rows, unresolved


def main() -> int:
    if not ANNUAL_REPORTS_CSV.is_file():
        print(f"error: {ANNUAL_REPORTS_CSV} does not exist.", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    all_unresolved: list[dict] = []
    for row in read_csv(ANNUAL_REPORTS_CSV):
        if row.get("bank") != "CABEI" or row.get("document"):  # document set = read by annual_reports_cabei_ar.py
            continue
        year = int(row["year"])
        url = row["url"]
        path = fetch(url, f"cabei_investor_{year}.pdf")
        rows, unresolved = parse_pdf(path, year, url)
        all_rows += rows
        all_unresolved += unresolved
        total_capital = sum(r["capital_share_pct"] for r in rows)
        print(f"{year}: {len(rows)} rows, capital shares sum to {total_capital:.2f}% "
              f"({'OK' if 95 <= total_capital <= 105 else 'CHECK THIS'})")

    all_rows.sort(key=lambda r: (r["iso3"], r["year"]))
    write_csv(TARGET, FIELDS, all_rows)
    write_csv(UNRESOLVED_REPORT, ["year", "name_raw"], all_unresolved)
    print(f"\n{len(all_rows)} rows -> {TARGET.relative_to(REPO)}")
    print(f"{len(all_unresolved)} unresolved names -> {UNRESOLVED_REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
