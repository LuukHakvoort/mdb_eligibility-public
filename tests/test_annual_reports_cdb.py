"""Offline tests for scripts/annual_reports_cdb.py's line parser, exercised
against real lines from CDB's own FY2019 and FY2024 financial statements
(this session, docs/coding_decisions.md -- the CDB pilot)."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from annual_reports_cdb import _clean_name, _parse_row, _split_into_table_instances  # noqa: E402


class ParseRowTests(unittest.TestCase):
    def test_full_row_both_percentages(self):
        name, capital_pct, voting_pct = _parse_row(
            "Jamaica 48,354 17.31 $291,659 $227,614 $64,045 $64,045 48,504 17.14 -"
        )
        self.assertEqual(name, "Jamaica")
        self.assertEqual(capital_pct, 17.31)
        self.assertEqual(voting_pct, 17.14)

    def test_uk_territory_bloc_row_has_no_voting_percentage(self):
        # Confirmed real: the five UK-territory rows are "considered a single
        # member... for the purpose of Articles 26 and 32" and most don't
        # carry an individual voting-power percentage on their own line.
        name, capital_pct, voting_pct = _parse_row("Anguilla1/ 455 0.16 2,744 2,141 603 603 -")
        self.assertEqual(name, "Anguilla")
        self.assertEqual(capital_pct, 0.16)
        self.assertIsNone(voting_pct)

    def test_section_header_and_subtotal_lines_are_skipped(self):
        self.assertIsNone(_parse_row("Regional States and Territories:"))
        self.assertIsNone(_parse_row("180,627 64.65 $1,089,494 $850,273 $239,221 $239,221 183,477 64.84 5,226"))
        self.assertIsNone(_parse_row("Sub-total 279,399 100.00 $1,685,261 $1,315,217 $370,044 370,044 282,999 100.00 5,226"))

    def test_non_data_line_with_no_numbers_is_skipped(self):
        self.assertIsNone(_parse_row("CARIBBEAN DEVELOPMENT BANK"))
        self.assertIsNone(_parse_row(""))


class CleanNameTests(unittest.TestCase):
    def test_footnote_marker_variants_both_stripped(self):
        # The footnote marker's position varies by year -- confirmed real:
        # "Anguilla1/" (2024) vs. "Anguilla /1" (2019).
        self.assertEqual(_clean_name("Anguilla1/"), "Anguilla")
        self.assertEqual(_clean_name("Anguilla /1"), "Anguilla")

    def test_name_fixups_match_the_codelist(self):
        self.assertEqual(_clean_name("St. Lucia"), "Saint Lucia")
        self.assertEqual(_clean_name("St. Vincent and the Grenadines"), "Saint Vincent and the Grenadines")
        self.assertEqual(_clean_name("St. Kitts and Nevis"), "Saint Kitts and Nevis")

    def test_ordinary_name_is_unchanged(self):
        self.assertEqual(_clean_name("Jamaica"), "Jamaica")


class SplitIntoTableInstancesTests(unittest.TestCase):
    def test_splits_on_bare_year_labels(self):
        # Confirmed real: CDB's own financial-statement PDFs repeat the whole
        # table twice per document -- current year and the comparative prior
        # year, each introduced by a bare year label on its own line.
        pages = ["2024\nJamaica 1 17.31 2 3 4 5 6 17.14 -\n"
                 "2023\nJamaica 1 17.00 2 3 4 5 6 16.90 -\n"]
        instances = _split_into_table_instances(pages)
        years = [year for year, _ in instances]
        self.assertEqual(years, [2024, 2023])

    def test_leading_lines_before_any_year_label_have_no_year(self):
        # No year label yet -- correctly unattributable (None), not guessed.
        # parse_pdf() is what actually discards these (`if year is None: continue`).
        instances = _split_into_table_instances(["unlabeled header line\n"])
        self.assertEqual(instances, [(None, ["unlabeled header line"])])


if __name__ == "__main__":
    unittest.main()
