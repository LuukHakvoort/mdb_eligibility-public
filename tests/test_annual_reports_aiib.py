"""Offline tests for scripts/annual_reports_aiib.py -- real line shapes from
AIIB's 2019-2024 financial-statement notes and 2022-2024 voting-power
appendices (docs/coding_decisions.md, 2026-09-24)."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from annual_reports_aiib import (  # noqa: E402
    _CAPITAL_ROW,
    _clean_ocr_line,
    _iso3,
    _rejoin_wrapped_names,
    compute_voting,
    parse_capital_lines,
    parse_voting_lines,
    parse_voting_lines_2022,
)


class CapitalRowTests(unittest.TestCase):
    def test_four_column_row(self):
        match = _CAPITAL_ROW.match("Australia 36,912 3,691,200 2,953,000 738,200")
        self.assertEqual((match.group(1), match.group(3)), ("Australia", "3,691,200"))

    def test_2019_row_with_two_extra_paid_in_columns_and_a_dash(self):
        match = _CAPITAL_ROW.match("Australia 36,912 3,691,200 2,953,000 738,200 738,200 -")
        self.assertEqual((match.group(1), match.group(3)), ("Australia", "3,691,200"))

    def test_header_line_does_not_match(self):
        self.assertIsNone(_CAPITAL_ROW.match("Members Total shares Subscribed capital Callable capital Paid-in capital"))


class WrappedNameTests(unittest.TestCase):
    def test_2019_wrapped_names_are_rejoined(self):
        lines = ["Brunei", "Darussalam 524 52,400 41,900 10,500 10,500 -", "Hong Kong,", "China 7,651 765,100 612,100 153,000 91,800 61,200"]
        self.assertEqual(_rejoin_wrapped_names(lines), [
            "Brunei Darussalam 524 52,400 41,900 10,500 10,500 -",
            "Hong Kong, China 7,651 765,100 612,100 153,000 91,800 61,200",
        ])

    def test_digit_free_column_header_lines_are_not_joined_onto_the_first_row(self):
        lines = ["Total Subscribed Callable Paid-in capital not yet", "Members shares capital capital capital received received", "Afghanistan 866 86,600 69,300 17,300 6,920 10,380"]
        self.assertEqual(_rejoin_wrapped_names(lines)[-1], "Afghanistan 866 86,600 69,300 17,300 6,920 10,380")

    def test_parse_capital_lines_reads_members_and_the_printed_total(self):
        lines = ["Afghanistan 866 86,600 69,300 17,300", "Algeria 50 5,000 4,000 1,000", "Total 916 91,600 73,300 18,300"]
        members, _, stated = parse_capital_lines(lines)
        self.assertEqual(members, {"Afghanistan": 86600.0, "Algeria": 5000.0})
        self.assertEqual(stated, 91600.0)


class OcrCleaningTests(unittest.TestCase):
    def test_gridline_characters_at_the_ends_of_a_line_are_stripped(self):
        self.assertEqual(_clean_ocr_line("| Cambodia 623 62,300 49,800 12,500 |"), "Cambodia 623 62,300 49,800 12,500")

    def test_a_lone_dot_between_numbers_is_dropped(self):
        self.assertEqual(_clean_ocr_line("Qatar 6,044 604,400 483,500 120,900 48,360 . 72,540"),
                         "Qatar 6,044 604,400 483,500 120,900 48,360 72,540")

    def test_a_dash_before_a_number_is_a_gridline_but_a_trailing_dash_is_a_real_zero(self):
        self.assertEqual(_clean_ocr_line("Nepal 809 80,900 64,700 16,200 - 3,240 12,960"),
                         "Nepal 809 80,900 64,700 16,200 3,240 12,960")
        self.assertEqual(_clean_ocr_line("Australia 36,912 3,691,200 2,953,000 738,200 738,200 -"),
                         "Australia 36,912 3,691,200 2,953,000 738,200 738,200 -")


class OcrRowVerificationTests(unittest.TestCase):
    def test_a_misread_in_an_unused_column_does_not_reject_the_row(self):
        # Real OCR misread, 2016: Turkey's paid-in "622,000" for 522,000. Subscribed
        # capital still agrees with shares x 100, so it is verified and kept.
        members, inconsistent, _ = parse_capital_lines(["Turkey 26,099 2,609,900 2,087,900 622,000 208,800 313,200"])
        self.assertEqual(members, {"Turkey": 2609900.0})
        self.assertEqual(inconsistent, [])

    def test_a_misread_share_count_is_rescued_by_callable_plus_paid_in(self):
        # Real OCR misread, 2018: Maldives' share count "2" for 72.
        members, inconsistent, _ = parse_capital_lines(["Maldives 2 7,200 5,800 1,400 560 840"])
        self.assertEqual(members, {"Maldives": 7200.0})
        self.assertEqual(inconsistent, [])

    def test_a_misread_in_the_subscribed_cell_itself_is_rejected(self):
        # Subscribed capital wrong: neither shares x 100 nor callable + paid-in agrees.
        _, inconsistent, _ = parse_capital_lines(["Maldives 72 8,200 5,800 1,400 280 1,120"])
        self.assertEqual(inconsistent, ["Maldives"])

    def test_2017s_own_spelling_of_hong_kong_resolves(self):
        self.assertEqual(_iso3("Hong Kong, SAR"), "HKG")


class VotingRowTests(unittest.TestCase):
    def test_2023_single_column_row_with_founding_votes(self):
        members = parse_voting_lines(["2 Australia 3,691.2 3.8043% 36,912 600 1,425 38,937 3.4504%"])
        self.assertEqual(members["Australia"]["founding"], True)
        self.assertEqual(members["Australia"]["voting_pct"], 3.4504)

    def test_dash_means_not_a_founding_member(self):
        members = parse_voting_lines(["1 Afghanistan 86.6 0.0893% 520 - 1,425 1,945 0.1724%"])
        self.assertEqual(members["Afghanistan"]["founding"], False)

    def test_2024_two_members_per_line_are_both_read(self):
        line = "1 Afghanistan 86.6 0.0892% 520 - 1,382 1,902 0.1685% 40 Tajikistan 30.9 0.0318% 278 600 1,382 2,260 0.2003%"
        members = parse_voting_lines([line])
        self.assertEqual(sorted(members), ["Afghanistan", "Tajikistan"])

    def test_name_with_a_comma_and_an_apostrophe(self):
        members = parse_voting_lines(["13 Hong Kong, China 765.1 0.7885% 7,651 - 1,382 9,033 0.8004%", "58 Côte d'Ivoire 5.0 0.0052% 41 - 1,382 1,423 0.1261%"])
        self.assertIn("Hong Kong, China", members)
        self.assertIn("Côte d'Ivoire", members)

    def test_totals_rows_are_not_members(self):
        self.assertEqual(parse_voting_lines(["Total Regional 73,887.0 76.1425% 730,444 21,600 66,336 818,380 72.5195%"]), {})

    def test_2022_row_has_a_membership_date_and_only_a_percentage(self):
        members = parse_voting_lines_2022(["1 Afghanistan Oct. 13, 2017 0.1765%", "13 Hong Kong, China June 7, 2017 0.8087%"])
        self.assertEqual(members["Afghanistan"], {"membership_date": "Oct. 13, 2017", "voting_pct": 0.1765})
        self.assertEqual(members["Hong Kong, China"]["voting_pct"], 0.8087)


class NameTests(unittest.TestCase):
    def test_bare_korea_is_the_republic_of_korea(self):
        self.assertEqual(_iso3("Korea"), "KOR")

    def test_aiib_spellings_resolve(self):
        self.assertEqual(_iso3("UAE"), "ARE")
        self.assertEqual(_iso3("Vietnam"), "VNM")
        self.assertEqual(_iso3("Brunei Darussalam"), "BRN")


class ComputeVotingTests(unittest.TestCase):
    def test_article_28_formula_on_a_two_member_bank(self):
        # A: 1,000,000k USD = 10,000 shares; B: 3,000,000k = 30,000 shares; both founders.
        result = compute_voting({"A": 1_000_000.0, "B": 3_000_000.0}, {"A", "B"})
        self.assertAlmostEqual(sum(result.values()), 100.0)
        # basic votes = 12/88 of (share + founding) = 5,618.18, split equally.
        self.assertAlmostEqual(result["A"], (10_000 + 600 + 2_809.0909) / 46_818.1818 * 100, places=3)

    def test_non_founder_gets_no_founding_votes_and_everyone_gets_equal_basic_votes(self):
        with_founding = compute_voting({"A": 1_000_000.0, "B": 1_000_000.0}, {"A"})
        self.assertGreater(with_founding["A"], with_founding["B"])  # only the 600 founding votes differ

    def test_voting_share_of_a_large_holder_is_below_its_capital_share(self):
        # The point of Article 28's basic votes: small members punch above their capital weight.
        result = compute_voting({"BIG": 9_000_000.0, "SMALL": 1_000_000.0}, set())
        self.assertLess(result["BIG"], 90.0)
        self.assertGreater(result["SMALL"], 10.0)


if __name__ == "__main__":
    unittest.main()
