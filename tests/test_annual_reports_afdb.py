"""Offline tests for scripts/annual_reports_afdb.py -- built specifically
around the "extract every candidate, dedupe by name" redesign that replaced
x-position filtering (see the module docstring and docs/coding_decisions.md,
2026-09-24: no fixed x-threshold separated the left (alphabetical) block
from the right (by-constituency) block across every row)."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _reference import iso3_from_name  # noqa: E402
from annual_reports_afdb import _NAME_FIXUPS, _extract_candidates, _is_number  # noqa: E402


def _word(text, x0, top=100.0):
    return {"text": text, "x0": x0, "top": top}


def _resolve(name_raw):
    return iso3_from_name(_NAME_FIXUPS.get(name_raw, name_raw))


class IsNumberTests(unittest.TestCase):
    def test_plain_integer_is_a_number(self):
        self.assertTrue(_is_number("12345"))

    def test_comma_grouped_integer_is_a_number(self):
        self.assertTrue(_is_number("1,234,567"))

    def test_decimal_percentage_is_a_number(self):
        self.assertTrue(_is_number("6.79"))

    def test_bdir_label_is_not_a_number(self):
        self.assertFalse(_is_number("BDIR.1"))

    def test_country_name_is_not_a_number(self):
        self.assertFalse(_is_number("ALGERIA"))


class ExtractCandidatesTests(unittest.TestCase):
    def test_simple_left_block_row_yields_one_candidate(self):
        row = [_word("ALGERIA", 50), _word("12,345", 150), _word("6.79", 200)]
        self.assertEqual(_extract_candidates(row), [("ALGERIA", 6.79)])

    def test_multi_word_name_is_joined(self):
        row = [_word("CENT.AFR.REP", 50), _word("1,000", 150), _word("0.50", 200)]
        self.assertEqual(_extract_candidates(row), [("CENT.AFR.REP", 0.50)])

    def test_bdir_label_skipped_without_crashing_or_looping(self):
        # Confirmed real: "BDIR.1" starts a constituency label mid-row. It
        # must not be swallowed into a name, nor cause an infinite loop.
        row = [
            _word("ALGERIA", 50), _word("12,345", 150), _word("6.79", 200),
            _word("BDIR.1", 240),
            _word("EGYPT", 260), _word("22,222", 350), _word("4.44", 400),
        ]
        self.assertEqual(
            _extract_candidates(row),
            [("ALGERIA", 6.79), ("EGYPT", 4.44)],
        )

    def test_redundant_right_block_on_same_row_is_a_second_candidate(self):
        # The module's whole design point: a row can legitimately carry two
        # (name, pct) pairs -- the left block's own entry, plus a right-side
        # constituency entry for a *different* country landing on the same
        # visual line. Both are extracted; dedup-by-name happens later, in
        # parse_pdf(), not here.
        row = [
            _word("MOROCCO", 50), _word("9,999", 150), _word("3.33", 200),
            _word("TUNISIA", 260), _word("8,888", 350), _word("2.22", 400),
        ]
        self.assertEqual(
            _extract_candidates(row),
            [("MOROCCO", 3.33), ("TUNISIA", 2.22)],
        )

    def test_skip_names_produce_no_candidate(self):
        row = [_word("TOTAL", 50), _word("999,999", 150), _word("100.00", 200)]
        self.assertEqual(_extract_candidates(row), [])

    def test_decimal_first_number_is_rejected_as_not_a_vote_count(self):
        # Vote counts are always integers; if the first number already has
        # a decimal point, this isn't a genuine (votes, pct) pair.
        row = [_word("ALGERIA", 50), _word("6.79", 150), _word("4.44", 200)]
        self.assertEqual(_extract_candidates(row), [])

    def test_row_with_no_trailing_numbers_yields_nothing(self):
        row = [_word("EXECUTIVE", 50), _word("DIRECTOR", 120)]
        self.assertEqual(_extract_candidates(row), [])


class NameFixupResolutionTests(unittest.TestCase):
    def test_abbreviated_names_resolve(self):
        self.assertEqual(_resolve("CENT.AFR.REP"), "CAF")
        self.assertEqual(_resolve("DEM.REP.CONGO"), "COD")
        self.assertEqual(_resolve("EQ.GUINEA"), "GNQ")
        self.assertEqual(_resolve("GUINEA BISSAU"), "GNB")
        self.assertEqual(_resolve("SAO TOME & P."), "STP")

    def test_turkiye_variants_both_resolve(self):
        self.assertEqual(_resolve("TÜRKIYE"), "TUR")
        self.assertEqual(_resolve("TURKIYE"), "TUR")

    def test_bare_abbreviations_resolve(self):
        self.assertEqual(_resolve("KOREA"), "KOR")
        self.assertEqual(_resolve("U.K."), "GBR")
        self.assertEqual(_resolve("U.S.A"), "USA")

    def test_ordinary_name_still_resolves_without_a_fixup(self):
        self.assertEqual(_resolve("NIGERIA"), "NGA")


if __name__ == "__main__":
    unittest.main()
