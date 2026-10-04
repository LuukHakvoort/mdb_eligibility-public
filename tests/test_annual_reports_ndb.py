"""Offline tests for scripts/annual_reports_ndb.py."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from annual_reports_ndb import _PROSPECTIVE_ROW, _ROW  # noqa: E402


class RowRegexTests(unittest.TestCase):
    def test_plain_row_matches(self):
        match = _ROW.match("Brazil 18.76%")
        self.assertIsNotNone(match)
        name, pct = match.groups()
        self.assertEqual(name, "Brazil")
        self.assertEqual(pct, "18.76")

    def test_row_with_trailing_commentary_from_the_two_column_layout_still_matches(self):
        # Confirmed real: the slide's two-column layout interleaves bullet
        # commentary onto some rows' extracted text.
        match = _ROW.match("China 18.76% ❖ Full member support for maintaining a very strong financial profile")
        self.assertIsNotNone(match)
        name, pct = match.groups()
        self.assertEqual(name, "China")
        self.assertEqual(pct, "18.76")

    def test_prospective_member_row_is_recognized_separately(self):
        self.assertIsNotNone(_PROSPECTIVE_ROW.match("Uzbekistan Prospective member2"))
        self.assertIsNone(_ROW.match("Uzbekistan Prospective member2"))


if __name__ == "__main__":
    unittest.main()
