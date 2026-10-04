"""Offline tests for scripts/build_project_breakdown.py and scripts/
merge_control_panel.py -- the sector/instrument/sovereign pivot and the
control-variable/project-breakdown merge onto data/output/mdb_panel.csv.
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


PROJECT_FIELDS = ["bank_id", "country_code", "approval_year", "sector_category",
                  "instrument_category", "loan_type", "usd_constant_2025"]


class BuildProjectBreakdownTests(unittest.TestCase):
    def test_pivots_sector_instrument_and_sovereign_counts_and_amounts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            projects = write_csv(path / "all_projects.csv", PROJECT_FIELDS, [
                {"bank_id": "ibrd", "country_code": "KEN", "approval_year": "2015",
                 "sector_category": "Transport & Storage", "instrument_category": "loan",
                 "loan_type": "Sovereign", "usd_constant_2025": "1000000"},
                {"bank_id": "ibrd", "country_code": "KEN", "approval_year": "2015",
                 "sector_category": "Transport & Storage", "instrument_category": "grant",
                 "loan_type": "Non-sovereign", "usd_constant_2025": "500000"},
                {"bank_id": "ibrd", "country_code": "KEN", "approval_year": "2015",
                 "sector_category": "", "instrument_category": "", "loan_type": "",
                 "usd_constant_2025": "0"},
            ])
            output = path / "project_breakdown.csv"
            result = run("build_project_breakdown.py", "--all-projects", str(projects), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(output)}
            row = rows[("IBRD", "KEN", "2015")]
            self.assertEqual(row["sector_transport___storage_n"], "2")
            self.assertEqual(row["sector_unspecified_n"], "1")
            self.assertEqual(row["instrument_loan_n"], "1")
            self.assertEqual(row["instrument_loan_usd"], "1000000.0")
            self.assertEqual(row["instrument_grant_n"], "1")
            self.assertEqual(row["sovereign_n"], "1")
            self.assertEqual(row["sovereign_usd"], "1000000.0")
            self.assertEqual(row["non_sovereign_n"], "1")
            self.assertEqual(row["unknown_n"], "1")

    def test_afdb_projects_are_attributed_like_any_other_bank(self):
        # AfDB and ADF were briefly two separate bank codes (2026-09-24 -
        # 2026-09-28); merged back, so AfDB's projects now flow through this
        # pivot directly, no more skip -- see the module's own docstring.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            projects = write_csv(path / "all_projects.csv", PROJECT_FIELDS, [
                {"bank_id": "afdb", "country_code": "KEN", "approval_year": "2015",
                 "sector_category": "Agriculture", "instrument_category": "loan",
                 "loan_type": "Sovereign", "usd_constant_2025": "1000000"},
            ])
            output = path / "project_breakdown.csv"
            result = run("build_project_breakdown.py", "--all-projects", str(projects), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(output)}
            row = rows[("AfDB", "KEN", "2015")]
            self.assertEqual(row["sector_agriculture_n"], "1")
            self.assertEqual(row["sovereign_n"], "1")
            self.assertEqual(row["sovereign_usd"], "1000000.0")


PANEL_FIELDS = ["bank", "iso3", "year", "eligibility_basis", "any_lending", "note"]
CONTROL_FIELDS = ["iso3", "year", "wdi_ny_gdp_mktp_pp_cd"]
BREAKDOWN_FIELDS = ["bank", "iso3", "year", "sector_agriculture_n", "sovereign_n", "sovereign_usd"]


class MergeControlPanelTests(unittest.TestCase):
    def test_row_count_never_changes_and_controls_broadcast_by_country_year(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            panel = write_csv(path / "panel.csv", PANEL_FIELDS, [
                {"bank": "IBRD", "iso3": "KEN", "year": "2015", "eligibility_basis": "rule", "any_lending": "1", "note": ""},
                {"bank": "IDA", "iso3": "KEN", "year": "2015", "eligibility_basis": "rule", "any_lending": "0", "note": ""},
            ])
            controls = write_csv(path / "controls.csv", CONTROL_FIELDS, [
                {"iso3": "KEN", "year": "2015", "wdi_ny_gdp_mktp_pp_cd": "70000000000"},
            ])
            breakdown = write_csv(path / "breakdown.csv", BREAKDOWN_FIELDS, [
                {"bank": "IBRD", "iso3": "KEN", "year": "2015", "sector_agriculture_n": "2",
                 "sovereign_n": "2", "sovereign_usd": "3000000"},
            ])
            output = path / "merged.csv"
            result = run("merge_control_panel.py", "--panel", str(panel), "--controls", str(controls),
                         "--breakdown", str(breakdown), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(output)}
            self.assertEqual(len(rows), 2)  # never filtered by the join
            # Both banks share KEN/2015's control variable (broadcast by iso3+year).
            self.assertEqual(rows[("IBRD", "KEN", "2015")]["wdi_ny_gdp_mktp_pp_cd"], "70000000000")
            self.assertEqual(rows[("IDA", "KEN", "2015")]["wdi_ny_gdp_mktp_pp_cd"], "70000000000")
            # IBRD/KEN/2015 matched a real breakdown row.
            self.assertEqual(rows[("IBRD", "KEN", "2015")]["sovereign_n"], "2.0")
            # IDA/KEN/2015 has no lending at all -- breakdown columns are a
            # real zero, not blank (docs/coding_decisions.md, 2026-09-27).
            self.assertEqual(rows[("IDA", "KEN", "2015")]["sovereign_n"], "0.0")

    def test_a_bank_with_lending_but_no_breakdown_match_stays_blank_not_zero(self):
        # any_lending=1 but the breakdown table has no matching row at all
        # (e.g. project_breakdown.csv is stale, or missing a bank entirely)
        # -- must not silently read as a confirmed zero.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            panel = write_csv(path / "panel.csv", PANEL_FIELDS, [
                {"bank": "IBRD", "iso3": "KEN", "year": "2015", "eligibility_basis": "rule", "any_lending": "1", "note": ""},
            ])
            controls = write_csv(path / "controls.csv", CONTROL_FIELDS, [])
            breakdown = write_csv(path / "breakdown.csv", BREAKDOWN_FIELDS, [])
            output = path / "merged.csv"
            result = run("merge_control_panel.py", "--panel", str(panel), "--controls", str(controls),
                         "--breakdown", str(breakdown), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            row = read_rows(output)[0]
            self.assertEqual(row["sovereign_n"], "")


class ControlVariablesResolutionTests(unittest.TestCase):
    """scripts/build_control_variables.py's name-resolution helper -- the
    seam every name-based source (Religious Restrictions' Ctry_EditorialName,
    UN Tourism's reporter_area_label) goes through, plus each source's own
    small fixup dict for names the shared resolver doesn't recognize as-is."""

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        import build_control_variables as bcv
        self.bcv = bcv

    def test_a_name_the_resolver_already_knows_needs_no_fixup(self):
        self.assertEqual(self.bcv._resolve("Kenya", {}), "KEN")

    def test_religion_fixups_resolve_names_the_resolver_alone_would_miss(self):
        for name in self.bcv._RELIGION_FIXUPS:
            self.assertIsNotNone(self.bcv._resolve(name, self.bcv._RELIGION_FIXUPS), msg=name)

    def test_un_tourism_fixups_resolve_names_the_resolver_alone_would_miss(self):
        for name in self.bcv._UN_TOURISM_FIXUPS:
            self.assertIsNotNone(self.bcv._resolve(name, self.bcv._UN_TOURISM_FIXUPS), msg=name)

    def test_a_regional_aggregate_correctly_fails_to_resolve(self):
        # "Africa" etc. are UN/WB regional aggregates, not countries -- they
        # must stay unresolved (dropped), never guessed at a country.
        self.assertIsNone(self.bcv._resolve("Africa", {}))
        self.assertIsNone(self.bcv._resolve("World", {}))


class EuMemberAndWbRegionTests(unittest.TestCase):
    """scripts/build_control_variables.py's eu_member()/wb_region() sources
    (2026-09-28) -- checked against the real, checked-in eu_membership.csv
    and the real World Bank region metadata file, same as this file's other
    resolution tests."""

    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        import build_control_variables as bcv
        self.bcv = bcv

    def test_eu_member_is_a_closed_roster_never_blank_for_a_known_country(self):
        df = self.bcv.eu_member()
        by_key = {(r["iso3"], r["year"]): r["eu_member"] for _, r in df.iterrows()}
        # Croatia: acceded 1 July 2013.
        self.assertEqual(by_key[("HRV", 2012)], 0)
        self.assertEqual(by_key[("HRV", 2013)], 1)
        # UK: Brexit 31 Jan 2020 -- the exit year itself still counts (this
        # project's usual calendar-year spell convention), the next doesn't.
        self.assertEqual(by_key[("GBR", 2020)], 1)
        self.assertEqual(by_key[("GBR", 2021)], 0)
        # No blanks anywhere in this source's own (iso3, year) grid.
        self.assertTrue(df["eu_member"].isin([0, 1]).all())

    def test_wb_region_resolves_a_known_country_and_drops_aggregates(self):
        df = self.bcv.wb_region()
        by_iso3 = dict(zip(df[df["year"] == 2015]["iso3"], df[df["year"] == 2015]["wb_region"]))
        self.assertEqual(by_iso3.get("KEN"), "Sub-Saharan Africa")
        self.assertEqual(by_iso3.get("FRA"), "Europe & Central Asia")
        # WDI aggregate pseudo-codes ("AFE" etc.) have a blank Region in the
        # source file and must never surface as a fabricated region.
        self.assertNotIn("AFE", df["iso3"].values)


if __name__ == "__main__":
    unittest.main()
