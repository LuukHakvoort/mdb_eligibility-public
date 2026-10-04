"""Offline tests for scripts/annual_reports_idb_ar.py's row readers (docs/coding_decisions.md, 2026-09-25)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from annual_reports_idb_ar import parse_shares_layout, parse_table_layout  # noqa: E402


class LayoutTests(unittest.TestCase):
    def test_2002_2007_dot_leader_row_gives_shares_and_vote_percentage(self):
        rows = parse_shares_layout(["Argentina . . . . . . . . . . . . . . . . . 900,154 900,289 10.752"] * 1)
        self.assertEqual(rows["Argentina"], (900154.0, 10.752))

    def test_2008_table_row_reads_paid_in_plus_callable_and_the_three_decimal_vote_percentage(self):
        rows = parse_table_layout(["Argentina $ 465.1 $ 10,393.8 $ 10,858.9 10.752 $ 505.4"])
        self.assertAlmostEqual(rows["Argentina"][0], 465.1 + 10393.8)
        self.assertEqual(rows["Argentina"][1], 10.752)

    def test_glued_footnote_letter_and_lowercase_us_are_resolved(self):
        rows = parse_table_layout(["Canadac 214.5 6,896.1 7,110.6 4.003 329.7", "united States 1,303.0 29,006.7 30,309.7 30.006 5,076.4"])
        self.assertEqual(set(rows), {"Canada", "united States"})

    def test_row_with_a_dash_for_paid_in_and_the_2020_additional_paid_in_column(self):
        rows = parse_table_layout(["Bahamas 15.1 341.4 6.0 362.5 0.209"])
        self.assertEqual(rows["Bahamas"][1], 0.209)

    def test_total_rows_are_not_members(self):
        self.assertEqual(parse_table_layout(["Total regional developing members 2,170.5 48,311.4 50,481.1 50.015 2,610.3"]), {})


if __name__ == "__main__":
    unittest.main()
