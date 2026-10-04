"""Offline tests for scripts/build_afdb_window_breakdown.py's funding_window
categorization rule -- unchanged from the retired build_afdb_adf_split.py
(confirmed directly with the user 2026-09-24), now producing ordinary/
concessional sub-total columns on one AfDB row instead of two bank codes.
See docs/coding_decisions.md, 2026-09-28."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_afdb_window_breakdown import _windows_for  # noqa: E402


class WindowsForTests(unittest.TestCase):
    def test_pure_afdb(self):
        self.assertEqual(_windows_for("African Development Bank"), ["ordinary"])

    def test_pure_adf(self):
        self.assertEqual(_windows_for("African Development Fund"), ["concessional"])

    def test_blended_counts_toward_both(self):
        self.assertEqual(
            sorted(_windows_for("African Development Bank; African Development Fund")),
            sorted(["ordinary", "concessional"]),
        )

    def test_adf_with_co_listed_fund_is_concessional(self):
        self.assertEqual(_windows_for("African Development Fund; Transition Support Facility"), ["concessional"])

    def test_afdb_with_co_listed_fund_is_ordinary(self):
        self.assertEqual(
            _windows_for("Africa Growing Together Fund; African Development Bank"), ["ordinary"],
        )

    def test_standalone_special_fund_is_ordinary(self):
        # AfDB-administered trust funds with external co-financiers (Denmark,
        # the US, Germany, the Nordic Development Fund, etc.), not part of
        # ADF's own capital structure -- confirmed directly by the user.
        for fund in ("Transition Support Facility", "Congo Basin Forest Fund",
                     "AfricaWater Facility Fund", "Sustainable Energy Fund for Africa",
                     "Nigerian Trust Fund"):
            self.assertEqual(_windows_for(fund), ["ordinary"], fund)

    def test_blank_is_unresolved(self):
        self.assertEqual(_windows_for(""), [])


if __name__ == "__main__":
    unittest.main()
