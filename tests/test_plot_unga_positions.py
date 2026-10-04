"""Offline tests for scripts/plot_unga_positions.py -- the percentile-band/
median and per-bank-trajectory data behind the recreated "MDB positions
within the UNGA country distribution" chart. The chart itself (a PNG) isn't
pixel-tested; these cover the numbers that go into it.
"""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

IDEAL_POINTS_FIELDS = ["iso3", "year", "idealpoint_all", "idealpoint_fp"]
REFERENCE_FIELDS = [
    "bank", "year", "largest_shareholder_iso3", "largest_shareholder_weight_pct",
    "largest_shareholder_weight_basis", "hegemonic_ip_all", "hegemonic_ip_fp",
    "g7_ip_all", "g7_n_shareholders_all", "g7_ip_fp", "g7_n_shareholders_fp",
    "g10_ip_all", "g10_n_shareholders_all", "g10_ip_fp", "g10_n_shareholders_fp",
    "ls_ip_all", "ls_n_shareholders_all", "ls_ip_fp", "ls_n_shareholders_fp",
    "coalition_ip_all", "coalition_n_shareholders_all", "coalition_ip_fp", "coalition_n_shareholders_fp",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "plot_unga_positions.py"), *args],
        capture_output=True, text=True, cwd=REPO,
    )


class BankColorsTests(unittest.TestCase):
    """scripts/plot_unga_positions.py's BANK_COLORS -- a hand-picked, logo-
    derived palette (2026-09-28, replacing the original tab20 default the
    user found hard to read). Covers the constraints the user gave
    explicitly, not the exact hex values (which may be retuned later)."""

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        import plot_unga_positions as plot
        self.plot = plot

    @staticmethod
    def _hue(hexcode: str) -> float:
        import colorsys
        h = hexcode.lstrip("#")
        r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
        return colorsys.rgb_to_hsv(r, g, b)[0] * 360

    def test_every_canonical_bank_has_a_color_and_none_collide(self):
        from _panel import CANONICAL_BANKS
        for bank in CANONICAL_BANKS:
            self.assertIn(bank, self.plot.BANK_COLORS)
        colors = list(self.plot.BANK_COLORS.values())
        self.assertEqual(len(colors), len(set(colors)), "two banks share the exact same color")

    def test_aiib_is_red(self):
        hue = self._hue(self.plot.BANK_COLORS["AIIB"])
        self.assertTrue(hue < 15 or hue > 345, f"AIIB's hue is {hue:.0f}, not red")

    def test_ibrd_and_idb_are_a_similar_but_distinct_blue_pair(self):
        ibrd_hue = self._hue(self.plot.BANK_COLORS["IBRD"])
        idb_hue = self._hue(self.plot.BANK_COLORS["IDB"])
        self.assertLess(abs(ibrd_hue - idb_hue), 25)  # same family
        self.assertNotEqual(self.plot.BANK_COLORS["IBRD"], self.plot.BANK_COLORS["IDB"])  # not identical
        for hue in (ibrd_hue, idb_hue):
            self.assertTrue(190 < hue < 250, f"expected a blue hue, got {hue:.0f}")

    def test_badea_and_isdb_are_a_similar_but_distinct_green_pair(self):
        badea_hue = self._hue(self.plot.BANK_COLORS["BADEA"])
        isdb_hue = self._hue(self.plot.BANK_COLORS["IsDB"])
        self.assertLess(abs(badea_hue - isdb_hue), 25)
        self.assertNotEqual(self.plot.BANK_COLORS["BADEA"], self.plot.BANK_COLORS["IsDB"])
        for hue in (badea_hue, isdb_hue):
            self.assertTrue(100 < hue < 170, f"expected a green hue, got {hue:.0f}")


class BuildBandDataTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        import plot_unga_positions as plot
        self.plot = plot

    def test_pre_2002_years_are_excluded_from_the_bands(self):
        import pandas as pd
        df = pd.DataFrame([
            {"iso3": "AAA", "year": 2001, "idealpoint_fp": 9.0},
            {"iso3": "AAA", "year": 2002, "idealpoint_fp": -1.0},
            {"iso3": "BBB", "year": 2002, "idealpoint_fp": 1.0},
        ])
        bands = self.plot.build_band_data(df)
        self.assertEqual(sorted(bands["year"]), [2002])
        self.assertAlmostEqual(bands.iloc[0]["p50"], 0.0)

    def test_percentiles_computed_across_every_country_that_year(self):
        import pandas as pd
        rows = [{"iso3": f"C{i}", "year": 2010, "idealpoint_fp": float(i)} for i in range(1, 11)]
        bands = self.plot.build_band_data(pd.DataFrame(rows))
        row = bands.iloc[0]
        self.assertAlmostEqual(row["p10"], 1.9, places=2)
        self.assertAlmostEqual(row["p50"], 5.5, places=2)
        self.assertAlmostEqual(row["p90"], 9.1, places=2)


class MainScriptTests(unittest.TestCase):
    def test_writes_a_non_empty_png_and_a_data_csv_with_expected_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            ideal_points = write_csv(path / "ideal_points.csv", IDEAL_POINTS_FIELDS, [
                {"iso3": "USA", "year": "2010", "idealpoint_all": "1.0", "idealpoint_fp": "1.0"},
                {"iso3": "KEN", "year": "2010", "idealpoint_all": "-0.5", "idealpoint_fp": "-0.5"},
                {"iso3": "USA", "year": "2011", "idealpoint_all": "0.9", "idealpoint_fp": "0.9"},
                {"iso3": "KEN", "year": "2011", "idealpoint_all": "-0.4", "idealpoint_fp": "-0.4"},
            ])

            def ref_row(bank, year, coalition_fp):
                return {"bank": bank, "year": year, "largest_shareholder_iso3": "USA",
                         "largest_shareholder_weight_pct": "20", "largest_shareholder_weight_basis": "voting",
                         "hegemonic_ip_all": "", "hegemonic_ip_fp": "",
                         "g7_ip_all": "", "g7_n_shareholders_all": "", "g7_ip_fp": "", "g7_n_shareholders_fp": "",
                         "g10_ip_all": "", "g10_n_shareholders_all": "", "g10_ip_fp": "", "g10_n_shareholders_fp": "",
                         "ls_ip_all": "", "ls_n_shareholders_all": "", "ls_ip_fp": "", "ls_n_shareholders_fp": "",
                         "coalition_ip_all": coalition_fp, "coalition_n_shareholders_all": "2",
                         "coalition_ip_fp": coalition_fp, "coalition_n_shareholders_fp": "2"}

            reference = write_csv(path / "reference.csv", REFERENCE_FIELDS, [
                ref_row("IBRD", "2010", "0.3"), ref_row("IBRD", "2011", "0.25"),
                ref_row("NDB", "2011", "0.1"),  # NDB has no 2010 row -- founded later
            ])
            png = path / "chart.png"
            data_csv = path / "chart_data.csv"
            result = run("--ideal-points", str(ideal_points), "--reference", str(reference),
                         "--measure", "fp", "--png", str(png), "--data-csv", str(data_csv))
            self.assertEqual(result.returncode, 0, result.stderr)

            self.assertTrue(png.is_file())
            self.assertGreater(png.stat().st_size, 0)
            self.assertEqual(png.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

            rows = {r["year"]: r for r in read_rows(data_csv)}
            self.assertEqual(rows["2010"]["IBRD"], "0.3")
            self.assertEqual(rows["2010"]["NDB"], "")  # not founded yet -- blank, not zero
            self.assertEqual(rows["2011"]["NDB"], "0.1")
            self.assertEqual(rows["2010"]["p50"], "0.25")  # median of 1.0 and -0.5

    def test_png_or_data_csv_without_measure_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            result = run("--ideal-points", str(path / "missing.csv"), "--png", str(path / "chart.png"))
            self.assertEqual(result.returncode, 2)
            self.assertIn("--measure", result.stderr)

    def test_no_measure_given_writes_both_charts_to_their_own_default_paths(self):
        # Direct import (not subprocess) so MEASURES' default output paths
        # can be pointed at the temp dir instead of the real ../Final
        # dataset/output/ -- confirms the "no --measure -> build both,
        # never overwriting each other" behaviour end to end.
        sys.path.insert(0, str(SCRIPTS))
        import importlib
        import plot_unga_positions as plot
        importlib.reload(plot)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            ideal_points = write_csv(path / "ideal_points.csv", IDEAL_POINTS_FIELDS, [
                {"iso3": "USA", "year": "2010", "idealpoint_all": "1.0", "idealpoint_fp": "1.0"},
                {"iso3": "KEN", "year": "2010", "idealpoint_all": "-0.5", "idealpoint_fp": "-0.5"},
            ])
            reference = write_csv(path / "reference.csv", REFERENCE_FIELDS, [])

            original = {m: dict(spec) for m, spec in plot.MEASURES.items()}
            try:
                for measure, spec in plot.MEASURES.items():
                    spec["png"] = path / f"{measure}.png"
                    spec["data_csv"] = path / f"{measure}_data.csv"
                result = plot.main(["--ideal-points", str(ideal_points), "--reference", str(reference)])
                self.assertEqual(result, 0)
                for measure in ("fp", "all"):
                    self.assertTrue((path / f"{measure}.png").is_file())
                    self.assertTrue((path / f"{measure}_data.csv").is_file())
                # The two measures' outputs are genuinely separate files.
                self.assertNotEqual((path / "fp.png").read_bytes(), (path / "all.png").read_bytes())
            finally:
                plot.MEASURES.clear()
                plot.MEASURES.update(original)


if __name__ == "__main__":
    unittest.main()
