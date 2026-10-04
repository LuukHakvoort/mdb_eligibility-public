"""Offline tests for scripts/annual_reports_ibrd.py -- real row shapes from
IBRD's EDGAR annual reports, FY2003-FY2026 (docs/coding_decisions.md,
2026-09-24)."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _reference import iso3_from_name  # noqa: E402
from annual_reports_ibrd import (  # noqa: E402
    _NAME_FIXUPS,
    _TEXT_ROW,
    _text_member_rows,
    cache_name_for,
    parse_member_row,
)


class ParseMemberRowTests(unittest.TestCase):
    def test_2024_layout(self):
        row = ["Afghanistan", "506", "0.02", "%", "$ 61.0", "$ 5.1", "$ 55.9", "", "1,339", "0.05", "%"]
        self.assertEqual(parse_member_row(row), ("Afghanistan", 506.0, 1339.0))

    def test_2005_layout_has_blank_spacer_cells_and_dollar_cells(self):
        row = ["Afghanistan", "", "300", "", "0.02", "%", "$", "36.2", "", "$", "3.6", "", "$", "32.6", "", "550", "", "0.03", "%"]
        self.assertEqual(parse_member_row(row), ("Afghanistan", 300.0, 550.0))

    def test_row_without_dollar_or_percent_signs(self):
        row = ["Albania", "", "830", "", "0.05", "", "", "100.1", "", "", "3.6", "", "", "96.5", "", "1,080", "", "0.07", ""]
        self.assertEqual(parse_member_row(row), ("Albania", 830.0, 1080.0))

    def test_footnote_marker_variants_on_the_name_are_stripped(self):
        row = ["Kosovo, Republic of ( c)", "1,000", "0.05", "5.0", "1.0", "4.0", "1,250", "0.05"]
        self.assertEqual(parse_member_row(row)[0], "Kosovo, Republic of")
        row2 = ["Kosovo, Republic of (c)", "1,000", "0.05", "5.0", "1.0", "4.0", "1,250", "0.05"]
        self.assertEqual(parse_member_row(row2)[0], "Kosovo, Republic of")

    def test_header_rows_are_not_data(self):
        self.assertIsNone(parse_member_row(["Member", "", "Shares", "", "Percentage of total"]))
        self.assertIsNone(parse_member_row(["", "", "Subscriptions", "", "Voting Power", ""]))
        self.assertIsNone(parse_member_row([]))

    def test_the_total_row_is_returned_like_any_other_row(self):
        row = ["Total—June 30, 2015", "", "", "2,095,748", "", "", "", "100.00", "%", "", "$", "252,821", "", "$", "15,192", "", "$", "237,629", "", "", "2,218,888", "", "", "100.00", "%"]
        self.assertEqual(parse_member_row(row), ("Total—June 30, 2015", 2095748.0, 2218888.0))

    def test_the_prior_year_comparative_total_has_no_percentage_cells_and_so_is_not_a_reliable_total(self):
        # Confirmed real (FY2005, FY2015): this row's second-to-last number is
        # the "subject to call" amount, not votes -- the parser must use the
        # *first* Total row, which is what parse_filing() does.
        row = ["Total—June 30, 2014", "", "", "1,929,711", "", "", "", "", "", "", "$", "232,791", "", "$", "14,005", "", "$", "218,786", "", "", "2,043,075", "", "", "", "", ""]
        self.assertEqual(parse_member_row(row)[2], 218786.0)


class TextFilingTests(unittest.TestCase):
    def test_dot_leader_row(self):
        line = "Afghanistan..............................        300       0.02%  $  36.2     $   3.6       $   32.6           550       0.03%"
        match = _TEXT_ROW.match(line)
        self.assertEqual((match.group(1), match.group(2), match.group(3)), ("Afghanistan", "300", "550"))

    def test_dot_leader_row_without_dollar_or_percent_signs(self):
        line = "Albania..................................        830       0.05       100.1         3.6           96.5         1,080       0.07"
        match = _TEXT_ROW.match(line)
        self.assertEqual((match.group(1), match.group(2), match.group(3)), ("Albania", "830", "1,080"))

    def test_name_with_a_comma_and_a_period(self):
        line = "St. Kitts and Nevis......................        300       0.02       36.2         3.6           32.6           550       0.03"
        self.assertEqual(_TEXT_ROW.match(line).group(1), "St. Kitts and Nevis")

    def test_total_row_is_read_from_after_the_label_dot_leaders(self):
        text = (
            "STATEMENT OF SUBSCRIPTIONS TO\nCAPITAL STOCK AND VOTING POWER\nJune 30, 2003\n"
            "Zimbabwe.................................      3,325       0.21       401.1        22.4          378.7         3,575       0.22\n"
            "Total--June 30, 2003(2)..................  1,571,412     100.00%    $189,567    $11,478       $178,089     1,617,412     100.00%\n"
            "THE NOTES TO FINANCIAL STATEMENTS ARE AN INTEGRAL PART"
        )
        rows = _text_member_rows(text, 2003, Path("x"))
        total = [r for r in rows if r[0].startswith("Total")]
        self.assertEqual(parse_member_row(total[0])[1:], (1571412.0, 1617412.0))

    def test_a_filing_for_a_different_year_is_refused(self):
        text = "STATEMENT OF SUBSCRIPTIONS TO\nCAPITAL STOCK AND VOTING POWER\nJune 30, 2003\n"
        with self.assertRaises(SystemExit):
            _text_member_rows(text, 2004, Path("x"))


class NameAndCacheTests(unittest.TestCase):
    def test_fixups_resolve(self):
        for raw in _NAME_FIXUPS:
            self.assertTrue(iso3_from_name(_NAME_FIXUPS[raw]), msg=raw)
        self.assertEqual(iso3_from_name(_NAME_FIXUPS["Macedonia, Former Yugoslav Republic Of"]), "MKD")
        self.assertEqual(iso3_from_name(_NAME_FIXUPS["Naoero"]), "NRU")

    def test_predecessor_state_stays_unresolved_not_guessed(self):
        self.assertEqual(iso3_from_name("Serbia and Montenegro"), "")

    def test_cache_name_is_derived_from_the_url(self):
        url = "https://www.sec.gov/Archives/edgar/data/51120/000119312524226788/d879006dannlrpt.htm"
        self.assertEqual(cache_name_for(url), "sec_51120_000119312524226788_d879006dannlrpt.htm")


if __name__ == "__main__":
    unittest.main()
