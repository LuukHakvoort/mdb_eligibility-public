"""Offline tests for scripts/annual_reports_isdb.py -- one real line from each
layout found across IsDB's 2011-2025 annual reports (docs/coding_decisions.md,
2026-09-24), since the whole difficulty of this parser is that every few
years the same table is printed a little differently."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from annual_reports_isdb import (  # noqa: E402
    _CAPITAL_AMOUNT_ROW,
    _CAPITAL_ROW,
    _CAPITAL_ROW_MID,
    _COMBINED_ROW,
    _COMBINED_ROW_2012,
    _COMBINED_ROW_6,
    _VOTING_ROW,
    _VOTING_ROW_MID,
    parse_lines,
)


class CombinedLayoutTests(unittest.TestCase):
    def test_2013_style_row(self):
        match = _COMBINED_ROW.match("Afghanistan 993 5.00 4.93 9.93 0.06 3.80 * 1.20 1,373 0.10")
        self.assertEqual((match.group(1), match.group(2), match.group(3)), ("Afghanistan", "993", "1,373"))

    def test_2014_sidebar_text_glued_onto_the_end_does_not_break_the_row(self):
        line = "Kuwait 350,000 880.90 2619.10 3500.00 6.92 496.64 0.00 384.26 312,074 7.33 Facts and Figures on IDB Group Approvals"
        match = _COMBINED_ROW.match(line)
        self.assertEqual((match.group(1), match.group(2), match.group(3)), ("Kuwait", "350,000", "312,074"))

    def test_2011_row_has_a_serial_number_and_percent_signs(self):
        match = _COMBINED_ROW.match("1 Afghanistan 993 5.000 4.930 9.930 0.06% 3.268 0 1.732 1,320 0.10%")
        self.assertEqual((match.group(1), match.group(2), match.group(3)), ("Afghanistan", "993", "1,320"))

    def test_subtotal_row_can_carry_decimal_votes(self):
        # 2015's printed Sub-Total sums fractional vote counts.
        line = "Sub-Total 4,991,841 9,354.64 40,563.77 49,918.41 98.69 4,940.00 135.60 4,279.04 4,578,363.08 100.00"
        match = _COMBINED_ROW.match(line)
        self.assertEqual((match.group(1), match.group(3)), ("Sub-Total", "4,578,363.08"))

    def test_2012_variant_has_percent_right_after_shares_and_negative_zero_cells(self):
        line = "3 Algeria 45,922 2.55% 459.22 334.96 123.66 0.60 -0.00 35,734 2.61%"
        match = _COMBINED_ROW_2012.match(line)
        self.assertEqual((match.group(1), match.group(2), match.group(3)), ("Algeria", "45,922", "35,734"))

    def test_split_capital_row_is_not_mistaken_for_a_combined_row(self):
        self.assertIsNone(_COMBINED_ROW.match("1 Saudi Arabia 1,189,680 2,135.9 9,761.0 11,896.8 23.50% 1,369.0 0.0 766.9"))


class OlderCombinedLayoutTests(unittest.TestCase):
    def test_2007_2008_rows_have_six_cells_not_seven_and_no_percent_signs(self):
        # "1 Afghanistan 993 0.07 9.93 4.930 2.600 1.172 1.228 1,253 0.12"
        m = _COMBINED_ROW_6.match("1 Afghanistan 993 0.07 9.93 4.930 2.600 1.172 1.228 1,253 0.12")
        self.assertEqual((m.group(1), m.group(2), m.group(3)), ("Afghanistan", "993", "1,253"))

    def test_2007_row_with_an_asterisk_cell_and_a_long_name(self):
        m = _COMBINED_ROW_6.match("21 Islamic Republic of Iran 129,334 9.32 1,293.34 943.370 265.928 * 84.042 91,499 8.92")
        self.assertEqual((m.group(1), m.group(2), m.group(3)), ("Islamic Republic of Iran", "129,334", "91,499"))

    def test_2009_serial_number_has_a_trailing_period_and_percent_signs_return(self):
        m = _COMBINED_ROW.match("1. Afghanistan 993 5.000 4.930 9.930 0.06% 2.600 0.133 2.267 1,253 0.11%")
        self.assertEqual((m.group(1), m.group(2), m.group(3)), ("Afghanistan", "993", "1,253"))

    def test_six_cell_row_is_not_mistaken_for_the_seven_cell_layout(self):
        self.assertIsNone(_COMBINED_ROW.match("1 Afghanistan 993 0.07 9.93 4.930 2.600 1.172 1.228 1,253 0.12"))

    def test_iran_long_form_resolves(self):
        members, unresolved, _ = parse_lines(["21 Islamic Republic of Iran 129,334 9.32 1,293.34 943.370 265.928 * 84.042 91,499 8.92"])
        self.assertEqual(unresolved, [])
        self.assertEqual(members["IRN"], {"shares": 129334.0, "votes": 91499.0})


class SplitLayoutTests(unittest.TestCase):
    def test_capital_row_with_running_serial_number(self):
        match = _CAPITAL_ROW.match("1 Saudi Arabia 1,189,680 2,135.9 9,761.0 11,896.8 23.50% 1,369.0 0.0 766.9")
        self.assertEqual((match.group(1), match.group(2)), ("Saudi Arabia", "1,189,680"))

    def test_capital_row_without_serial_number(self):
        match = _CAPITAL_ROW.match("Saudi Arabia 1,319,868 3,437.73 9,760.95 13,198.68 22.50% 1,825.63 0.00 1,612.10")
        self.assertEqual((match.group(1), match.group(2)), ("Saudi Arabia", "1,319,868"))

    def test_2017_row_has_no_percent_sign_and_drops_an_empty_cell(self):
        match = _CAPITAL_ROW.match("7 Egypt 357,965 641.9 2,937.7 3,579.7 7.07 375.6 266.3")
        self.assertEqual((match.group(1), match.group(2)), ("Egypt", "357,965"))

    def test_2025_capital_row_has_amounts_only_and_uses_the_total_column(self):
        match = _CAPITAL_AMOUNT_ROW.match("Djibouti 3.04 2.46 5.50 0.01% 2.07 0.54 0.42")
        self.assertEqual((match.group(1), match.group(2)), ("Djibouti", "5.50"))
        self.assertIsNone(_CAPITAL_ROW.match("Djibouti 3.04 2.46 5.50 0.01% 2.07 0.54 0.42"))

    def test_voting_row_with_and_without_serial_number_and_percent_sign(self):
        for line in ("Saudi Arabia 1,159,158 22.66%", "1 Saudi Arabia 1,113,493 23.83%", "1 Saudi Arabia 1,108,755 23.85"):
            match = _VOTING_ROW.match(line)
            self.assertIsNotNone(match, msg=line)
            self.assertEqual(match.group(1), "Saudi Arabia")

    def test_voting_row_with_page_label_glued_on(self):
        match = _VOTING_ROW.match("28 Benin 5,951 0.13% 6A-9B")
        self.assertEqual((match.group(1), match.group(2)), ("Benin", "5,951"))

    def test_row_from_an_unrelated_numeric_table_does_not_match(self):
        line = "Egypt 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0"
        for pattern in (_COMBINED_ROW, _COMBINED_ROW_2012, _CAPITAL_ROW, _CAPITAL_AMOUNT_ROW, _VOTING_ROW):
            self.assertIsNone(pattern.match(line))


class GluedDirectorNameTests(unittest.TestCase):
    def test_2019_row_with_director_name_glued_onto_the_front(self):
        line = "Hon. Dr. Hamad Suleiman Al Bazai Saudi Arabia 6 Qatar 363,236 2,979.3 653.0 3,632.4 7.18% 421.8 0.0 231.3"
        self.assertIsNone(_CAPITAL_ROW.match(line))
        match = _CAPITAL_ROW_MID.search(line)
        self.assertEqual((match.group(1), match.group(2)), ("Qatar", "363,236"))

    def test_2019_voting_row_with_sidebar_after_it_and_text_before(self):
        match = _VOTING_ROW_MID.search("Hon. Bulent Aksu 9 Turkey 303,950 6.50%")
        self.assertEqual((match.group(1), match.group(2)), ("Turkey", "303,950"))


class ParseLinesTests(unittest.TestCase):
    def test_capital_and_voting_annexes_merge_by_country_not_by_spelling(self):
        # The same year's two annexes spell this country differently.
        lines = [
            "1 Côte D'Ivoire 1,302 3.6 9.5 13.0 0.03% 2.5 0.2 0.9",
            "2 Chad 977 4.9 4.9 9.8 0.02% 4.7 0.3 0.0",
            "Sub-Total 2,279 8.5 14.4 22.8 100.00% 7.2 0.5 0.9",
            "1 Cote D'Ivoire 1,695 0.04%",
            "2 Chad 1,452 0.03%",
            "Sub-Total 3,147 100.00%",
        ]
        members, unresolved, stated = parse_lines(lines)
        self.assertEqual(unresolved, [])
        self.assertEqual(members["CIV"], {"shares": 1302.0, "votes": 1695.0})
        self.assertEqual(members["TCD"], {"shares": 977.0, "votes": 1452.0})
        self.assertEqual(stated, {"shares": 2279.0, "votes": 3147.0})

    def test_uncommitted_reserve_grand_total_and_shortfall_are_not_members(self):
        lines = [
            "Chad 977 4.9 4.9 9.8 0.02% 4.7 0.3 0.0",
            "Uncommitted 38,875 0.0 388.8 388.8 0.77% * * *",
            "Grand Total 5,061,406 9,371.9 41,242.2 50,614.1 100.00% 5,785.1 182.4 3,404.4",
        ]
        members, unresolved, stated = parse_lines(lines)
        self.assertEqual(list(members), ["TCD"])
        self.assertEqual(unresolved, [])
        self.assertEqual(stated, {"shares": None, "votes": None})

    def test_a_bare_total_row_is_the_stated_votes_total_in_voting_annexes_only(self):
        # 2025's voting annex prints "Total" rather than "Sub-Total".
        members, _, stated = parse_lines(["Chad 1,496 0.03%", "Total 5,707,197 100%"])
        self.assertEqual(stated["votes"], 5707197.0)
        self.assertEqual(list(members), ["TCD"])

    def test_isdb_own_misspellings_resolve(self):
        members, unresolved, _ = parse_lines(["37 Kyrghyz 2,892 0.06", "Kyrgyz 923 0.05%"])
        self.assertEqual(unresolved, [])
        self.assertEqual(list(members), ["KGZ"])

    def test_unresolvable_name_is_reported_not_guessed(self):
        members, unresolved, _ = parse_lines(["Atlantis 1,000 0.50%"])
        self.assertEqual(members, {})
        self.assertEqual(unresolved, ["Atlantis"])


if __name__ == "__main__":
    unittest.main()
