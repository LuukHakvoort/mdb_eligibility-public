"""Offline tests for scripts/build_unga_iv.py, scripts/merge_unga_iv.py, and
scripts/report_largest_shareholders.py -- the four UNGA independent-variable
constructions (hegemonic, G7, G10, large shareholders, coalition), their
merge onto the panel, and the largest-shareholder-per-bank report.
"""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

WEIGHTS_FIELDS = ["bank", "iso3", "year", "weight_pct", "weight_basis", "weight_source_year"]
IDEAL_POINTS_FIELDS = ["iso3", "year", "idealpoint_all", "idealpoint_fp"]
PANEL_GRID_FIELDS = ["bank", "iso3", "year"]


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


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, cwd=REPO,
    )


class BuildUngaIvTests(unittest.TestCase):
    def _fixture(self, directory: Path):
        # TESTBANK/2020 (+2019 for the t-1 lag): USA/FRA/JPN are G7 (and
        # therefore G10 too); NLD is G10-only; BRA clears the 5% large-
        # shareholder threshold but isn't G7/G10; KEN does not clear it.
        weights_rows = []
        ideal_rows = []
        for year, ips in ((2020, {"USA": 1.0, "FRA": 0.6, "JPN": 0.4, "BRA": -0.3, "KEN": -0.8, "NLD": 0.5}),
                          (2019, {"USA": 0.9, "FRA": 0.5, "JPN": 0.3, "BRA": -0.4, "KEN": -0.9, "NLD": 0.4})):
            for iso3, weight in (("USA", 40), ("FRA", 30), ("JPN", 20), ("BRA", 8), ("KEN", 2), ("NLD", 1)):
                weights_rows.append({"bank": "TESTBANK", "iso3": iso3, "year": str(year),
                                      "weight_pct": str(weight), "weight_basis": "voting", "weight_source_year": ""})
                ideal_rows.append({"iso3": iso3, "year": str(year),
                                    "idealpoint_all": str(ips[iso3]), "idealpoint_fp": str(ips[iso3])})
        # TZA is the recipient: not a TESTBANK shareholder at all.
        ideal_rows.append({"iso3": "TZA", "year": "2020", "idealpoint_all": "-0.2", "idealpoint_fp": "-0.2"})
        ideal_rows.append({"iso3": "TZA", "year": "2019", "idealpoint_all": "-0.3", "idealpoint_fp": "-0.3"})
        # TIEBANK/2020: an exact weight tie -- alphabetical tie-break.
        weights_rows.append({"bank": "TIEBANK", "iso3": "BBB", "year": "2020",
                              "weight_pct": "50", "weight_basis": "capital", "weight_source_year": ""})
        weights_rows.append({"bank": "TIEBANK", "iso3": "AAA", "year": "2020",
                              "weight_pct": "50", "weight_basis": "capital", "weight_source_year": ""})

        weights = write_csv(directory / "weights.csv", WEIGHTS_FIELDS, weights_rows)
        ideal_points = write_csv(directory / "ideal_points.csv", IDEAL_POINTS_FIELDS, ideal_rows)
        panel = write_csv(directory / "panel.csv", PANEL_GRID_FIELDS, [{"bank": "TESTBANK", "iso3": "TZA", "year": "2020"}])
        return weights, ideal_points, panel

    def test_hegemonic_ties_break_alphabetically_by_iso3(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            weights, ideal_points, panel = self._fixture(path)
            ref_out, dist_out = path / "reference.csv", path / "distances.csv"
            result = run("build_unga_iv.py", "--weights", str(weights), "--ideal-points", str(ideal_points),
                         "--panel", str(panel), "--reference-output", str(ref_out), "--distances-output", str(dist_out))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["year"]): r for r in read_rows(ref_out)}
            self.assertEqual(rows[("TIEBANK", "2020")]["largest_shareholder_iso3"], "AAA")

    def test_g7_g10_ls_and_coalition_pools_are_renormalized_correctly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            weights, ideal_points, panel = self._fixture(path)
            ref_out, dist_out = path / "reference.csv", path / "distances.csv"
            result = run("build_unga_iv.py", "--weights", str(weights), "--ideal-points", str(ideal_points),
                         "--panel", str(panel), "--reference-output", str(ref_out), "--distances-output", str(dist_out))
            self.assertEqual(result.returncode, 0, result.stderr)
            row = {(r["bank"], r["year"]): r for r in read_rows(ref_out)}[("TESTBANK", "2020")]

            self.assertEqual(row["largest_shareholder_iso3"], "USA")
            # The fixture gives every shareholder both idealpoint_all and
            # idealpoint_fp, so the two measures' counts agree here -- the
            # measures-differ case (idealpoint_all missing but idealpoint_fp
            # present) is covered separately below.
            for suffix in ("_all", "_fp"):
                self.assertEqual(row[f"g7_n_shareholders{suffix}"], "3.0")   # USA, FRA, JPN
                self.assertEqual(row[f"g10_n_shareholders{suffix}"], "4.0")  # + NLD
                self.assertEqual(row[f"ls_n_shareholders{suffix}"], "4.0")   # USA, FRA, JPN, BRA (>5%)
                self.assertEqual(row[f"coalition_n_shareholders{suffix}"], "6.0")  # everyone

    def test_a_shareholder_missing_just_one_measure_still_counts_for_the_other(self):
        # Regression test: idealpoint_fp now reaches 2025 while idealpoint_all
        # never does (build_unga_ideal_points.py's FP extension), so a pool
        # can have real idealpoint_fp coverage with zero idealpoint_all
        # coverage. Sharing one renormalization across both measures used to
        # silently produce a spurious 0.0 for the all-null measure instead of
        # a proper blank -- pandas' .sum() skips the NaN contribution but
        # still counted that shareholder's weight in the denominator.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            weights = write_csv(path / "weights.csv", WEIGHTS_FIELDS, [
                {"bank": "TESTBANK", "iso3": "USA", "year": "2025", "weight_pct": "60",
                 "weight_basis": "voting", "weight_source_year": ""},
                {"bank": "TESTBANK", "iso3": "FRA", "year": "2025", "weight_pct": "40",
                 "weight_basis": "voting", "weight_source_year": ""},
            ])
            ideal_points = write_csv(path / "ideal_points.csv", IDEAL_POINTS_FIELDS, [
                {"iso3": "USA", "year": "2025", "idealpoint_all": "", "idealpoint_fp": "1.0"},
                {"iso3": "FRA", "year": "2025", "idealpoint_all": "", "idealpoint_fp": "0.5"},
                {"iso3": "TZA", "year": "2025", "idealpoint_all": "", "idealpoint_fp": "-0.2"},
            ])
            panel = write_csv(path / "panel.csv", PANEL_GRID_FIELDS, [{"bank": "TESTBANK", "iso3": "TZA", "year": "2025"}])
            ref_out, dist_out = path / "reference.csv", path / "distances.csv"
            result = run("build_unga_iv.py", "--weights", str(weights), "--ideal-points", str(ideal_points),
                         "--panel", str(panel), "--reference-output", str(ref_out), "--distances-output", str(dist_out))
            self.assertEqual(result.returncode, 0, result.stderr)
            row = read_rows(ref_out)[0]
            self.assertEqual(row["coalition_ip_all"], "")  # blank, never a spurious 0.0
            self.assertEqual(row["coalition_n_shareholders_all"], "")
            self.assertAlmostEqual(float(row["coalition_ip_fp"]), (60 * 1.0 + 40 * 0.5) / 100, places=6)
            # int vs "2.0"-style float formatting depends on whether any
            # other row in this single-row output forced the whole CSV
            # column to float64 -- not meaningful here, so compare numerically.
            self.assertEqual(float(row["coalition_n_shareholders_fp"]), 2.0)

    def test_individual_large_shareholder_distances_at_t_and_t1(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            weights, ideal_points, panel = self._fixture(path)
            ref_out, dist_out = path / "reference.csv", path / "distances.csv"
            result = run("build_unga_iv.py", "--weights", str(weights), "--ideal-points", str(ideal_points),
                         "--panel", str(panel), "--reference-output", str(ref_out), "--distances-output", str(dist_out))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = read_rows(dist_out)
            self.assertEqual(len(rows), 8)  # 4 qualifying (>5%) shareholders x 2 lags
            by_key = {(r["lag"], r["large_shareholder_iso3"]): r for r in rows}
            # KEN and NLD never clear the 5% threshold -- no rows for them at any lag.
            self.assertNotIn(("t", "KEN"), by_key)
            self.assertNotIn(("t", "NLD"), by_key)
            self.assertAlmostEqual(float(by_key[("t", "USA")]["distance_all"]), abs(-0.2 - 1.0), places=6)
            self.assertAlmostEqual(float(by_key[("t1", "USA")]["distance_all"]), abs(-0.3 - 0.9), places=6)
            self.assertAlmostEqual(float(by_key[("t", "BRA")]["distance_all"]), abs(-0.2 - -0.3), places=6)


REFERENCE_FIELDS = [
    "bank", "year", "largest_shareholder_iso3", "largest_shareholder_weight_pct",
    "largest_shareholder_weight_basis", "hegemonic_ip_all", "hegemonic_ip_fp",
    "g7_ip_all", "g7_n_shareholders_all", "g7_ip_fp", "g7_n_shareholders_fp",
    "g10_ip_all", "g10_n_shareholders_all", "g10_ip_fp", "g10_n_shareholders_fp",
    "ls_ip_all", "ls_n_shareholders_all", "ls_ip_fp", "ls_n_shareholders_fp",
    "coalition_ip_all", "coalition_n_shareholders_all", "coalition_ip_fp", "coalition_n_shareholders_fp",
]
FINAL_PANEL_FIELDS = ["bank", "iso3", "year", "any_lending", "note"]
DISTANCES_FIELDS = ["bank", "recipient_iso3", "year", "lag", "large_shareholder_iso3",
                     "large_shareholder_weight_pct", "distance_all", "distance_fp"]


class MergeUngaIvTests(unittest.TestCase):
    def test_row_count_never_changes_and_distances_stay_blank_not_zero_when_unmatched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            panel = write_csv(path / "panel.csv", FINAL_PANEL_FIELDS, [
                {"bank": "IBRD", "iso3": "KEN", "year": "2020", "any_lending": "1", "note": ""},
                {"bank": "IDA", "iso3": "KEN", "year": "2020", "any_lending": "0", "note": ""},
            ])
            reference = write_csv(path / "reference.csv", REFERENCE_FIELDS, [
                {"bank": "IBRD", "year": "2020", "largest_shareholder_iso3": "USA",
                 "largest_shareholder_weight_pct": "16.4", "largest_shareholder_weight_basis": "voting",
                 "hegemonic_ip_all": "1.0", "hegemonic_ip_fp": "0.9",
                 "g7_ip_all": "", "g7_n_shareholders_all": "", "g7_ip_fp": "", "g7_n_shareholders_fp": "",
                 "g10_ip_all": "", "g10_n_shareholders_all": "", "g10_ip_fp": "", "g10_n_shareholders_fp": "",
                 "ls_ip_all": "", "ls_n_shareholders_all": "", "ls_ip_fp": "", "ls_n_shareholders_fp": "",
                 "coalition_ip_all": "", "coalition_n_shareholders_all": "",
                 "coalition_ip_fp": "", "coalition_n_shareholders_fp": ""},
            ])
            ideal_points = write_csv(path / "ideal_points.csv", IDEAL_POINTS_FIELDS, [
                {"iso3": "KEN", "year": "2020", "idealpoint_all": "0.4", "idealpoint_fp": "0.3"},
                {"iso3": "KEN", "year": "2019", "idealpoint_all": "0.2", "idealpoint_fp": "0.1"},
            ])
            distances = write_csv(path / "distances.csv", DISTANCES_FIELDS, [])
            output = path / "merged.csv"
            distances_output = path / "merged_distances.csv"
            result = run(
                "merge_unga_iv.py",
                "--panel", str(panel), "--reference", str(reference), "--ideal-points", str(ideal_points),
                "--distances", str(distances), "--output", str(output), "--distances-output", str(distances_output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(output)}
            self.assertEqual(len(rows), 2)  # never filtered by the join

            ibrd = rows[("IBRD", "KEN", "2020")]
            self.assertEqual(ibrd["unga_recipient_ip_all_t"], "0.4")
            self.assertEqual(ibrd["unga_recipient_ip_all_t1"], "0.2")
            self.assertAlmostEqual(float(ibrd["unga_hegemonic_dist_all_t"]), abs(0.4 - 1.0), places=6)
            # No reference row for IBRD/2019 -- the t-1 hegemonic distance must
            # stay blank, not be treated as a zero or dropped silently.
            self.assertEqual(ibrd["unga_hegemonic_ip_all_t1"], "")
            self.assertEqual(ibrd["unga_hegemonic_dist_all_t1"], "")

            # IDA has no reference row at all -- every unga_* distance column
            # is blank, even though the recipient's own ideal point (KEN,
            # bank-independent) is still populated.
            ida = rows[("IDA", "KEN", "2020")]
            self.assertEqual(ida["unga_recipient_ip_all_t"], "0.4")
            self.assertEqual(ida["unga_hegemonic_ip_all_t"], "")
            self.assertEqual(ida["unga_hegemonic_dist_all_t"], "")


class ReportLargestShareholdersTests(unittest.TestCase):
    def test_collapses_consecutive_years_into_runs_and_flags_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)

            def ref_row(bank, year, iso3):
                return {"bank": bank, "year": year, "largest_shareholder_iso3": iso3,
                        "largest_shareholder_weight_pct": "10.0", "largest_shareholder_weight_basis": "voting",
                        "hegemonic_ip_all": "", "hegemonic_ip_fp": "",
                        "g7_ip_all": "", "g7_n_shareholders_all": "", "g7_ip_fp": "", "g7_n_shareholders_fp": "",
                        "g10_ip_all": "", "g10_n_shareholders_all": "", "g10_ip_fp": "", "g10_n_shareholders_fp": "",
                        "ls_ip_all": "", "ls_n_shareholders_all": "", "ls_ip_fp": "", "ls_n_shareholders_fp": "",
                        "coalition_ip_all": "", "coalition_n_shareholders_all": "",
                        "coalition_ip_fp": "", "coalition_n_shareholders_fp": ""}

            reference = write_csv(path / "reference.csv", REFERENCE_FIELDS, [
                ref_row("TESTBANK2", "2018", "USA"), ref_row("TESTBANK2", "2019", "USA"),
                ref_row("TESTBANK2", "2020", "FRA"), ref_row("TESTBANK2", "2021", "FRA"),
                ref_row("STABLEBANK", "2018", "USA"), ref_row("STABLEBANK", "2019", "USA"),
                ref_row("GAPBANK", "2018", "USA"), ref_row("GAPBANK", "2019", ""), ref_row("GAPBANK", "2020", "USA"),
            ])
            csv_out, md_out = path / "shareholders.csv", path / "summary.md"
            result = run("report_largest_shareholders.py", "--reference", str(reference),
                         "--csv-output", str(csv_out), "--md-output", str(md_out))
            self.assertEqual(result.returncode, 0, result.stderr)

            text = md_out.read_text(encoding="utf-8")
            self.assertIn("**TESTBANK2** (changes): USA 2018-2019, FRA 2020-2021", text)
            self.assertIn("**STABLEBANK** (unchanged): USA 2018-2019", text)
            # A no-data gap year doesn't count as a "change" if the same
            # shareholder is largest on both sides of it.
            self.assertIn("no data", text)
            self.assertIn("**GAPBANK** (unchanged):", text)


if __name__ == "__main__":
    unittest.main()
