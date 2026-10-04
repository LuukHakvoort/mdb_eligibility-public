"""Offline tests for the validation harness.

Each test builds a tiny panel in a temporary directory and runs the real
scripts against it, so the checks are exercised end to end without the scraper
output, the network, or the full 8,000-row panel.
"""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

COMMITMENT_ROWS = [
    # bank, iso3, year, projects, positive
    ("AIIB", "IND", 2018, 3, 3),
    ("AIIB", "BGD", 2019, 1, 1),
    ("NDB", "BRA", 2020, 2, 2),
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_commitments(directory: Path) -> Path:
    return write_csv(
        directory / "commitments.csv",
        ["bank", "iso3", "year", "projects", "projects_with_positive_amount"],
        [
            {
                "bank": bank, "iso3": iso3, "year": year,
                "projects": projects, "projects_with_positive_amount": positive,
            }
            for bank, iso3, year, projects, positive in COMMITMENT_ROWS
        ],
    )


def write_eligibility(directory: Path, rows: list[tuple[str, str, int, str]]) -> Path:
    return write_csv(
        directory / "eligibility.csv",
        ["bank", "iso3", "year", "eligible", "source", "note"],
        [
            {"bank": bank, "iso3": iso3, "year": year, "eligible": eligible,
             "source": "test fixture", "note": ""}
            for bank, iso3, year, eligible in rows
        ],
    )


def write_coverage(directory: Path, rows: list[tuple[str, str, str]] = ()) -> Path:
    """An empty coverage file by default -- keeps zero-share/panel-balance tests
    hermetic instead of silently picking up this repo's real bank_coverage.csv."""
    return write_csv(
        directory / "bank_coverage.csv",
        ["bank", "coverage_start_year", "coverage_end_year", "note"],
        [
            {"bank": bank, "coverage_start_year": start, "coverage_end_year": end, "note": ""}
            for bank, start, end in rows
        ],
    )


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, cwd=REPO,
    )


class RevealedEligibilityTests(unittest.TestCase):
    # `--accepted` points at a path that doesn't exist in every test below
    # unless a test specifically builds one -- keeps these hermetic, isolated
    # from this repo's own real data/manual/accepted_revealed_exceptions.csv
    # (2026-09-30), the same pattern used elsewhere in this project (e.g.
    # test_unga_ideal_points.py's `--fp-extension`).

    def test_missing_eligibility_file_fails_with_every_dyad_year_uncoded(self):
        # The expected state at the start of session 2: the panel does not
        # exist, so every observed dyad-year is a violation -- reported, not
        # crashed on.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            result = run(
                "check_revealed.py",
                "--commitments", str(write_commitments(path)),
                "--eligibility", str(path / "does_not_exist.csv"),
                "--accepted", str(path / "no_accepted.csv"),
                "--report", str(path / "violations.csv"),
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("does not exist yet", result.stdout)
            violations = read_rows(path / "violations.csv")
            self.assertEqual(len(violations), len(COMMITMENT_ROWS))
            self.assertEqual({row["kind"] for row in violations}, {"not yet coded"})

    def test_fully_covered_panel_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            eligibility = write_eligibility(
                path, [(bank, iso3, year, "1") for bank, iso3, year, _, _ in COMMITMENT_ROWS]
            )
            result = run(
                "check_revealed.py",
                "--commitments", str(write_commitments(path)),
                "--eligibility", str(eligibility),
                "--accepted", str(path / "no_accepted.csv"),
                "--report", str(path / "violations.csv"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PASS", result.stdout)

    def test_partial_coverage_reduces_violations_by_exactly_the_rows_covered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            eligibility = write_eligibility(path, [("AIIB", "IND", 2018, "1")])
            result = run(
                "check_revealed.py",
                "--commitments", str(write_commitments(path)),
                "--eligibility", str(eligibility),
                "--accepted", str(path / "no_accepted.csv"),
                "--report", str(path / "violations.csv"),
            )
            self.assertEqual(result.returncode, 2)
            violations = read_rows(path / "violations.csv")
            self.assertEqual(len(violations), len(COMMITMENT_ROWS) - 1)

    def test_explicit_zero_is_a_contradiction_not_an_uncoded_row(self):
        # The distinction the bank-by-bank workflow depends on: a blank means
        # "not done yet"; a coded 0 against observed lending is a real error.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            eligibility = write_eligibility(
                path, [("AIIB", "IND", 2018, "0"), ("AIIB", "BGD", 2019, "")]
            )
            result = run(
                "check_revealed.py",
                "--commitments", str(write_commitments(path)),
                "--eligibility", str(eligibility),
                "--accepted", str(path / "no_accepted.csv"),
                "--report", str(path / "violations.csv"),
            )
            self.assertEqual(result.returncode, 2)
            violations = {
                (row["bank"], row["iso3"]): row["kind"]
                for row in read_rows(path / "violations.csv")
            }
            self.assertEqual(violations[("AIIB", "IND")], "contradiction")
            self.assertEqual(violations[("AIIB", "BGD")], "not yet coded")
            self.assertIn("coded ineligible", result.stdout)


class AcceptedRevealedExceptionsSchemaTests(unittest.TestCase):
    """scripts/validate_manual.py's schema for data/manual/accepted_revealed_
    exceptions.csv (2026-09-30) -- no existing test file covers validate_
    manual.py itself, so this is deliberately narrow: just the new schema."""

    ACCEPTED_FIELDS = ["bank", "iso3", "year", "reason", "decided_date", "note"]

    def test_the_real_checked_in_file_validates_clean(self):
        result = run("validate_manual.py", str(REPO / "data" / "manual" / "accepted_revealed_exceptions.csv"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_an_unrecognized_reason_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accepted_revealed_exceptions.csv"
            write_csv(path, self.ACCEPTED_FIELDS, [
                {"bank": "AIIB", "iso3": "IND", "year": "2018", "reason": "made_up_reason_not_in_the_enum",
                 "decided_date": "2026-09-30", "note": "test fixture"},
            ])
            result = run("validate_manual.py", str(path))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("reason", result.stderr.lower())


class AcceptedRevealedExceptionTests(unittest.TestCase):
    """The three-way classification added 2026-09-30: a violation already
    logged in data/manual/accepted_revealed_exceptions.csv is reported as its
    own kind and doesn't fail the build, but a violation NOT on that list
    still does -- so a genuinely new, unexplained gap is still caught."""

    def write_accepted(self, directory: Path, rows: list[tuple[str, str, int, str]]) -> Path:
        return write_csv(
            directory / "accepted.csv",
            ["bank", "iso3", "year", "reason", "decided_date", "note"],
            [
                {"bank": bank, "iso3": iso3, "year": year, "reason": reason,
                 "decided_date": "2026-09-30", "note": "test fixture"}
                for bank, iso3, year, reason in rows
            ],
        )

    def test_an_accepted_row_is_reported_but_does_not_fail_the_build(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            eligibility = write_eligibility(path, [("AIIB", "IND", 2018, "0")])
            accepted = self.write_accepted(path, [("AIIB", "IND", 2018, "test_reason")])
            result = run(
                "check_revealed.py",
                "--commitments", str(write_commitments(path)),
                "--eligibility", str(eligibility),
                "--accepted", str(accepted),
                "--report", str(path / "violations.csv"),
            )
            self.assertEqual(result.returncode, 2, result.stderr)  # BGD/BRA still uncoded, not accepted
            self.assertIn("FAIL", result.stderr)
            violations = {(r["bank"], r["iso3"]): r["kind"] for r in read_rows(path / "violations.csv")}
            self.assertEqual(violations[("AIIB", "IND")], "accepted exception")

    def test_every_violation_accepted_passes_the_build(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            eligibility = write_eligibility(
                path, [(bank, iso3, year, "0") for bank, iso3, year, _, _ in COMMITMENT_ROWS]
            )
            accepted = self.write_accepted(
                path, [(bank, iso3, year, "test_reason") for bank, iso3, year, _, _ in COMMITMENT_ROWS]
            )
            result = run(
                "check_revealed.py",
                "--commitments", str(write_commitments(path)),
                "--eligibility", str(eligibility),
                "--accepted", str(accepted),
                "--report", str(path / "violations.csv"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PASS", result.stdout)
            self.assertIn("accepted exception", result.stdout)
            violations = read_rows(path / "violations.csv")
            self.assertEqual({row["kind"] for row in violations}, {"accepted exception"})

    def test_a_row_not_on_the_accepted_list_still_fails_even_if_others_are_accepted(self):
        # The whole point: accepting one specific, reviewed case must never
        # accidentally silence an unrelated, genuinely new violation.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            eligibility = write_eligibility(
                path, [(bank, iso3, year, "0") for bank, iso3, year, _, _ in COMMITMENT_ROWS]
            )
            accepted = self.write_accepted(path, [("AIIB", "IND", 2018, "test_reason")])
            result = run(
                "check_revealed.py",
                "--commitments", str(write_commitments(path)),
                "--eligibility", str(eligibility),
                "--accepted", str(accepted),
                "--report", str(path / "violations.csv"),
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("FAIL", result.stderr)
            violations = {(r["bank"], r["iso3"]): r["kind"] for r in read_rows(path / "violations.csv")}
            self.assertEqual(violations[("AIIB", "IND")], "accepted exception")
            self.assertEqual(violations[("AIIB", "BGD")], "contradiction")
            self.assertEqual(violations[("NDB", "BRA")], "contradiction")


class ZeroShareTests(unittest.TestCase):
    def test_zero_eligible_dyad_years_reports_na_without_dividing_by_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            result = run(
                "report_zero_share.py",
                "--commitments", str(write_commitments(path)),
                "--eligibility", str(path / "does_not_exist.csv"),
                "--coverage", str(write_coverage(path)),
                "--report", str(path / "zero_share.csv"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("n/a", result.stdout)
            rows = {
                row["bank"]: row
                for row in read_rows(path / "zero_share.csv")
            }
            self.assertEqual(rows["AIIB"]["eligible_dyad_years"], "0")
            self.assertEqual(rows["AIIB"]["zero_share"], "")

    def test_share_matches_a_hand_calculation_and_flags_a_wide_panel(self):
        # AIIB: 4 eligible, 1 with lending -> 0.750, no flag.
        # NDB: 21 eligible, 1 with lending -> 0.952, flagged as possibly wide.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            rows = [("AIIB", iso3, 2018, "1") for iso3 in ("IND", "PAK", "LKA", "NPL")]
            rows += [("NDB", "BRA", 2020, "1")]
            rows += [("NDB", f"X{index:02d}", 2020, "1") for index in range(20)]
            eligibility = write_eligibility(path, rows)
            result = run(
                "report_zero_share.py",
                "--commitments", str(write_commitments(path)),
                "--eligibility", str(eligibility),
                "--coverage", str(write_coverage(path)),
                "--report", str(path / "zero_share.csv"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            share = {
                row["bank"]: row
                for row in read_rows(path / "zero_share.csv")
            }
            self.assertEqual(share["AIIB"]["zero_share"], "0.750")
            self.assertEqual(share["AIIB"]["flag"], "")
            self.assertEqual(share["NDB"]["zero_share"], "0.952")
            self.assertEqual(share["NDB"]["flag"], "WIDE?")


class PanelBalanceTests(unittest.TestCase):
    def test_empty_panel_renders_a_chart_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            result = run(
                "report_panel_balance.py",
                "--eligibility", str(path / "does_not_exist.csv"),
                "--coverage", str(write_coverage(path)),
                "--report", str(path / "balance.csv"),
                "--svg", str(path / "balance.svg"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            svg = (path / "balance.svg").read_text(encoding="utf-8")
            self.assertIn("No eligible dyad-years yet", svg)
            self.assertIn("<svg", svg)
            rows = read_rows(path / "balance.csv")
            self.assertEqual({row["eligible_dyad_years"] for row in rows}, {"0"})
            self.assertEqual({row["in_coverage"] for row in rows}, {"1"})

    def test_counts_land_in_the_right_bank_year_cell(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            eligibility = write_eligibility(
                path,
                [("AIIB", "IND", 2018, "1"), ("AIIB", "PAK", 2018, "1"),
                 ("AIIB", "IND", 2019, "1"), ("NDB", "BRA", 2020, "0")],
            )
            result = run(
                "report_panel_balance.py",
                "--eligibility", str(eligibility),
                "--coverage", str(write_coverage(path)),
                "--report", str(path / "balance.csv"),
                "--svg", str(path / "balance.svg"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            counts = {
                (row["bank"], row["year"]): int(row["eligible_dyad_years"])
                for row in read_rows(path / "balance.csv")
            }
            self.assertEqual(counts[("AIIB", "2018")], 2)
            self.assertEqual(counts[("AIIB", "2019")], 1)
            self.assertEqual(counts[("NDB", "2020")], 0)  # eligible = 0 is not counted


class CoverageAwarenessTests(unittest.TestCase):
    """A dyad-year outside a bank's data-coverage window (banks.json's
    coverage_start_year/coverage_end_year) means the source doesn't cover that
    year -- not that the bank had no lending. Both reports must say so rather
    than reading it as a real zero."""

    def test_zero_share_excludes_out_of_coverage_years_from_the_denominator(self):
        # CDB: coverage 2013-2023. Eligible in 2010 (out) and 2015 (in, no
        # lending). Only the 2015 row should count toward the share.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            eligibility = write_eligibility(
                path, [("CDB", "JAM", 2010, "1"), ("CDB", "JAM", 2015, "1")]
            )
            result = run(
                "report_zero_share.py",
                "--commitments", str(write_commitments(path)),  # no CDB rows -> no lending either year
                "--eligibility", str(eligibility),
                "--coverage", str(write_coverage(path, [("CDB", "2013", "2023")])),
                "--report", str(path / "zero_share.csv"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            row = {r["bank"]: r for r in read_rows(path / "zero_share.csv")}["CDB"]
            self.assertEqual(row["eligible_dyad_years"], "2")
            self.assertEqual(row["out_of_coverage"], "1")
            self.assertEqual(row["in_coverage_dyad_years"], "1")
            self.assertEqual(row["zero_share"], "1.000")  # the one in-coverage year has no lending

    def test_panel_balance_marks_in_coverage_per_year_and_hatches_the_svg(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            eligibility = write_eligibility(
                path, [("CDB", "JAM", 2010, "1"), ("CDB", "JAM", 2015, "1")]
            )
            result = run(
                "report_panel_balance.py",
                "--eligibility", str(eligibility),
                "--coverage", str(write_coverage(path, [("CDB", "2013", "2023")])),
                "--report", str(path / "balance.csv"),
                "--svg", str(path / "balance.svg"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {
                (row["bank"], int(row["year"])): row["in_coverage"]
                for row in read_rows(path / "balance.csv")
            }
            self.assertEqual(rows[("CDB", 2010)], "0")
            self.assertEqual(rows[("CDB", 2015)], "1")
            # A bank with no coverage window at all (e.g. AIIB got none here) is
            # always in coverage.
            self.assertEqual(rows[("AIIB", 2002)], "1")
            svg = (path / "balance.svg").read_text(encoding="utf-8")
            self.assertIn("no-coverage-hatch", svg)
            self.assertIn("data 2013–2023", svg)


class BuildMdbPanelTests(unittest.TestCase):
    """scripts/build_mdb_panel.py: the estimation panel joining eligibility.csv,
    membership.csv and lending outcomes. Covers the two things that matter most
    -- an eligible-but-quiet dyad-year is zero-filled rather than dropped, and a
    dyad-year the rules missed is still included, flagged, whenever
    commitments.csv shows real lending (the same revealed-eligibility principle
    check_revealed.py enforces)."""

    ELIGIBILITY_FIELDS = [
        "bank", "iso3", "year", "eligible", "member_since", "source", "note",
    ]
    MEMBERSHIP_FIELDS = [
        "bank", "iso3", "year", "member", "capital_share_pct", "voting_power_pct",
        "accession_date", "recipient_status", "member_source", "recipient_source", "note",
    ]
    DYAD_FIELDS = ["bank_id", "country_code", "year", "usd_nominal_total", "usd_2025_total",
                   "ppp_2025_total", "n_ppp_unpriced"]

    def _write_eligibility(self, path: Path, rows: list[dict]) -> Path:
        return write_csv(path / "eligibility.csv", self.ELIGIBILITY_FIELDS, rows)

    def _write_membership(self, path: Path, rows: list[dict]) -> Path:
        return write_csv(path / "membership.csv", self.MEMBERSHIP_FIELDS, rows)

    def _write_dyad(self, path: Path, rows: list[dict]) -> Path:
        return write_csv(path / "dyad_country_year.csv", self.DYAD_FIELDS, rows)

    def _run(self, path: Path, commitments: Path) -> subprocess.CompletedProcess:
        return run(
            "build_mdb_panel.py",
            "--eligibility", str(self._write_eligibility(path, self.eligibility_rows)),
            "--membership", str(self._write_membership(path, self.membership_rows)),
            "--commitments", str(commitments),
            "--dyad-country-year", str(self._write_dyad(path, self.dyad_rows)),
            "--output", str(path / "mdb_panel.csv"),
        )

    def test_eligible_dyad_year_with_no_lending_is_zero_filled_not_dropped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.eligibility_rows = [
                {"bank": "AIIB", "iso3": "PAK", "year": 2020, "eligible": "1",
                 "member_since": "2016", "source": "test", "note": ""},
            ]
            self.membership_rows = [
                {"bank": "AIIB", "iso3": "PAK", "year": 2020, "member": "1",
                 "capital_share_pct": "8.5", "voting_power_pct": "7.6",
                 "accession_date": "2016-01-01", "recipient_status": "1",
                 "member_source": "test", "recipient_source": "test", "note": ""},
            ]
            self.dyad_rows = []
            commitments = write_commitments(path)  # AIIB/PAK/2020 is not in COMMITMENT_ROWS
            result = self._run(path, commitments)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(path / "mdb_panel.csv")}
            row = rows[("AIIB", "PAK", "2020")]
            self.assertEqual(row["eligibility_basis"], "rule")
            self.assertEqual(row["any_lending"], "0")
            self.assertEqual(row["projects"], "0")
            self.assertEqual(row["capital_share_pct"], "8.5")
            # A real zero, not a missing value: nothing to join because there
            # was no lending, not because the amount is unknown.
            self.assertEqual(row["usd_nominal_total"], "0")
            self.assertEqual(row["usd_2025_total"], "0")
            self.assertEqual(row["ppp_2025_total"], "0")

    def test_lending_with_no_ppp_value_stays_blank_not_zero(self):
        # 2026-10-04: the scraper prices no PPP for some lending (all 2026
        # lending, and 313 unpriced country-years). A real lending dyad-year
        # with no PPP value must stay blank, never read as zero lending.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.eligibility_rows = []
            self.membership_rows = []
            self.dyad_rows = [
                {"bank_id": "aiib", "country_code": "IND", "year": 2018,
                 "usd_nominal_total": "500000", "usd_2025_total": "550000", "ppp_2025_total": ""},
            ]
            commitments = write_commitments(path)
            result = self._run(path, commitments)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(path / "mdb_panel.csv")}
            row = rows[("AIIB", "IND", "2018")]
            self.assertEqual(row["any_lending"], "1")
            self.assertEqual(row["usd_2025_total"], "550000")
            self.assertEqual(row["ppp_2025_total"], "")

    def test_unpriced_lending_is_blank_even_though_the_scraper_wrote_zero(self):
        # The scraper sums PPP over priced projects only, so an unpriced
        # dyad-year arrives as 0 with n_ppp_unpriced > 0. That must not be
        # read as a priced zero.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.eligibility_rows = []
            self.membership_rows = []
            self.dyad_rows = [
                {"bank_id": "aiib", "country_code": "IND", "year": 2018,
                 "usd_nominal_total": "500000", "usd_2025_total": "550000",
                 "ppp_2025_total": "0", "n_ppp_unpriced": "3"},
            ]
            commitments = write_commitments(path)
            result = self._run(path, commitments)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(path / "mdb_panel.csv")}
            self.assertEqual(rows[("AIIB", "IND", "2018")]["ppp_2025_total"], "")

    def test_years_after_the_deflator_base_are_blank_not_zero(self):
        # 2026 lending: the FRED deflator has no 2026 value, so nothing is
        # priced -- even a 0 written by the scraper must not become a zero.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.eligibility_rows = []
            self.membership_rows = []
            self.dyad_rows = [
                {"bank_id": "aiib", "country_code": "IND", "year": 2026,
                 "usd_nominal_total": "500000", "usd_2025_total": "0", "ppp_2025_total": "0",
                 "n_ppp_unpriced": "0"},
            ]
            commitments = write_commitments(path)
            with commitments.open("a", encoding="utf-8", newline="") as handle:
                handle.write("AIIB,IND,2026,2,2\n")
            result = self._run(path, commitments)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(path / "mdb_panel.csv")}
            self.assertEqual(rows[("AIIB", "IND", "2026")]["ppp_2025_total"], "")

    def test_lending_the_rules_missed_is_still_included_and_flagged_revealed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            # AIIB/IND/2018 has observed lending (COMMITMENT_ROWS) but no
            # eligibility.csv row at all here.
            self.eligibility_rows = []
            self.membership_rows = []
            self.dyad_rows = []
            commitments = write_commitments(path)
            result = self._run(path, commitments)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(path / "mdb_panel.csv")}
            row = rows[("AIIB", "IND", "2018")]
            self.assertEqual(row["eligibility_basis"], "revealed")
            self.assertEqual(row["any_lending"], "1")
            self.assertEqual(row["projects"], "3")
            self.assertIn("revealed lending", row["note"])

    def test_afdb_gets_a_real_usd_total_like_any_other_bank(self):
        # AfDB and ADF were briefly two separate bank codes (2026-09-24 -
        # 2026-09-28); merged back, so AfDB now reads dyad_country_year.csv
        # the same way every other bank does -- no more "no USD split" case.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.eligibility_rows = [
                {"bank": "AfDB", "iso3": "KEN", "year": 2020, "eligible": "1",
                 "member_since": "", "source": "test", "note": ""},
            ]
            self.membership_rows = []
            self.dyad_rows = [
                {"bank_id": "afdb", "country_code": "KEN", "year": 2020,
                 "usd_nominal_total": "1000000", "usd_2025_total": "1100000"},
            ]
            commitments = write_commitments(path)
            with commitments.open("a", encoding="utf-8", newline="") as handle:
                handle.write("AfDB,KEN,2020,1,1\n")
            result = self._run(path, commitments)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(path / "mdb_panel.csv")}
            row = rows[("AfDB", "KEN", "2020")]
            self.assertEqual(row["usd_nominal_total"], "1000000")
            self.assertEqual(row["usd_2025_total"], "1100000")

    def test_ppp_adjusted_amount_is_carried_through_alongside_usd(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.eligibility_rows = []
            self.membership_rows = []
            self.dyad_rows = [
                {"bank_id": "aiib", "country_code": "IND", "year": 2018,
                 "usd_nominal_total": "500000", "usd_2025_total": "550000", "ppp_2025_total": "1400000"},
            ]
            commitments = write_commitments(path)
            result = self._run(path, commitments)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {(r["bank"], r["iso3"], r["year"]): r for r in read_rows(path / "mdb_panel.csv")}
            self.assertEqual(rows[("AIIB", "IND", "2018")]["ppp_2025_total"], "1400000")

    def test_no_lending_is_lost_between_commitments_and_the_panel(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.eligibility_rows = [
                {"bank": bank, "iso3": iso3, "year": year, "eligible": "1",
                 "member_since": "", "source": "test", "note": ""}
                for bank, iso3, year, _, _ in COMMITMENT_ROWS
            ]
            self.membership_rows = []
            self.dyad_rows = []
            commitments = write_commitments(path)
            result = self._run(path, commitments)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = read_rows(path / "mdb_panel.csv")
            self.assertEqual(
                sum(int(r["projects"]) for r in rows),
                sum(projects for _, _, _, projects, _ in COMMITMENT_ROWS),
            )


if __name__ == "__main__":
    unittest.main()
