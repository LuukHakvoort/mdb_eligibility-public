"""Offline tests for scripts/build_shareholder_weights.py -- the vote-power/
capital-share fallback and the carry-forward (LOCF) logic that feeds the
UNGA independent variables (scripts/build_unga_iv.py).
"""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

MEMBERSHIP_FIELDS = ["bank", "iso3", "year", "member", "capital_share_pct", "voting_power_pct"]


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
        [sys.executable, str(SCRIPTS / "build_shareholder_weights.py"), *args],
        capture_output=True, text=True, cwd=REPO,
    )


class BuildShareholderWeightsTests(unittest.TestCase):
    def test_voting_power_preferred_over_capital_share(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            membership = write_csv(path / "membership.csv", MEMBERSHIP_FIELDS, [
                {"bank": "IBRD", "iso3": "USA", "year": "2015", "member": "1",
                 "capital_share_pct": "17.0", "voting_power_pct": "16.4"},
            ])
            output = path / "weights.csv"
            result = run("--membership", str(membership), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            row = read_rows(output)[0]
            self.assertEqual(row["weight_pct"], "16.4")
            self.assertEqual(row["weight_basis"], "voting")
            self.assertEqual(row["weight_source_year"], "")

    def test_falls_back_to_capital_share_when_voting_power_is_missing(self):
        # EIB never publishes voting_power_pct at all -- this is the only
        # way it gets any weight coverage.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            membership = write_csv(path / "membership.csv", MEMBERSHIP_FIELDS, [
                {"bank": "EIB", "iso3": "DEU", "year": "2015", "member": "1",
                 "capital_share_pct": "18.8", "voting_power_pct": ""},
            ])
            output = path / "weights.csv"
            result = run("--membership", str(membership), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            row = read_rows(output)[0]
            self.assertEqual(row["weight_pct"], "18.8")
            self.assertEqual(row["weight_basis"], "capital")

    def test_carries_the_last_known_weight_forward_across_a_gap_year(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            membership = write_csv(path / "membership.csv", MEMBERSHIP_FIELDS, [
                {"bank": "AIIB", "iso3": "CHN", "year": "2016", "member": "1",
                 "capital_share_pct": "33.0", "voting_power_pct": ""},
                {"bank": "AIIB", "iso3": "CHN", "year": "2017", "member": "1",
                 "capital_share_pct": "", "voting_power_pct": ""},
            ])
            output = path / "weights.csv"
            result = run("--membership", str(membership), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {r["year"]: r for r in read_rows(output)}
            self.assertEqual(rows["2017"]["weight_pct"], "33.0")
            self.assertEqual(rows["2017"]["weight_basis"], "capital_carried_forward")
            self.assertEqual(rows["2017"]["weight_source_year"], "2016")
            # The real row is untouched: no "carried_forward" tag, no source year.
            self.assertEqual(rows["2016"]["weight_basis"], "capital")
            self.assertEqual(rows["2016"]["weight_source_year"], "")

    def test_carry_forward_never_crosses_a_non_member_year(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            membership = write_csv(path / "membership.csv", MEMBERSHIP_FIELDS, [
                {"bank": "EBRD", "iso3": "GBR", "year": "2010", "member": "1",
                 "capital_share_pct": "10.0", "voting_power_pct": ""},
                {"bank": "EBRD", "iso3": "GBR", "year": "2011", "member": "0",
                 "capital_share_pct": "", "voting_power_pct": ""},
                {"bank": "EBRD", "iso3": "GBR", "year": "2012", "member": "1",
                 "capital_share_pct": "", "voting_power_pct": ""},
            ])
            output = path / "weights.csv"
            result = run("--membership", str(membership), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {r["year"]: r for r in read_rows(output)}
            # 2011 is not a member at all -- dropped from the output entirely.
            self.assertNotIn("2011", rows)
            # 2012 re-joined with no weight data of its own -- must NOT carry
            # forward the 2010 value across the 2011 non-member gap.
            self.assertEqual(rows["2012"]["weight_pct"], "")
            self.assertEqual(rows["2012"]["weight_source_year"], "")


if __name__ == "__main__":
    unittest.main()
