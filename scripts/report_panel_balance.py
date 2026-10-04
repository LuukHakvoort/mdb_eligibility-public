"""Panel balance: eligible dyad-years per bank per year.

Every discontinuity in these counts should correspond to a documented accession
or mandate change. An unexplained jump is a coding error -- a spell with the
wrong start year, or a country coded for the wrong bank.

Writes a CSV (the table view) and a self-contained SVG of small multiples, one
panel per bank. No plotting library: the repo stays dependency-free, and an SVG
opens in any browser or editor.

Scales are per bank, and each panel is labelled with its own maximum. That is
deliberate: the question here is "does this bank's own series jump?", not "is
this bank bigger than that one". Panels are therefore not comparable by height.

A year outside the bank's own data-coverage window (data/extracted/
bank_coverage.csv -- CDB 2013-2023, BADEA -2022, AIIB/NDB 2016-, CAF 2006-) is
shaded, not blank, in both the chart and the CSV's `in_coverage` column: the
series stopping at CDB 2023 should read as "the source stops here," not "a
coding error to go hunt for."

Usage:  python3 scripts/report_panel_balance.py [--eligibility PATH]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _panel import (
    BANK_COVERAGE_CSV, BANKS, ELIGIBILITY_CSV, MAX_YEAR, MIN_YEAR, REPORTS_DIR, REPO, YEARS,
    in_coverage, load_bank_coverage, load_eligibility, write_csv,
)

FIELDS = ["bank", "year", "eligible_dyad_years", "in_coverage"]

# Validated against the reference palette's surfaces in both modes
# (scripts/validate_palette.js: lightness band, chroma floor, contrast >= 3:1).
LIGHT = {
    "surface": "#fcfcfb", "ink": "#0b0b0b", "muted": "#898781",
    "grid": "#e1e0d9", "axis": "#c3c2b7", "series": "#2a78d6",
}
DARK = {
    "surface": "#1a1a19", "ink": "#ffffff", "muted": "#898781",
    "grid": "#2c2c2a", "axis": "#383835", "series": "#3987e5",
}

PANEL_W, PANEL_H = 200, 96
COL_GAP, ROW_GAP = 22, 52
COLUMNS = 4
MARGIN_X, HEADER_H, CAPTION_H = 24, 64, 48
LABEL_H = 18  # panel title above each plot


def _coverage_label(coverage: dict[str, tuple[int | None, int | None]], bank: str) -> str:
    start, end = coverage.get(bank, (None, None))
    if start is None and end is None:
        return ""
    return f"data {start or MIN_YEAR}–{end or MAX_YEAR}"


def _panel_svg(
    bank: str, counts: dict[int, int], x: float, y: float,
    coverage: dict[str, tuple[int | None, int | None]],
) -> list[str]:
    """One small multiple: a 2px line on a zero baseline, per-panel y scale."""

    peak = max(counts.values()) if counts else 0
    top = peak or 1
    span = MAX_YEAR - MIN_YEAR
    label = _coverage_label(coverage, bank)
    parts = [
        f'<text class="panel-title" x="{x}" y="{y - 6}">{bank}</text>',
        f'<text class="panel-max" x="{x + PANEL_W}" y="{y - 6}">'
        f'{"max " + str(peak) if peak else "no data"}</text>',
        f'<rect class="plot" x="{x}" y="{y}" width="{PANEL_W}" height="{PANEL_H}"/>',
    ]
    if label:
        parts.append(
            f'<text class="coverage-note" x="{x}" y="{y + PANEL_H + 26}">{label}</text>'
        )
    # Out-of-coverage years are shaded (hatched fill defined once in <defs>),
    # not left to look like an ordinary flat zero the same as a real gap.
    for year in YEARS:
        if in_coverage(bank, year, coverage):
            continue
        px = x + PANEL_W * (year - MIN_YEAR) / span
        step = PANEL_W / span
        parts.append(
            f'<rect class="no-coverage" x="{px:.1f}" y="{y}" width="{step:.2f}" height="{PANEL_H}"/>'
        )
    # Recessive gridlines at the quarter marks, baseline drawn separately.
    for fraction in (0.25, 0.5, 0.75):
        gy = y + PANEL_H * fraction
        parts.append(f'<line class="grid" x1="{x}" y1="{gy:.1f}" x2="{x + PANEL_W}" y2="{gy:.1f}"/>')
    parts.append(
        f'<line class="axis" x1="{x}" y1="{y + PANEL_H}" x2="{x + PANEL_W}" y2="{y + PANEL_H}"/>'
    )

    points = []
    for year in YEARS:
        px = x + PANEL_W * (year - MIN_YEAR) / span
        py = y + PANEL_H - PANEL_H * (counts.get(year, 0) / top)
        points.append((px, py, year, counts.get(year, 0)))
    path = " ".join(f"{'M' if index == 0 else 'L'}{px:.1f},{py:.1f}"
                    for index, (px, py, _, _) in enumerate(points))
    parts.append(f'<path class="series" d="{path}"/>')
    # Invisible wide hit targets give a native tooltip per year.
    for px, py, year, value in points:
        parts.append(
            f'<circle class="hit" cx="{px:.1f}" cy="{py:.1f}" r="7">'
            f"<title>{bank} {year}: {value} eligible</title></circle>"
        )
    for year in (MIN_YEAR, MAX_YEAR):
        px = x + PANEL_W * (year - MIN_YEAR) / span
        anchor = "start" if year == MIN_YEAR else "end"
        parts.append(
            f'<text class="tick" x="{px:.1f}" y="{y + PANEL_H + 14}" '
            f'text-anchor="{anchor}">{year}</text>'
        )
    return parts


def build_svg(
    counts_by_bank: dict[str, dict[int, int]], total: int,
    coverage: dict[str, tuple[int | None, int | None]],
) -> str:
    rows = (len(BANKS) + COLUMNS - 1) // COLUMNS
    width = MARGIN_X * 2 + COLUMNS * PANEL_W + (COLUMNS - 1) * COL_GAP
    height = HEADER_H + rows * (PANEL_H + LABEL_H + ROW_GAP) + CAPTION_H

    def theme(mode: dict[str, str]) -> str:
        return "".join(f"--{key}:{value};" for key, value in mode.items())

    body: list[str] = []
    for index, bank in enumerate(BANKS):
        column, row = index % COLUMNS, index // COLUMNS
        x = MARGIN_X + column * (PANEL_W + COL_GAP)
        y = HEADER_H + row * (PANEL_H + LABEL_H + ROW_GAP) + LABEL_H
        body += _panel_svg(bank, counts_by_bank.get(bank, {}), x, y, coverage)

    subtitle = (
        f"{total} eligible dyad-years"
        if total
        else "No eligible dyad-years yet - the panel has not been built"
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif">
  <defs>
    <pattern id="no-coverage-hatch" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
      <rect width="6" height="6" fill="var(--surface)"/>
      <line x1="0" y1="0" x2="0" y2="6" stroke="var(--grid)" stroke-width="2"/>
    </pattern>
  </defs>
  <style>
    svg {{ {theme(LIGHT)} color-scheme: light; }}
    @media (prefers-color-scheme: dark) {{ svg {{ {theme(DARK)} color-scheme: dark; }} }}
    .bg {{ fill: var(--surface); }}
    .title {{ fill: var(--ink); font-size: 15px; font-weight: 600; }}
    .subtitle, .caption {{ fill: var(--muted); font-size: 11px; }}
    .panel-title {{ fill: var(--ink); font-size: 12px; font-weight: 600; }}
    .panel-max, .tick, .coverage-note {{ fill: var(--muted); font-size: 9px; font-variant-numeric: tabular-nums; }}
    .panel-max {{ text-anchor: end; }}
    .plot {{ fill: none; }}
    .no-coverage {{ fill: url(#no-coverage-hatch); }}
    .grid {{ stroke: var(--grid); stroke-width: 1; }}
    .axis {{ stroke: var(--axis); stroke-width: 1; }}
    .series {{ fill: none; stroke: var(--series); stroke-width: 2;
               stroke-linejoin: round; stroke-linecap: round; }}
    .hit {{ fill: transparent; }}
  </style>
  <rect class="bg" x="0" y="0" width="{width}" height="{height}"/>
  <text class="title" x="{MARGIN_X}" y="26">Eligible dyad-years per bank, {MIN_YEAR}-{MAX_YEAR}</text>
  <text class="subtitle" x="{MARGIN_X}" y="44">{subtitle}. Every discontinuity should match a documented accession or mandate change.</text>
  {chr(10).join("  " + part for part in body)}
  <text class="caption" x="{MARGIN_X}" y="{height - 26}">Each panel has its own y scale, labelled with that bank's maximum; panel heights are not comparable across banks. Baseline is zero.</text>
  <text class="caption" x="{MARGIN_X}" y="{height - 12}">Hatched years are outside the source's own data coverage, not a coding gap.</text>
</svg>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--eligibility", type=Path, default=ELIGIBILITY_CSV)
    parser.add_argument("--coverage", type=Path, default=BANK_COVERAGE_CSV)
    parser.add_argument("--report", type=Path, default=REPORTS_DIR / "panel_balance.csv")
    parser.add_argument("--svg", type=Path, default=REPORTS_DIR / "panel_balance.svg")
    args = parser.parse_args(argv)

    eligibility, exists = load_eligibility(args.eligibility)
    coverage = load_bank_coverage(args.coverage)
    if not exists:
        print(f"note: {args.eligibility} does not exist yet; every count is zero.")

    counts_by_bank: dict[str, dict[int, int]] = {bank: {} for bank in BANKS}
    for row in eligibility:
        if row["eligible"] is True and row["bank"] in counts_by_bank:
            year_counts = counts_by_bank[row["bank"]]
            year_counts[row["year"]] = year_counts.get(row["year"], 0) + 1

    rows_out = [
        {
            "bank": bank, "year": year,
            "eligible_dyad_years": counts_by_bank[bank].get(year, 0),
            "in_coverage": int(in_coverage(bank, year, coverage)),
        }
        for bank in BANKS
        for year in YEARS
    ]
    write_csv(args.report, FIELDS, rows_out)

    total = sum(sum(counts.values()) for counts in counts_by_bank.values())
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    args.svg.write_text(build_svg(counts_by_bank, total, coverage), encoding="utf-8")

    print(f"\n{'bank':6} {'eligible dyad-years':>20} {'peak year':>10}")
    for bank in BANKS:
        counts = counts_by_bank[bank]
        peak = max(counts.values()) if counts else 0
        print(f"{bank:6} {sum(counts.values()):20} {peak:10}")
    relative = lambda path: path.relative_to(REPO) if path.is_relative_to(REPO) else path
    print(f"\nWrote {relative(args.report)} and {relative(args.svg)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
