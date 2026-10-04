"""Offline tests for scripts/annual_reports_badea_annex.py (docs/coding_decisions.md, 2026-09-25)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from annual_reports_badea_annex import _num, parse  # noqa: E402


class NumberTests(unittest.TestCase):
    def test_dot_grouped_and_comma_grouped_numbers(self):
        self.assertEqual(_num("4.484.807.66"), 4484807.66)
        self.assertEqual(_num("4,280.95"), 4280.95)

    def test_a_comma_in_a_percentage_is_a_decimal_point(self):
        self.assertEqual(_num("2,065961", True), 2.065961)


class RowTests(unittest.TestCase):
    def test_wrapped_name_and_the_200_basic_votes_identity(self):
        members, total, _ = parse([
            "People’s Democratic Republic",
            "89696153.36 896.96153 4.077098 1096.96153 4.285006",
            "of Algeria",
        ])
        self.assertEqual(members["DZA"][:2], (896.96153, 1096.96153))

    def test_scan_debris_and_misspelled_name_are_tolerated(self):
        members, _, _ = parse(["Kmgdom of Saudi Arabia 366938809 21 3669.38809 24.462587 3869.38809 20.803162 •"])
        self.assertEqual(members["SAU"][1], 3869.38809)

    def test_comma_typo_in_votes_is_repaired_by_the_identity(self):
        members, _, _ = parse(["Sultanate of Oman 51.372 513.72 1.29 713,72 1.64"])
        self.assertEqual(members["OMN"][1], 713.72)


if __name__ == "__main__":
    unittest.main()
