"""Offline tests for scripts/annual_reports_ida.py -- real line shapes from
IDA's FY2005-FY2026 financial statements (docs/coding_decisions.md,
2026-09-24), including the OCR'd FY2006/FY2007 ones."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from annual_reports_ida import (  # noqa: E402
    _ROW,
    _TOTAL_ALL,
    _TOTAL_ROW,
    _clean_ocr_line,
    _resolve,
    parse_rows,
)


class RowTests(unittest.TestCase):
    def test_first_row_of_a_group_carries_a_percent_sign_and_a_dollar_sign(self):
        m = _ROW.match("Australia 216,245 1.25% $ 2,645.63")
        self.assertEqual((m.group(1), m.group(2), m.group(4)), ("Australia", "216,245", "2,645.63"))

    def test_later_rows_have_neither(self):
        m = _ROW.match("Austria 126,704 0.73 1,499.63")
        self.assertEqual((m.group(1), m.group(2), m.group(4)), ("Austria", "126,704", "1,499.63"))

    def test_percent_sign_after_a_space(self):
        m = _ROW.match("Albania 61,859 0.20 % $ 0.38")
        self.assertEqual((m.group(2), m.group(4)), ("61,859", "0.38"))

    def test_multi_word_name_with_a_comma(self):
        m = _ROW.match("Egypt, Arab Republic of 134,452 0.43 18.52")
        self.assertEqual(m.group(1), "Egypt, Arab Republic of")

    def test_ocr_misread_row_with_a_dollar_before_the_votes_and_no_decimal_point_in_the_percentage(self):
        # Real FY2006 OCR: Korea, "$ 94,639 060% $ 690.80" for 94,639 / 0.60%.
        m = _ROW.match("Korea, Republic of $ 94,639 060% $ 690.80")
        self.assertEqual((m.group(1), m.group(2), m.group(4)), ("Korea, Republic of", "94,639", "690.80"))

    def test_a_debt_table_row_is_not_a_member_row(self):
        # The neighbouring "Summary Statement of Development Credits" table.
        self.assertIsNone(_ROW.match("Tanzania $4,513 $ 754 $3,759 3.11%"))
        self.assertIsNone(_ROW.match("Niger 1,240 129 1,111 0.87"))


class TotalRowTests(unittest.TestCase):
    def test_dated_total_with_a_glued_footnote_letter(self):
        # "2015b": the footnote letter is glued straight onto the year.
        m = _TOTAL_ROW.match("Total—June 30, 2015b 25,120,295 100.00 % $ 244,694")
        self.assertEqual((m.group(1), m.group(2), m.group(4)), ("2015", "25,120,295", "244,694"))

    def test_the_prior_year_comparative_total_has_no_percentage_and_does_not_match(self):
        self.assertIsNone(_TOTAL_ROW.match("Total—June 30, 2014 23,804,709 $ 225,800"))

    def test_fy2023_labels_the_current_total_all_members_with_a_bare_100(self):
        m = _TOTAL_ALL.match("Total All Members b 31,149,851 100 % $ 310,672")
        self.assertEqual((m.group(1), m.group(3)), ("31,149,851", "310,672"))

    def test_parse_rows_uses_the_current_years_total_not_the_comparative(self):
        lines = [
            "Australia 216,245 1.25% $ 2,645.63",
            "Subtotal Part I Members b 10,240,914 59.37% $172,078.37",
            "Total—June 30, 2008 b 17,248,162 100.00% $177,038.35",
            "Total—June 30, 2007 16,678,266 100.00% $168,438.55",
        ]
        members, total = parse_rows(lines, 2008)
        self.assertEqual(list(members), ["Australia"])
        self.assertEqual(total, (17248162.0, 177038.35))

    def test_subtotals_and_group_totals_are_not_members(self):
        lines = ["Subtotal Non-Recipients 24,837,060 79.73 % $ 309,571.10", "Total Recipients 4,737,642 15.21 % $ 254.10"]
        members, _ = parse_rows(lines, 2023)
        self.assertEqual(members, {})


class OcrTests(unittest.TestCase):
    def test_a_comma_followed_by_exactly_two_digits_is_a_decimal_point(self):
        self.assertEqual(_clean_ocr_line("Pakistan 144,828 0.92 13,99"), "Pakistan 144,828 0.92 13.99")

    def test_a_real_thousands_separator_is_left_alone(self):
        self.assertEqual(_clean_ocr_line("Japan 1,721,312 9.98 34,302.66"), "Japan 1,721,312 9.98 34,302.66")
        self.assertEqual(_clean_ocr_line("Canada 475,564 2.76 6,366"), "Canada 475,564 2.76 6,366")


class NameTests(unittest.TestCase):
    def test_footnote_letter_glued_onto_a_name_is_retried_without_it(self):
        self.assertEqual(_resolve("Estoniac"), "EST")
        self.assertEqual(_resolve("Tuvaluc"), "TUV")
        self.assertEqual(_resolve("Bahamas, Thec"), "BHS")

    def test_a_real_name_ending_in_a_letter_is_never_truncated(self):
        self.assertEqual(_resolve("Cyprus"), "CYP")
        self.assertEqual(_resolve("Bhutan"), "BTN")

    def test_fixups_and_predecessor_state(self):
        self.assertEqual(_resolve("Macedonia, former Yugoslav Republic of"), "MKD")
        self.assertEqual(_resolve("Kosovo, Republic ofd"), "XKX")
        self.assertEqual(_resolve("Serbia and Montenegro"), "")


if __name__ == "__main__":
    unittest.main()
