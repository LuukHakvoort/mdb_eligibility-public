"""Offline tests for scripts/build_control_variables.py's ucdp_conflict()/
banking_crisis() sources (2026-09-30, closed rosters within each source's
own coverage window), and scripts/build_other_mdb_lending.py + scripts/
merge_other_mdb_lending.py + scripts/merge_conflict_crisis_lags.py (the
other-MDB-lending instrument and the conflict/crisis _t1 lags).

ucdp_conflict()/banking_crisis() are tested directly against the real,
checked-in source data (same pattern as EuMemberAndWbRegionTests in
test_control_panel.py) -- they're closed-roster sources with deterministic
real answers, and reconstructing a synthetic UCDP/Laeven-Valencia file
would just re-implement the parser being tested. The merge/build scripts
are tested against small synthetic fixtures, since those need precise
control over edge cases (a blank usd_2025_total, an empty pool).
"""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, cwd=REPO,
    )


class UcdpConflictTests(unittest.TestCase):
    """scripts/build_control_variables.py's ucdp_conflict() -- the UCDP/PRIO
    Armed Conflict Dataset v26.1, closed roster 2002-2025 (2026 outside the
    source's own coverage, left blank -- see docs/coding_decisions.md,
    2026-09-30)."""

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        import build_control_variables as bcv
        self.bcv = bcv
        self.df = bcv.ucdp_conflict()
        self.by_key = {(r["iso3"], r["year"]): r for _, r in self.df.iterrows()}

    def test_closed_roster_every_value_is_0_or_1_within_coverage(self):
        self.assertTrue(self.df["ucdp_armed_conflict"].isin([0, 1]).all())
        self.assertTrue(self.df["ucdp_war"].isin([0, 1]).all())

    def test_2026_is_outside_the_sources_own_coverage_and_absent_entirely(self):
        # Not merely blank -- ucdp_conflict()'s own grid doesn't extend past
        # 2025 at all, so a later outer-merge in main() leaves 2026 blank
        # for these columns rather than this function claiming a 0 it can't
        # vouch for.
        self.assertFalse((self.df["year"] == 2026).any())
        self.assertEqual(self.df["year"].max(), 2025)

    def test_a_known_war_year_reads_war_1_and_intensity_2(self):
        row = self.by_key[("SYR", 2015)]  # Syrian civil war, well past the 1,000-death threshold
        self.assertEqual(row["ucdp_armed_conflict"], 1)
        self.assertEqual(row["ucdp_war"], 1)
        self.assertEqual(row["ucdp_conflict_intensity"], 2)

    def test_a_peaceful_country_year_reads_0_not_blank(self):
        row = self.by_key[("NOR", 2015)]
        self.assertEqual(row["ucdp_armed_conflict"], 0)
        self.assertEqual(row["ucdp_war"], 0)

    def test_conflict_intensity_is_blank_not_zero_when_no_conflict(self):
        # 1=minor/2=war isn't a scale with a meaningful zero -- a country-
        # year with no conflict at all must read blank here, unlike the two
        # binary flags which are a genuine 0.
        row = self.by_key[("NOR", 2015)]
        import pandas as pd
        self.assertTrue(pd.isna(row["ucdp_conflict_intensity"]))

    def test_an_interstate_conflict_credits_every_listed_country(self):
        # India-Pakistan (conflict_id 218 in the real file) is interstate --
        # per the user's own confirmed choice (2026-09-30), both listed
        # countries are credited, not just one or neither.
        self.assertEqual(self.by_key[("IND", 2014)]["ucdp_armed_conflict"], 1)
        self.assertEqual(self.by_key[("PAK", 2014)]["ucdp_armed_conflict"], 1)

    def test_no_unresolved_ucdp_location_names(self):
        # A real assertion, not just a report -- every location in the
        # actual v26.1 file is expected to resolve with the fixups already
        # in place (empirically verified, 2026-09-30); a regression here
        # means a new unresolved name needs a fixup, not a silent drop.
        report = REPO / "data" / "output" / "reports" / "ucdp_unresolved.csv"
        if report.is_file():
            self.assertEqual(read_rows(report), [], "unexpected unresolved UCDP location(s) -- see the report")


class BankingCrisisTests(unittest.TestCase):
    """scripts/build_control_variables.py's banking_crisis() -- Laeven &
    Valencia's Systemic Banking Crises Database 2026, closed roster
    2002-2025 (2026 outside the source's own coverage, left blank)."""

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        import build_control_variables as bcv
        self.bcv = bcv
        self.df = bcv.banking_crisis()
        self.by_key = {(r["iso3"], r["year"]): r["banking_crisis"] for _, r in self.df.iterrows()}

    def test_closed_roster_every_value_is_0_or_1_within_coverage(self):
        self.assertTrue(self.df["banking_crisis"].isin([0, 1]).all())

    def test_2026_is_outside_the_sources_own_coverage_and_absent_entirely(self):
        self.assertFalse((self.df["year"] == 2026).any())
        self.assertEqual(self.df["year"].max(), 2025)

    def test_the_2008_global_financial_crisis_reads_1_for_the_us(self):
        self.assertEqual(self.by_key[("USA", 2007)], 1)
        self.assertEqual(self.by_key[("USA", 2008)], 1)
        self.assertEqual(self.by_key[("USA", 2009)], 1)
        self.assertEqual(self.by_key[("USA", 2013)], 0)  # well after the crisis's own End year

    def test_argentinas_2001_2002_crisis_reads_1_only_in_its_own_span(self):
        self.assertEqual(self.by_key[("ARG", 2002)], 1)
        self.assertEqual(self.by_key[("ARG", 2003)], 1)
        self.assertEqual(self.by_key[("ARG", 2004)], 0)

    def test_a_country_with_no_listed_crisis_reads_0_not_blank(self):
        self.assertEqual(self.by_key[("KEN", 2010)], 0)

    def test_footnote_suffixes_and_whitespace_are_cleaned_from_country_names(self):
        self.assertEqual(self.bcv._clean_banking_crisis_token("Argentina 5/"), "Argentina")
        self.assertEqual(self.bcv._clean_banking_crisis_token("Azerbaijan "), "Azerbaijan")

    def test_no_unresolved_banking_crisis_country_names(self):
        report = REPO / "data" / "output" / "reports" / "banking_crises_unresolved.csv"
        if report.is_file():
            self.assertEqual(read_rows(report), [], "unexpected unresolved banking-crisis name(s) -- see the report")


PANEL_FIELDS = ["bank", "iso3", "year", "usd_2025_total", "ppp_2025_total"]


class BuildOtherMdbLendingTests(unittest.TestCase):
    def test_available_fills_missing_component_but_strict_stays_blank(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            panel = write_csv(path / "panel.csv", PANEL_FIELDS, [
                {"bank": "IBRD", "iso3": "KEN", "year": "2015", "usd_2025_total": "1000000", "ppp_2025_total": "2000000"},
                {"bank": "IDA", "iso3": "KEN", "year": "2015", "usd_2025_total": "500000", "ppp_2025_total": "900000"},
                {"bank": "AfDB", "iso3": "KEN", "year": "2015", "usd_2025_total": "", "ppp_2025_total": ""},  # a genuine data gap
            ])
            output = path / "other_mdb.csv"
            result = run("build_other_mdb_lending.py", "--panel", str(panel), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {r["bank"]: r for r in read_rows(output)}

            # IBRD's pool is {IDA=500000, AfDB=blank}.
            self.assertEqual(rows["IBRD"]["other_mdb_usd_available"], "500000.0")  # blank treated as 0
            self.assertEqual(rows["IBRD"]["other_mdb_usd_strict"], "")            # a real gap, stays blank
            self.assertEqual(rows["IBRD"]["other_mdb_n_eligible"], "2")
            self.assertEqual(rows["IBRD"]["other_mdb_n_missing_amount"], "1")

            # AfDB's own pool is {IBRD=1000000, IDA=500000} -- no gap, both totals agree.
            self.assertEqual(rows["AfDB"]["other_mdb_usd_available"], "1500000.0")
            self.assertEqual(rows["AfDB"]["other_mdb_usd_strict"], "1500000.0")
            self.assertEqual(rows["AfDB"]["other_mdb_n_missing_amount"], "0")

            # PPP version (2026-10-04), same pool and same rules.
            self.assertEqual(rows["IBRD"]["other_mdb_ppp_available"], "900000.0")  # IDA's 900000; AfDB blank -> 0
            self.assertEqual(rows["IBRD"]["other_mdb_ppp_strict"], "")             # AfDB PPP is a gap
            self.assertEqual(rows["IBRD"]["other_mdb_ppp_n_missing_amount"], "1")
            self.assertEqual(rows["AfDB"]["other_mdb_ppp_available"], "2900000.0")
            self.assertEqual(rows["AfDB"]["other_mdb_ppp_strict"], "2900000.0")
            self.assertEqual(rows["AfDB"]["other_mdb_ppp_n_missing_amount"], "0")

    def test_an_empty_pool_is_a_real_zero_not_blank(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            panel = write_csv(path / "panel.csv", PANEL_FIELDS, [
                {"bank": "AIIB", "iso3": "MNG", "year": "2018", "usd_2025_total": "200000", "ppp_2025_total": "350000"},
            ])
            output = path / "other_mdb.csv"
            result = run("build_other_mdb_lending.py", "--panel", str(panel), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            row = read_rows(output)[0]
            self.assertEqual(row["other_mdb_n_eligible"], "0")
            self.assertEqual(row["other_mdb_usd_available"], "0.0")
            self.assertEqual(row["other_mdb_usd_strict"], "0.0")  # empty pool, nothing can be "missing"
            self.assertEqual(row["other_mdb_ppp_available"], "0.0")
            self.assertEqual(row["other_mdb_ppp_strict"], "0.0")
            self.assertEqual(row["other_mdb_ppp_n_missing_amount"], "0")


OTHER_MDB_FIELDS = ["bank", "iso3", "year", "other_mdb_usd_available", "other_mdb_usd_strict",
                     "other_mdb_n_eligible", "other_mdb_n_missing_amount",
                     "other_mdb_ppp_available", "other_mdb_ppp_strict", "other_mdb_ppp_n_missing_amount"]


class MergeOtherMdbLendingTests(unittest.TestCase):
    def test_row_count_invariant_and_t1_is_the_prior_years_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            panel = write_csv(path / "panel.csv", ["bank", "iso3", "year"], [
                {"bank": "IBRD", "iso3": "KEN", "year": "2015"},
                {"bank": "IBRD", "iso3": "KEN", "year": "2016"},
            ])
            other_mdb = write_csv(path / "other_mdb.csv", OTHER_MDB_FIELDS, [
                {"bank": "IBRD", "iso3": "KEN", "year": "2015", "other_mdb_usd_available": "900000",
                 "other_mdb_usd_strict": "900000", "other_mdb_n_eligible": "1", "other_mdb_n_missing_amount": "0",
                 "other_mdb_ppp_available": "1800000", "other_mdb_ppp_strict": "1800000",
                 "other_mdb_ppp_n_missing_amount": "0"},
            ])
            output = path / "merged.csv"
            result = run("merge_other_mdb_lending.py", "--panel", str(panel), "--other-mdb", str(other_mdb),
                         "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {r["year"]: r for r in read_rows(output)}
            self.assertEqual(len(rows), 2)
            # 2016's t1 picks up 2015's value; 2015 itself has no prior year in the fixture -- blank.
            self.assertEqual(rows["2016"]["other_mdb_usd_t1"], "900000.0")
            self.assertEqual(rows["2016"]["other_mdb_usd_millions_t1"], "0.9")
            self.assertEqual(rows["2015"]["other_mdb_usd_t1"], "")
            # PPP t1 (2026-10-04): same lag, PPP total.
            self.assertEqual(rows["2016"]["other_mdb_ppp_t1"], "1800000.0")
            self.assertEqual(rows["2016"]["other_mdb_ppp_millions_t1"], "1.8")
            self.assertEqual(rows["2015"]["other_mdb_ppp_t1"], "")


CONTROLS_FIELDS = ["iso3", "year", "ucdp_armed_conflict", "ucdp_war", "ucdp_conflict_intensity", "banking_crisis"]


class MergeConflictCrisisLagsTests(unittest.TestCase):
    def test_row_count_invariant_and_t1_is_the_prior_years_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            panel = write_csv(path / "panel.csv", ["bank", "iso3", "year"], [
                {"bank": "IBRD", "iso3": "SYR", "year": "2015"},
                {"bank": "IBRD", "iso3": "SYR", "year": "2016"},
            ])
            controls = write_csv(path / "controls.csv", CONTROLS_FIELDS, [
                {"iso3": "SYR", "year": "2015", "ucdp_armed_conflict": "1", "ucdp_war": "1",
                 "ucdp_conflict_intensity": "2", "banking_crisis": "0"},
            ])
            output = path / "merged.csv"
            result = run("merge_conflict_crisis_lags.py", "--panel", str(panel), "--controls", str(controls),
                         "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {r["year"]: r for r in read_rows(output)}
            self.assertEqual(len(rows), 2)
            # A single-row-without-other-NaN fixture can serialize a whole-
            # number column as "1.0" rather than "1" (pandas' own float64
            # upcast when any NaN is present elsewhere in the column) --
            # compare numerically, not by exact string, same convention as
            # this project's other lag-merge tests (e.g. test_unga_iv.py).
            self.assertEqual(float(rows["2016"]["ucdp_war_t1"]), 1.0)
            self.assertEqual(float(rows["2016"]["ucdp_conflict_intensity_t1"]), 2.0)
            # 2015 has no prior-year row in this tiny fixture -- blank, never guessed/carried.
            self.assertEqual(rows["2015"]["ucdp_war_t1"], "")


if __name__ == "__main__":
    unittest.main()
