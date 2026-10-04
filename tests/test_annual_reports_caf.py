"""Offline tests for scripts/annual_reports_caf.py's cell reading (docs/coding_decisions.md, 2026-09-25)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from annual_reports_caf import _solve  # noqa: E402


class PaidInRowTests(unittest.TestCase):
    def test_clean_row(self):
        self.assertEqual(_solve("1 119,079 - 1,200 595,395 - 596,595".split(), "paid")[6], 596595)

    def test_kerned_row_is_rejoined_by_the_identities(self):
        # 2018's text layer splits the first digit off: "1 00,404" is 100,404
        row = "1 1 00,404 - 1 ,200 5 02,020 - 503,220".split()
        self.assertEqual(_solve(row, "paid")[6], 503220)

    def test_printed_total_in_the_wrong_cell_is_replaced_by_the_sum_of_the_amounts(self):
        self.assertEqual(_solve("- - 6,567 - - 32,835 198,695".split(), "paid")[6], 32835)


class UnpaidRowTests(unittest.TestCase):
    def test_amounts_are_summed_across_series_and_a_blank_pair_is_tolerated(self):
        self.assertEqual(_solve("142 710 - - - -".split(), "unpaid"), [710])
        self.assertEqual(_solve("31,120 155,600 - - 25,200 126,000 - -".split(), "unpaid"), [281600])

    def test_amounts_rounded_to_the_thousand_are_accepted(self):
        self.assertEqual(_solve("- - 346 1,730 - - 15,688 78,439".split(), "unpaid"), [80169])

    def test_a_row_that_breaks_the_five_dollar_par_is_rejected(self):
        self.assertIsNone(_solve("100 999".split(), "unpaid"))


if __name__ == "__main__":
    unittest.main()
