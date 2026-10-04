"""Offline tests for scripts/annual_reports_cabei.py."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from annual_reports_cabei import _ROW, _resolve  # noqa: E402


class ResolveTests(unittest.TestCase):
    def test_glued_name_is_fixed(self):
        # Confirmed real: this document renders some names with no space
        # between words ("RepúblicaDominicana"), a PDF-extraction artifact.
        self.assertEqual(_resolve("RepúblicaDominicana"), "DOM")

    def test_extraregional_long_forms_resolve(self):
        self.assertEqual(_resolve("República de China (Taiwán)"), "TWN")
        self.assertEqual(_resolve("República de Corea"), "KOR")
        self.assertEqual(_resolve("España"), "ESP")

    def test_ordinary_name_still_resolves(self):
        self.assertEqual(_resolve("Guatemala"), "GTM")


class RowRegexTests(unittest.TestCase):
    def test_real_row_captures_both_percentages_taking_the_second(self):
        match = _ROW.match(
            "Guatemala 714,000,000 535,500,000 178,500,000 71,400 28,757 100,157 10.20% 10.68%"
        )
        self.assertIsNotNone(match)
        name, pct_authorized, pct_subscribed = match.groups()
        self.assertEqual(name, "Guatemala")
        self.assertEqual(pct_authorized, "10.20")
        self.assertEqual(pct_subscribed, "10.68")  # this is the one the parser keeps


if __name__ == "__main__":
    unittest.main()
