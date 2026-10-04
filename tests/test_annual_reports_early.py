"""Offline tests for the early-year parsers (AfDB 2002-04 plain text, IsDB 1423H-1425H) -- docs/coding_decisions.md, 2026-09-25."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from annual_reports_afdb_early import parse as afdb_parse  # noqa: E402
from annual_reports_isdb_early import parse_appendix  # noqa: E402

AFDB = """Statement of Subscriptions to the Capital Stock and Voting Powers as at
31 December, 2004
   MEMBER STATES        shares   % of    votes   Voting power
 1 ALGERIA                4,493    3,834    3.834    737,600    87,020    83,087    3.806
37 NIG ER                   691    4,835    0.256   48,353     6,908     6,151     0.281
NOTES:
"""


class AfdbEarlyTests(unittest.TestCase):
    def test_row_with_share_and_vote_percentages_is_read_and_a_source_typo_is_mapped(self):
        members = afdb_parse(AFDB)
        self.assertEqual(members["Algeria"]["shares"], 3834)
        self.assertEqual(members["Niger"]["vpct"], 0.281)


class IsdbEarlyTests(unittest.TestCase):
    def test_row_total_and_the_subtotal_that_members_must_reconcile_to(self):
        members, printed = parse_appendix([
            "1 Afghanistan 2.50 - 2.50 - 5.00 0.06",
            "53 U.A.E 110.00 33.72 139.31 278.64 561.67 7.06",
            "Sub total 834.30 1,369.94 1,861.30 3,895.17 7,960.71 100.00",
            "Grand Total 834.30 1,369.94 1,895.76 4,000.00 8,100.00 -",
        ])
        self.assertEqual(members["Afghanistan"], 5.0)
        self.assertEqual(members["United Arab Emirates"], 561.67)
        self.assertEqual(printed, 7960.71)


if __name__ == "__main__":
    unittest.main()
