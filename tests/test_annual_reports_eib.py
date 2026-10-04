"""Offline tests for scripts/annual_reports_eib.py's fallbacks for the years whose
text layers are awkward (docs/coding_decisions.md, 2026-09-25)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from annual_reports_eib import _read_table_text, _split_by_identity  # noqa: E402


class IdentitySplitTests(unittest.TestCase):
    def test_2003_row_with_lost_spacing_splits_where_subscribed_is_uncalled_plus_paid_in(self):
        self.assertEqual(_split_by_identity("2664953250025316065017" + "1333467483"), 26649532500)

    def test_ambiguous_or_impossible_runs_return_none(self):
        self.assertIsNone(_split_by_identity("123456789"))


class TextTableTests(unittest.TestCase):
    def test_rows_and_unlabelled_total_from_2003_style_text(self):
        text = "Germany 26 649532 500 25 316 065 0171 3 33 467 483\n150 000 000 000 142 500 000 000 7 500 000 000"
        rows, total = _read_table_text(text)
        self.assertEqual(rows, [("Germany", 26649532500.0)])
        self.assertEqual(total, 150000000000.0)


if __name__ == "__main__":
    unittest.main()
