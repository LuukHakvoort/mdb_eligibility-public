"""Offline tests for scripts/annual_reports_idb.py -- real row shapes from IDB's
SEC-filed annual reports, FY2022-FY2025 (docs/coding_decisions.md, 2026-09-24)."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from annual_reports_idb import _is_total, _member_table, cache_name_for, parse_member_row  # noqa: E402


class ParseMemberRowTests(unittest.TestCase):
    def test_member_row(self):
        self.assertEqual(parse_member_row(["Argentina", "1,609,442", "1,609,577", "11.354"]), ("Argentina", 1609442.0, 1609577.0, 11.354))

    def test_blank_spacer_cells_are_ignored(self):
        self.assertEqual(parse_member_row(["", "Bahamas", "", "29,548", "29,683", "", "0.209"])[0], "Bahamas")

    def test_grand_total_row(self):
        row = parse_member_row(["Grand total", "14,170,108", "14,176,588", "100.000"])
        self.assertTrue(_is_total(row[0]))
        self.assertEqual(row[1:3], (14170108.0, 14176588.0))

    def test_group_header_and_column_header_rows_are_not_data(self):
        self.assertIsNone(parse_member_row(["Regional developing members"]))
        self.assertIsNone(parse_member_row(["Member countries", "Subscribed voting shares", "Number of votes", "% of total number of votes (1)"]))

    def test_a_footnote_marker_on_the_name_is_stripped(self):
        self.assertEqual(parse_member_row(["Canada (1)", "100", "235", "0.5"])[0], "Canada")


class MemberTableTests(unittest.TestCase):
    def _table(self, n=30, pct=100 / 30):
        rows = [["Member countries", "shares", "votes", "%"]]
        rows += [[f"Country{i}", "1,000", "1,135", f"{pct:.3f}"] for i in range(n)]
        rows.append(["Grand total", f"{1000 * n:,}", f"{1135 * n:,}", "100.000"])
        return rows

    def test_the_table_whose_percentages_sum_to_100_is_found(self):
        self.assertIsNotNone(_member_table([[["x", "1"]], self._table()]))

    def test_a_lookalike_table_whose_percentages_do_not_sum_to_100_is_rejected(self):
        self.assertIsNone(_member_table([self._table(pct=1.0)]))

    def test_cache_name_is_derived_from_the_url(self):
        url = "https://www.sec.gov/Archives/edgar/data/311670/000119312525036789/d930864dannlrpt.htm"
        self.assertEqual(cache_name_for(url), "sec_311670_000119312525036789_d930864dannlrpt.htm")


if __name__ == "__main__":
    unittest.main()
