"""Offline tests for scripts/annual_reports_badea.py."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from annual_reports_badea import _resolve  # noqa: E402


class ResolveTests(unittest.TestCase):
    def test_badea_official_long_forms_resolve(self):
        # Every one of these failed to resolve directly against the shared
        # codelist when first checked against the real table this session --
        # confirmed fixed, not assumed.
        cases = {
            "Hashemite Kingdom of Jordan": "JOR",
            "Kingdom of Bahrain": "BHR",
            "Republic of Tunisia": "TUN",
            "People’s Democratic Republic of Algeria": "DZA",
            "Kingdom of Saudi Arabia": "SAU",
            "State of Palestine": "PSE",
            "Lebanese Republic": "LBN",
            "Arab Republic of Egypt": "EGY",
            "The Islamic Republic of Mauritania": "MRT",
        }
        for name, expected_iso3 in cases.items():
            self.assertEqual(_resolve(name), expected_iso3, name)

    def test_ordinary_name_still_resolves_without_a_fixup(self):
        self.assertEqual(_resolve("United Arab Emirates"), "ARE")


if __name__ == "__main__":
    unittest.main()
