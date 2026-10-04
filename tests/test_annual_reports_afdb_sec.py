"""Offline tests for scripts/annual_reports_afdb_sec.py -- real row shapes from
AfDB's SEC-filed annual reports, statement years 2005-2025 (docs/
coding_decisions.md, 2026-09-24)."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _reference import iso3_from_name  # noqa: E402
from annual_reports_afdb_sec import (  # noqa: E402
    _NAME_FIXUPS,
    _is_total,
    _member_tables,
    cache_name_for,
    parse_member_row,
    statement_year,
)


class ParseMemberRowTests(unittest.TestCase):
    def test_serial_number_in_its_own_cell(self):
        row = ["1", "ALGERIA", "86,566", "3.979", "94,584", "771,080", "87,191", "3.924"]
        self.assertEqual(parse_member_row(row), ("ALGERIA", [86566.0, 3.979, 94584.0, 771080.0, 87191.0, 3.924]))

    def test_serial_number_glued_onto_the_name(self):
        row = ["1 Algeria", "773,155", "4.800", "389,853", "7,341,680", "773,780", "5.301"]
        self.assertEqual(parse_member_row(row)[0], "Algeria")

    def test_blank_spacer_cells_are_ignored(self):
        row = ["", "1", "", "Algeria", "", "773,155", "4.800", "", "389,853", "7,341,680", "773,780", "5.301"]
        self.assertEqual(parse_member_row(row)[0], "Algeria")

    def test_header_and_page_number_rows_are_not_data(self):
        self.assertIsNone(parse_member_row(["Member States", "Total Shares", "% of Total Shares", "Amount Paid"]))
        self.assertIsNone(parse_member_row(["131"]))

    def test_a_loans_table_row_has_the_wrong_number_of_numeric_columns(self):
        # "Country | Number of loans | Total loans | Unsigned | Undisbursed | Outstanding | %" -- 6 numbers, but
        # confirm the percentage-sum check in _member_tables is what tells it apart, not this row shape alone.
        row = ["Algeria", "1", "549,880", "—", "—", "549,880", "2.27"]
        self.assertIsNone(parse_member_row(row))

    def test_grand_total_and_plain_total_are_both_totals(self):
        self.assertTrue(_is_total("Grand total"))
        self.assertTrue(_is_total("TOTAL"))
        self.assertFalse(_is_total("Total regionals"))
        self.assertFalse(_is_total("Total non-regionals"))


class MemberTablesTests(unittest.TestCase):
    def _member_table(self, n=40, pct_shares=2.5, pct_votes=2.5):
        rows = [["Member States", "Total Shares", "% of Total Shares", "Amount Paid", "Callable Capital", "Number of Votes", "% of Total Voting Power"]]
        for i in range(n):
            rows.append([str(i + 1), f"Country{i}", "1,000", str(pct_shares), "10", "20", "1,100", str(pct_votes)])
        rows.append(["", "TOTAL", f"{1000 * n:,}", "100.000", "1", "1", f"{1100 * n:,}", "100.000"])
        return rows

    def test_a_table_whose_two_percentage_columns_sum_to_100_is_the_member_statement(self):
        tables = [[["Country", "loans"], ["x", "1"]], self._member_table()]
        self.assertEqual(len(_member_tables(tables)), 1)

    def test_a_similar_looking_table_with_one_percentage_column_is_rejected(self):
        tables = [self._member_table(pct_shares=0.5)]
        self.assertEqual(_member_tables(tables), [])

    def test_a_page_number_only_table_between_two_pages_is_skipped_over(self):
        first = self._member_table(n=30, pct_shares=2.0, pct_votes=2.0)[:-1]  # no total on page 1
        second = [["Member States", "Total Shares"]] + [[str(i), f"Other{i}", "1,000", "2.0", "10", "20", "1,100", "2.0"] for i in range(20)]
        second.append(["", "TOTAL", "1", "100", "1", "1", "1", "100"])
        collected = _member_tables([first, [["131"]], second])
        self.assertEqual(len(collected), 2)


class StatementYearAndNameTests(unittest.TestCase):
    def test_year_comes_from_the_documents_own_sentence(self):
        text = "A list of the members at 31 December 2009 showing each member&#146;s voting power and the amount"
        self.assertEqual(statement_year(text), 2009)

    def test_missing_space_in_31december(self):
        self.assertEqual(statement_year("A list of the members at 31December 2005 showing each member"), 2005)

    def test_as_at_wording(self):
        self.assertEqual(statement_year("A list of the members as at 31 December 2024 showing each member"), 2024)

    def test_no_sentence_means_no_year_rather_than_a_guess(self):
        self.assertIsNone(statement_year("Nothing about members here."))

    def test_fixups_resolve(self):
        for raw, fixed in _NAME_FIXUPS.items():
            self.assertTrue(iso3_from_name(fixed), msg=raw)
        self.assertEqual(iso3_from_name(_NAME_FIXUPS["U.S.A."]), "USA")
        self.assertEqual(iso3_from_name(_NAME_FIXUPS["U.K."]), "GBR")
        self.assertEqual(iso3_from_name(_NAME_FIXUPS["KOREA"]), "KOR")

    def test_cache_name_is_derived_from_the_url(self):
        url = "https://www.sec.gov/Archives/edgar/data/785677/000120864625000028/c200198.htm"
        self.assertEqual(cache_name_for(url), "sec_785677_000120864625000028_c200198.htm")


if __name__ == "__main__":
    unittest.main()
