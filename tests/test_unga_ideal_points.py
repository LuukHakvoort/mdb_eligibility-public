"""Offline tests for scripts/build_unga_ideal_points.py -- cleaning Erik
Voeten's raw UNGA ideal-point source into data/extracted/unga_ideal_points
.csv. Uses --input pointing at a small CSV fixture (the script accepts
either .dta or .csv by extension) so no real Stata file is needed.
"""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

RAW_FIELDS = ["ccode", "iso3c", "countryname", "year", "idealpointall",
              "idealpointfp", "idealpointlegacy", "nvotesall", "nvotesfp"]
FP_EXTENSION_FIELDS = ["ccode", "session", "NVotesFP", "IdealPointFP", "iso3c", "Countryname", "year"]


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
        [sys.executable, str(SCRIPTS / "build_unga_ideal_points.py"), *args],
        capture_output=True, text=True, cwd=REPO,
    )


class BuildUngaIdealPointsTests(unittest.TestCase):
    def test_drops_blank_iso3c_and_pre_2000_rows_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            raw = write_csv(path / "raw.csv", RAW_FIELDS, [
                {"ccode": "2", "iso3c": "USA", "countryname": "United States", "year": "2015",
                 "idealpointall": "1.5", "idealpointfp": "1.4", "idealpointlegacy": "1.3",
                 "nvotesall": "50", "nvotesfp": "20"},
                {"ccode": "260", "iso3c": "", "countryname": "", "year": "1980",
                 "idealpointall": "0.1", "idealpointfp": "0.1", "idealpointlegacy": "0.1",
                 "nvotesall": "10", "nvotesfp": "5"},
                {"ccode": "255", "iso3c": "DEU", "countryname": "Germany", "year": "1990",
                 "idealpointall": "0.5", "idealpointfp": "0.4", "idealpointlegacy": "0.3",
                 "nvotesall": "30", "nvotesfp": "10"},
            ])
            output = path / "unga_ideal_points.csv"
            # --fp-extension points at a nonexistent path deliberately, so this
            # test stays hermetic (isolated from the real FP CSV on disk) and
            # only exercises the base .dta-cleaning behaviour -- the extension
            # itself is covered by its own tests below.
            result = run("--input", str(raw), "--output", str(output),
                         "--fp-extension", str(path / "does_not_exist.csv"))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = read_rows(output)
            # The blank-iso3c row and the pre-2000 (Germany, 1990) row are both dropped.
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["iso3"], "USA")
            self.assertEqual(rows[0]["idealpoint_all"], "1.5")
            self.assertEqual(rows[0]["idealpoint_fp"], "1.4")

    def test_duplicate_iso3_year_after_cleaning_fails_loudly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            raw = write_csv(path / "raw.csv", RAW_FIELDS, [
                {"ccode": "678", "iso3c": "YAR", "countryname": "Yemen Arab Republic", "year": "2015",
                 "idealpointall": "1.0", "idealpointfp": "1.0", "idealpointlegacy": "1.0",
                 "nvotesall": "10", "nvotesfp": "5"},
                {"ccode": "680", "iso3c": "YAR", "countryname": "Yemen People's Republic", "year": "2015",
                 "idealpointall": "2.0", "idealpointfp": "2.0", "idealpointlegacy": "2.0",
                 "nvotesall": "10", "nvotesfp": "5"},
            ])
            output = path / "unga_ideal_points.csv"
            result = run("--input", str(raw), "--output", str(output),
                         "--fp-extension", str(path / "does_not_exist.csv"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate", result.stderr.lower())


class FpExtensionTests(unittest.TestCase):
    """The 2025 idealpoint_fp extension (the user's explicit choice, after
    being shown the vintage-mismatch trade-off -- docs/coding_decisions.md,
    2026-09-28): idealpoint_fp reaches past the main .dta's own last year,
    idealpoint_all never does."""

    def test_extension_rows_get_idealpoint_fp_but_never_idealpoint_all(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            raw = write_csv(path / "raw.csv", RAW_FIELDS, [
                {"ccode": "2", "iso3c": "USA", "countryname": "United States", "year": "2024",
                 "idealpointall": "1.0", "idealpointfp": "0.9", "idealpointlegacy": "0.8",
                 "nvotesall": "40", "nvotesfp": "18"},
            ])
            fp_extension = write_csv(path / "fp_extension.csv", FP_EXTENSION_FIELDS, [
                {"ccode": "2", "session": "80", "NVotesFP": "19", "IdealPointFP": "1.1",
                 "iso3c": "USA", "Countryname": "United States", "year": "2025"},
                # A year the main .dta already covers must NOT be duplicated in.
                {"ccode": "2", "session": "79", "NVotesFP": "18", "IdealPointFP": "999",
                 "iso3c": "USA", "Countryname": "United States", "year": "2024"},
            ])
            output = path / "unga_ideal_points.csv"
            result = run("--input", str(raw), "--output", str(output), "--fp-extension", str(fp_extension))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {r["year"]: r for r in read_rows(output)}
            self.assertEqual(sorted(rows), ["2024", "2025"])
            self.assertEqual(rows["2024"]["idealpoint_fp"], "0.9")  # untouched -- from the .dta, not the "999" row
            self.assertEqual(rows["2025"]["idealpoint_fp"], "1.1")
            self.assertEqual(rows["2025"]["idealpoint_all"], "")   # never guessed

    def test_missing_fp_extension_file_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            raw = write_csv(path / "raw.csv", RAW_FIELDS, [
                {"ccode": "2", "iso3c": "USA", "countryname": "United States", "year": "2024",
                 "idealpointall": "1.0", "idealpointfp": "0.9", "idealpointlegacy": "0.8",
                 "nvotesall": "40", "nvotesfp": "18"},
            ])
            output = path / "unga_ideal_points.csv"
            result = run("--input", str(raw), "--output", str(output),
                         "--fp-extension", str(path / "does_not_exist.csv"))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("not found", result.stdout)
            rows = read_rows(output)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["year"], "2024")


if __name__ == "__main__":
    unittest.main()
