"""Offline tests for scripts/annual_reports_ebrd.py -- covering the three
real document quirks found extending EBRD's shares history to 2000-2013
(docs/coding_decisions.md, 2026-09-24): a heading that drops its final "s"
in the 2011 document only, a lone dash meaning zero, and 2000's one-off
unattributable Yugoslavia reserve row."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from annual_reports_ebrd import (  # noqa: E402
    _NAME_FIXUPS,
    _TABLE_HEADING,
    _UNALLOCATED_YUGOSLAVIA,
    _parse_row,
    _resolve,
)
from _reference import iso3_from_name  # noqa: E402


class ParseRowTests(unittest.TestCase):
    def test_ordinary_comma_grouped_row(self):
        result = _parse_row("Germany 178,956 178,956 1,790 1,257 533")
        self.assertEqual(result, ("Germany", 178956.0, 178956.0))

    def test_multi_word_name(self):
        result = _parse_row("Bosnia and Herzegovina 5,071 5,071 51 40 11")
        self.assertEqual(result[0], "Bosnia and Herzegovina")

    def test_decimal_capital_columns_2003_style(self):
        # 2003's document uses one decimal place for the capital columns
        # ("19,789.5" not "19,789") -- shares/votes stay whole numbers.
        result = _parse_row("Austria 47,903 47,903 479.0 336.3 142.7")
        self.assertEqual(result, ("Austria", 47903.0, 47903.0))

    def test_trailing_page_number_artifact_is_ignored(self):
        # Confirmed real: pdfplumber merges the page-footer number onto
        # this exact row in the 2000 document.
        result = _parse_row("Croatia 7,292 7,292 72,920 53,780 19,140 87")
        self.assertEqual(result, ("Croatia", 7292.0, 7292.0))

    def test_lone_dash_reads_as_zero(self):
        # Confirmed real, 2011: a brand-new member with negligible
        # paid-in capital that year, not a missing value.
        result = _parse_row("Jordan 100 100 1 1 –")
        self.assertEqual(result, ("Jordan", 100.0, 100.0))

    def test_section_header_line_does_not_match(self):
        self.assertIsNone(_parse_row("Members of the European Union"))

    def test_column_header_line_does_not_match(self):
        self.assertIsNone(_parse_row("(number) (number) €000 €000 €000"))


class UnallocatedYugoslaviaTests(unittest.TestCase):
    def test_matches_the_real_2000_line_and_strips_the_glued_footnote_digit(self):
        line = "forming part of Yugoslavia 4,6753 – 46,750 32,730 14,020"
        match = _UNALLOCATED_YUGOSLAVIA.search(line)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "4,675")  # not "4,6753" -- "3" is a footnote marker

    def test_does_not_match_an_ordinary_country_row(self):
        self.assertIsNone(_UNALLOCATED_YUGOSLAVIA.search("Croatia 7,292 7,292 72,920 53,780 19,140"))


class TableHeadingTests(unittest.TestCase):
    def test_plural_heading_matches(self):
        self.assertTrue(_TABLE_HEADING.search("Statement of capital subscriptions\nMembers"))

    def test_2011_singular_heading_also_matches(self):
        self.assertTrue(_TABLE_HEADING.search("Statement of capital subscription\nMembers"))

    def test_unrelated_text_does_not_match(self):
        self.assertFalse(_TABLE_HEADING.search("25. Subscribed capital"))


class NameFixupResolutionTests(unittest.TestCase):
    def test_macedonia_variants_both_resolve(self):
        self.assertEqual(_resolve("Former Yugoslav Republic of Macedonia"), "MKD")
        self.assertEqual(_resolve("FYR Macedonia"), "MKD")

    def test_ordinary_name_still_resolves_without_a_fixup(self):
        self.assertEqual(_resolve("Germany"), "DEU")

    def test_yugoslav_successor_state_stays_unresolved_not_guessed(self):
        for name in ("FR Yugoslavia", "Federal Republic of Yugoslavia", "Serbia and Montenegro"):
            self.assertEqual(iso3_from_name(name), "", msg=name)


if __name__ == "__main__":
    unittest.main()
