"""Offline tests for scripts/annual_reports_adb.py -- real row shapes from ADB's
Financial Reports, OCR-8 statements 2002-2025 (docs/coding_decisions.md,
2026-09-24)."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _reference import iso3_from_name  # noqa: E402
from annual_reports_adb import (  # noqa: E402
    _HEADING,
    _NAME_FIXUPS,
    _is_total_line,
    _partition,
    parse_row,
)


class ParseRowTests(unittest.TestCase):
    def test_2002_row_comes_through_whole(self):
        line = "Afghanistan 1,195 0.034 $ 16,187 $ 11,013 $ 5,174 15,486 0.355"
        self.assertEqual(parse_row(line), ("Afghanistan", 1195, 15486, 0.355))

    def test_2013_kerning_splits_the_first_digit_of_the_shares(self):
        # Real: "Afghanistan 3 ,585 ..." is 3,585; "Australia 6 14,220" is 614,220.
        self.assertEqual(parse_row("Afghanistan 3 ,585 0.034 $ 55.2 $ 47.8 $ 7.4 43,032 0.326"), ("Afghanistan", 3585, 43032, 0.326))
        self.assertEqual(parse_row("Australia 6 14,220 5.810 9,459.0 8,985.9 473.0 653,667 4.946"), ("Australia", 614220, 653667, 4.946))

    def test_2012_integer_amounts_with_kerning_in_both_shares_and_votes(self):
        # Real: votes "4 3,189" (43,189) sit right after the integer paid-in amount.
        line = "Afghanistan 3 ,585 0.03 $ 55,099 $ 47,752 7,346 4 3,189 0.33"
        self.assertEqual(parse_row(line), ("Afghanistan", 3585, 43189, 0.33))
        line = "Australia 6 14,220 5.79 9,440,070 8,967,974 472,096 653,824 4.93"
        self.assertEqual(parse_row(line), ("Australia", 614220, 653824, 4.93))

    def test_dollar_sign_glued_onto_the_number(self):
        line = "TOTAL 3,487,017 100.000 $47,234,435 $43,912,259 $3,322,176 4,358,768 100.000"
        self.assertEqual(parse_row(line), ("TOTAL", 3487017, 4358768, 100.0))

    def test_millions_era_total_row_with_kerning_in_every_field(self):
        line = "TOTAL 1 0,603,211 100.000 1 47,051.7 139,677.8 7,373.9 13,253,999 100.000"
        self.assertEqual(parse_row(line), ("TOTAL", 10603211, 13253999, 100.0))

    def test_ocr_margin_noise_before_the_name_and_after_the_percentage(self):
        # Real OCR of the 2009 statement page.
        self.assertEqual(parse_row("a Armenia 10,557 0.271 164,899 153,309 11,590 25,069 0.516")[0], "Armenia")
        self.assertEqual(parse_row("oa Bangladesh 108,384 2.787 1,692,947 1,608,287 84,660 122,896 2.528")[0], "Bangladesh")
        self.assertEqual(parse_row("[e) People’s Republic of China 228,000 5.862 3,561,337 3,311,872 249,465 242,512 4.988")[0],
                         "People’s Republic of China")
        self.assertEqual(parse_row("Denmark 12,040 0.310 188,064 174,896 13,168 26,552 0.546 2"), ("Denmark", 12040, 26552, 0.546))
        self.assertEqual(parse_row("Austria 12,040 0.310 188,064 174,896 13,168 26,552 0.546 Baa")[0], "Austria")

    def test_header_and_note_lines_are_not_rows(self):
        self.assertIsNone(parse_row("MEMBERS Shares of Total Total Callable Paid-in Votes of Total"))
        self.assertIsNone(parse_row("Note: Figures may not add due to rounding."))
        self.assertIsNone(parse_row("31 December 2009"))


class PartitionTests(unittest.TestCase):
    def test_unsplit_tokens(self):
        self.assertEqual(_partition(["55,099", "47,752", "7,346", "43,189"]), [55099, 47752, 7346, 43189])

    def test_a_split_votes_number_is_joined_only_where_total_equals_callable_plus_paid_in(self):
        self.assertEqual(_partition(["55,099", "47,752", "7,346", "4", "3,189"]), [55099, 47752, 7346, 43189])

    def test_no_consistent_split_means_no_answer_rather_than_a_guess(self):
        self.assertIsNone(_partition(["55,099", "47,752", "9,999", "43,189"]))


class StatementTests(unittest.TestCase):
    def test_heading_with_ocr_noise_before_the_date(self):
        text = "STATEMENT OF SUBSCRIPTIONS TO CAPITAL STOCK AND VOTING POWER\n\nWn 31 December 2009"
        self.assertEqual(_HEADING.search(text).group(1), "2009")

    def test_grand_total_line_but_not_a_subtotal(self):
        self.assertTrue(_is_total_line("TOTAL 3,889,343 100.000 $60,751,149 $56,640,850 $4,110,299 $4,861,647 100.000"))
        self.assertTrue(_is_total_line("TOTALS 3,546,311 100.000 $55,977,810 $52,040,702 $3,937,108 4,432,855 100.000"))
        self.assertFalse(_is_total_line("Total Regional (Forward) 2,591,027 66.619 40,471,583 37,781,648 2,689,934 3,287,603 67.623"))
        self.assertFalse(_is_total_line("Total Nonregional 1,298,316 33.381 20,279,566 18,859,202 1,420,364 1,574,044 32.377"))

    def test_fixups_resolve(self):
        for raw, fixed in _NAME_FIXUPS.items():
            self.assertTrue(iso3_from_name(fixed), msg=raw)
        self.assertEqual(iso3_from_name(_NAME_FIXUPS["China, People’s Rep. of"]), "CHN")
        self.assertEqual(iso3_from_name(_NAME_FIXUPS["Taipei,China"]), "TWN")


if __name__ == "__main__":
    unittest.main()
