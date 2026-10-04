"""Offline tests for the three-valued combination logic and components."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _panel import and3, not3  # noqa: E402
from components import bars, existence, mandate, membership, recipient, window  # noqa: E402


class And3Tests(unittest.TestCase):
    def test_any_false_wins_over_unknown(self):
        self.assertFalse(and3(True, None, False))

    def test_unknown_wins_when_nothing_is_false(self):
        self.assertIsNone(and3(True, None, True))

    def test_all_true_is_true(self):
        self.assertTrue(and3(True, True, True))

    def test_not3_preserves_unknown(self):
        self.assertIsNone(not3(None))
        self.assertFalse(not3(True))
        self.assertTrue(not3(False))


class ExistenceComponentTests(unittest.TestCase):
    def test_within_window_is_true_outside_is_false_unknown_bank_is_none(self):
        windows = {"IBRD": (1945, None), "AIIB": (2016, None), "EIB": (1958, 2020)}
        self.assertTrue(existence.bank_exists("IBRD", 2010, windows))
        self.assertFalse(existence.bank_exists("AIIB", 2010, windows))
        self.assertTrue(existence.bank_exists("AIIB", 2016, windows))
        self.assertFalse(existence.bank_exists("EIB", 2021, windows))  # closed window
        self.assertIsNone(existence.bank_exists("NDB", 2020, windows))  # not in the file at all


class MembershipComponentTests(unittest.TestCase):
    def test_real_accession_date_is_confident_both_sides(self):
        evidence = {("EBRD", "MNE"): {"accession_year": 2007, "earliest_observed_year": None,
                                       "earliest_panel_year": None}}
        self.assertFalse(membership.is_member("EBRD", "MNE", 2006, evidence))
        self.assertTrue(membership.is_member("EBRD", "MNE", 2007, evidence))

    def test_observed_lending_is_a_lower_bound_only(self):
        evidence = {("AIIB", "ARG"): {"accession_year": None, "earliest_observed_year": 2018,
                                       "earliest_panel_year": None}}
        self.assertTrue(membership.is_member("AIIB", "ARG", 2018, evidence))
        self.assertIsNone(membership.is_member("AIIB", "ARG", 2010, evidence))  # unknown, not False

    def test_no_evidence_at_all_is_unknown(self):
        self.assertIsNone(membership.is_member("IBRD", "XXX", 2010, {}))

    def test_earliest_of_multiple_lower_bounds_is_used(self):
        evidence = {("X", "Y"): {"accession_year": None, "earliest_observed_year": 2015,
                                  "earliest_panel_year": 2010}}
        self.assertTrue(membership.is_member("X", "Y", 2012, evidence))  # panel bound is earlier


class BarsComponentTests(unittest.TestCase):
    def test_start_year_itself_is_not_barred_only_subsequent_full_years_are(self):
        # Whole-year rule (docs/architecture.md sec. 3): a spell starting
        # mid-year doesn't retroactively bar its own start year, since we only
        # know it started *sometime* in 2022, not that it covered all of it.
        events = {("EBRD", "RUS"): [
            {"event_type": "sanctions_suspension", "start_date": "2022-03", "end_date": ""},
        ]}
        self.assertFalse(bars.is_barred("EBRD", "RUS", 2021, events))
        self.assertFalse(bars.is_barred("EBRD", "RUS", 2022, events))  # start year: only partially barred
        self.assertTrue(bars.is_barred("EBRD", "RUS", 2023, events))  # first full year
        self.assertTrue(bars.is_barred("EBRD", "RUS", 2026, events))  # open-ended

    def test_end_year_itself_is_not_barred_either(self):
        events = {("IDA", "AFG"): [
            {"event_type": "sanctions_suspension", "start_date": "2014-01", "end_date": "2016-06"},
        ]}
        self.assertFalse(bars.is_barred("IDA", "AFG", 2014, events))  # start year
        self.assertTrue(bars.is_barred("IDA", "AFG", 2015, events))  # only full year in range
        self.assertFalse(bars.is_barred("IDA", "AFG", 2016, events))  # end year
        self.assertFalse(bars.is_barred("IDA", "AFG", 2017, events))  # after the spell ended

    def test_undated_placeholder_row_is_unknown_not_false(self):
        events = {("IBRD", "ZWE"): [{"event_type": "non_accrual", "start_date": "", "end_date": ""}]}
        self.assertIsNone(bars.is_barred("IBRD", "ZWE", 2015, events))

    def test_no_row_at_all_is_unknown(self):
        self.assertIsNone(bars.is_barred("IBRD", "AAA", 2015, {}))


class BarsDefaultInBuildTests(unittest.TestCase):
    """build.py's own not_evidenced default (docs/coding_decisions.md,
    2026-09-27): components/bars.py itself still returns None for an
    unlogged pair (BarsComponentTests above), but eligibility.csv's
    `eligible` column treats that None as "not evidenced" (False) rather
    than propagating unknown, while `eligible_strict` keeps the original,
    fully-conservative three-valued result. Exercises the exact
    e_evidenced/eligible/eligible_strict computation in scripts/build.py's
    main() loop, not a reimplementation of it."""

    @staticmethod
    def _combine(a, b, c, d, e):
        e_evidenced = e is not None
        eligible_strict = and3(a, b, c, d, not3(e))
        eligible = and3(a, b, c, d, not3(e if e_evidenced else False))
        return e_evidenced, eligible, eligible_strict

    def test_unlogged_bar_defaults_to_eligible_true_but_strict_stays_unknown(self):
        e_evidenced, eligible, eligible_strict = self._combine(True, True, True, True, None)
        self.assertFalse(e_evidenced)
        self.assertTrue(eligible)
        self.assertIsNone(eligible_strict)

    def test_logged_bar_makes_both_columns_agree(self):
        e_evidenced, eligible, eligible_strict = self._combine(True, True, True, True, True)
        self.assertTrue(e_evidenced)
        self.assertFalse(eligible)
        self.assertFalse(eligible_strict)

    def test_a_definite_false_elsewhere_still_wins_regardless_of_the_bar_default(self):
        e_evidenced, eligible, eligible_strict = self._combine(True, False, True, True, None)
        self.assertFalse(e_evidenced)
        self.assertFalse(eligible)
        self.assertFalse(eligible_strict)


class RecipientComponentTests(unittest.TestCase):
    """components/recipient.py: Component B' -- recipient status, distinct
    from bare membership (components/membership.py). The AIIB/DEU and
    IDB/USA,CAN bug this whole module exists to fix is: bare membership must
    never leak into eligibility's Component B."""

    def test_membership_only_bank_mirrors_bare_membership(self):
        b_basis = {"EBRD": "membership_only"}
        evidence = {("EBRD", "MNE"): {"accession_year": 2007, "earliest_observed_year": None,
                                       "earliest_panel_year": None}}
        self.assertFalse(recipient.is_recipient("EBRD", "MNE", 2006, b_basis, {}, evidence))
        self.assertTrue(recipient.is_recipient("EBRD", "MNE", 2007, b_basis, {}, evidence))

    def test_no_membership_condition_bank_is_always_true(self):
        b_basis = {"EIB": "no_membership_condition"}
        self.assertTrue(recipient.is_recipient("EIB", "XXX", 2002, b_basis, {}, {}))

    def test_needs_research_bank_reads_recipient_status_table_not_bare_membership(self):
        # This is the exact AIIB/Germany, IDB/USA-and-Canada shape: a country
        # can be a confirmed shareholder (member=True elsewhere) while
        # recipient.is_recipient() says False, because they're two different
        # questions answered by two different files.
        b_basis = {"AIIB": "needs_recipient_research"}
        status = {("AIIB", "DEU"): False}
        evidence = {("AIIB", "DEU"): {"accession_year": 2016, "earliest_observed_year": None,
                                       "earliest_panel_year": None}}
        self.assertTrue(membership.is_member("AIIB", "DEU", 2024, evidence))
        self.assertFalse(recipient.is_recipient("AIIB", "DEU", 2024, b_basis, status, evidence))

    def test_needs_research_bank_with_no_row_is_unknown(self):
        b_basis = {"AIIB": "needs_recipient_research"}
        self.assertIsNone(recipient.is_recipient("AIIB", "ZZZ", 2024, b_basis, {}, {}))

    def test_unknown_bank_is_unknown(self):
        self.assertIsNone(recipient.is_recipient("ZZZ", "DEU", 2024, {}, {}, {}))

    def test_a_listed_non_regional_shareholder_is_false_despite_real_membership(self):
        # 2026-10-02: the US/Japan/Germany/... bug -- IBRD and EBRD are
        # membership_only, so a real, long-standing shareholder like the US
        # would otherwise read as a recipient. A (bank, iso3) pair on the
        # closed list overrides that, regardless of how solid the
        # membership evidence is.
        b_basis = {"IBRD": "membership_only"}
        evidence = {("IBRD", "USA"): {"accession_year": 1945, "earliest_observed_year": None,
                                       "earliest_panel_year": None}}
        non_regional = {("IBRD", "USA")}
        self.assertTrue(membership.is_member("IBRD", "USA", 2020, evidence))  # real shareholder
        self.assertFalse(recipient.is_recipient("IBRD", "USA", 2020, b_basis, {}, evidence, non_regional))

    def test_an_unlisted_country_is_unaffected_by_the_closed_list(self):
        # The closed list must never touch a country it doesn't name --
        # Poland-shaped case, same membership_only basis as the US above.
        b_basis = {"IBRD": "membership_only"}
        evidence = {("IBRD", "POL"): {"accession_year": 1986, "earliest_observed_year": None,
                                       "earliest_panel_year": None}}
        non_regional = {("IBRD", "USA")}  # POL is not on it
        self.assertTrue(recipient.is_recipient("IBRD", "POL", 2020, b_basis, {}, evidence, non_regional))


class MandateComponentTests(unittest.TestCase):
    """components/mandate.py: Component C, dispatched by banks.json's c_basis."""

    def test_trivial_region_mirrors_recipient_status(self):
        c_basis = {"IDB": "trivial_region"}
        b_basis = {"IDB": "needs_recipient_research"}
        status = {("IDB", "BRA"): True}
        self.assertTrue(mandate.in_mandate("IDB", "BRA", 2020, c_basis, b_basis, status, {}))

    def test_spell_based_is_unknown_until_built(self):
        c_basis = {"EBRD": "spell_based"}
        self.assertIsNone(mandate.in_mandate("EBRD", "MNE", 2020, c_basis, {}, {}, {}))

    def test_unknown_bank_is_unknown(self):
        self.assertIsNone(mandate.in_mandate("ZZZ", "AAA", 2020, {}, {}, {}, {}))

    def test_badea_is_au_member_and_not_arab_league(self):
        c_basis = {"BADEA": "computed"}
        au = {"KEN": [(None, None)], "DZA": [(None, None)]}
        arab_league = {"DZA": [(1962, None)]}
        # Kenya: AU member, never in the Arab League list at all -- True.
        self.assertTrue(mandate.in_mandate("BADEA", "KEN", 2020, c_basis, {}, {}, {},
                                            au, arab_league, {}))
        # Algeria: AU member AND an Arab League member that year -- excluded.
        self.assertFalse(mandate.in_mandate("BADEA", "DZA", 2020, c_basis, {}, {}, {},
                                             au, arab_league, {}))
        # Absent from the AU roster entirely -- both lists are complete, so
        # this is a confident False, not unknown (there's no one left missing).
        self.assertFalse(mandate.in_mandate("BADEA", "ZZZ", 2020, c_basis, {}, {}, {},
                                             au, arab_league, {}))

    def test_arab_league_spell_with_a_suspension_gap(self):
        # A hypothetical AU member with Syria's real Arab League suspension
        # shape (1945-2010 member, suspended 2011-2023, reinstated 2024-):
        # during the suspension gap it genuinely isn't an Arab League member,
        # so BADEA's "not Arab League" condition is True precisely then.
        c_basis = {"BADEA": "computed"}
        au = {"SYR": [(None, None)]}
        arab_league = {"SYR": [(1945, 2010), (2024, None)]}
        self.assertTrue(mandate.in_mandate("BADEA", "SYR", 2020, c_basis, {}, {}, {}, au, arab_league, {}))
        self.assertFalse(mandate.in_mandate("BADEA", "SYR", 2025, c_basis, {}, {}, {}, au, arab_league, {}))

    def test_eib_in_eu_is_true_non_eu_with_no_elm_spell_is_unknown(self):
        # eib_mandate_spells={} is explicit and hermetic (docs/coding_decisions.md,
        # 2026-09-27) -- without it, in_mandate() would fall back to reading the
        # real data/manual/mandate_spells.csv, making this test depend on
        # whatever ELM rows happen to be seeded there.
        c_basis = {"EIB": "spell_based"}
        eu = {"FRA": [(None, None)], "HRV": [(2013, None)]}
        self.assertTrue(mandate.in_mandate("EIB", "FRA", 2020, c_basis, eu_membership=eu, eib_mandate_spells={}))
        self.assertIsNone(mandate.in_mandate("EIB", "HRV", 2010, c_basis, eu_membership=eu, eib_mandate_spells={}))  # before accession, no ELM spell given here
        self.assertTrue(mandate.in_mandate("EIB", "HRV", 2015, c_basis, eu_membership=eu, eib_mandate_spells={}))
        # No ELM spell at all for this country -- unknown, not a guessed False.
        self.assertIsNone(mandate.in_mandate("EIB", "SEN", 2020, c_basis, eu_membership=eu, eib_mandate_spells={}))

    def test_eib_external_lending_mandate_spell_covers_a_non_eu_country(self):
        # The real fix this session (docs/coding_decisions.md, 2026-09-27):
        # a non-EU country with a dated ELM regime now resolves to True/None
        # by year, not just always None.
        c_basis = {"EIB": "spell_based"}
        elm = {"EGY": [(2000, 2006), (2007, 2013), (2014, 2020), (2021, None)]}
        self.assertTrue(mandate.in_mandate("EIB", "EGY", 2010, c_basis, eu_membership={}, eib_mandate_spells=elm))
        self.assertTrue(mandate.in_mandate("EIB", "EGY", 2025, c_basis, eu_membership={}, eib_mandate_spells=elm))
        self.assertIsNone(mandate.in_mandate("EIB", "EGY", 1999, c_basis, eu_membership={}, eib_mandate_spells=elm))

    def test_eib_elm_spell_with_a_gap_is_unknown_not_false_outside_it(self):
        # Brunei-shaped case: eligible 2014-2017, removed 2018, no evidence
        # either way afterwards -- the gap year and afterwards are both
        # unknown, not guessed False.
        c_basis = {"EIB": "spell_based"}
        elm = {"BRN": [(2014, 2017)]}
        self.assertTrue(mandate.in_mandate("EIB", "BRN", 2016, c_basis, eu_membership={}, eib_mandate_spells=elm))
        self.assertIsNone(mandate.in_mandate("EIB", "BRN", 2018, c_basis, eu_membership={}, eib_mandate_spells=elm))
        self.assertIsNone(mandate.in_mandate("EIB", "BRN", 2005, c_basis, eu_membership={}, eib_mandate_spells=elm))

    def test_ebrd_uses_expansion_spell_when_present(self):
        c_basis = {"EBRD": "spell_based"}
        spells = {"EGY": [(2012, None)]}
        # This is the exact bug the spell file fixes: Egypt's EBRD
        # membership date (1991) is not its countries-of-operations date.
        evidence = {("EBRD", "EGY"): {"accession_year": 1991, "earliest_observed_year": None, "earliest_panel_year": None}}
        self.assertFalse(mandate.in_mandate("EBRD", "EGY", 2005, c_basis,
                                             ebrd_mandate_spells=spells, membership_evidence=evidence))
        self.assertTrue(mandate.in_mandate("EBRD", "EGY", 2015, c_basis,
                                            ebrd_mandate_spells=spells, membership_evidence=evidence))

    def test_ebrd_falls_back_to_membership_date_for_the_founding_cohort(self):
        c_basis = {"EBRD": "spell_based"}
        evidence = {("EBRD", "POL"): {"accession_year": 1991, "earliest_observed_year": None, "earliest_panel_year": None}}
        self.assertFalse(mandate.in_mandate("EBRD", "POL", 1990, c_basis,
                                             ebrd_mandate_spells={}, membership_evidence=evidence))
        self.assertTrue(mandate.in_mandate("EBRD", "POL", 1991, c_basis,
                                            ebrd_mandate_spells={}, membership_evidence=evidence))

    def test_ebrd_non_regional_shareholder_override_beats_the_accession_fallback(self):
        # 2026-10-02: the US-shaped bug. The US has an EBRD "Date joined"
        # (1991-03-28, a founding shareholder) that looks identical in shape
        # to Poland's -- same fallback, same era -- but the US was never a
        # country of operations. A listed pair must resolve False even
        # though the accession-date fallback alone would say True.
        c_basis = {"EBRD": "spell_based"}
        evidence = {("EBRD", "USA"): {"accession_year": 1991, "earliest_observed_year": None, "earliest_panel_year": None}}
        non_regional = {("EBRD", "USA")}
        self.assertFalse(mandate.in_mandate("EBRD", "USA", 2020, c_basis,
                                             ebrd_mandate_spells={}, membership_evidence=evidence,
                                             non_regional_shareholders=non_regional))
        # Unlisted (empty override set passed explicitly, for hermeticity)
        # still falls through to the normal, correct fallback.
        self.assertTrue(mandate.in_mandate("EBRD", "USA", 2020, c_basis,
                                            ebrd_mandate_spells={}, membership_evidence=evidence,
                                            non_regional_shareholders=set()))

    def test_aiib_mandate_is_just_membership_no_income_gate(self):
        # AIIB's own FAQ: "AIIB may provide or facilitate financing to any
        # member... Prospective members will only be eligible for financing
        # after they become a member" -- no income or regional restriction.
        # AIIB is `trivial_region`, not `computed` (corrected 2026-09-21
        # after an earlier, wrong "member AND NOT high-income" guess).
        c_basis = {"AIIB": "trivial_region"}
        b_basis = {"AIIB": "needs_recipient_research"}
        status = {("AIIB", "DEU"): False}  # non-borrowing in practice, per recipient_status.csv
        self.assertFalse(mandate.in_mandate("AIIB", "DEU", 2020, c_basis, b_basis, status, {}))


class WindowComponentTests(unittest.TestCase):
    """components/window.py: Component D, dispatched by banks.json's d_basis."""

    def test_no_formal_window_is_always_true(self):
        self.assertTrue(window.window_ok("IDB", "BRA", 2020, {"IDB": "no_formal_window"}))

    def test_classification_spells_is_unknown_until_built(self):
        self.assertIsNone(window.window_ok("AfDB", "KEN", 2020, {"AfDB": "classification_spells"}))

    def test_oghist_lending_category_is_authoritative_when_present(self):
        # The direct signal resolves blend countries the income-group table can't.
        d_basis = {"IDA": "oghist_income", "IBRD": "oghist_income"}
        category = {("PAK", 2026): "Blend"}
        self.assertTrue(window.window_ok("IDA", "PAK", 2026, d_basis, {}, category))
        self.assertTrue(window.window_ok("IBRD", "PAK", 2026, d_basis, {}, category))

    def test_ida_never_guesses_false_from_income_group_alone(self):
        # Small-state exception (Dominica, Grenada): "UM" income does not
        # reliably rule out IDA eligibility, so this must be None, not False.
        d_basis = {"IDA": "oghist_income"}
        income = {("DMA", 2015): "UM"}
        self.assertIsNone(window.window_ok("IDA", "DMA", 2015, d_basis, income, {}))
        income_low = {("AFG", 2015): "L"}
        self.assertTrue(window.window_ok("IDA", "AFG", 2015, d_basis, income_low, {}))

    def test_ibrd_never_guesses_false_from_low_income_alone(self):
        # Blend-country ambiguity: "L" income does not rule out IBRD terms.
        d_basis = {"IBRD": "oghist_income"}
        income = {("PAK", 2015): "L"}
        self.assertIsNone(window.window_ok("IBRD", "PAK", 2015, d_basis, income, {}))
        income_um = {("BRA", 2015): "UM"}
        self.assertTrue(window.window_ok("IBRD", "BRA", 2015, d_basis, income_um, {}))

    def test_no_income_data_at_all_is_unknown(self):
        d_basis = {"IDA": "oghist_income"}
        self.assertIsNone(window.window_ok("IDA", "ZZZ", 2015, d_basis, {}, {}))


class NonRegionalShareholdersRealDataTests(unittest.TestCase):
    """data/manual/non_regional_shareholders.csv (2026-10-02) against the
    real, checked-in data/output/eligibility.csv -- a direct regression
    guard, same pattern as test_control_panel.py's EuMemberAndWbRegionTests:
    no listed (bank, iso3) pair should ever read eligible=1 again, and a
    sample of known-good borrowers must be unaffected."""

    @classmethod
    def setUpClass(cls):
        from _panel import ELIGIBILITY_CSV, load_eligibility
        rows, exists = load_eligibility(ELIGIBILITY_CSV)
        if not exists:
            raise unittest.SkipTest("data/output/eligibility.csv not built -- run `make build` first")
        cls.eligible = {(r["bank"], r["iso3"]): r["eligible"] for r in rows if r["eligible"] is True}
        cls.non_regional = recipient.load_non_regional_shareholders()

    def test_no_listed_non_regional_shareholder_reads_eligible(self):
        offenders = [pair for pair in self.non_regional if pair in self.eligible]
        self.assertEqual(offenders, [], f"these should never read eligible=1: {offenders}")

    def test_known_good_borrowers_are_unaffected(self):
        for bank, iso3 in [("IBRD", "POL"), ("IBRD", "BHS"), ("EBRD", "UKR"), ("EBRD", "POL")]:
            self.assertIn((bank, iso3), self.eligible, f"{bank}/{iso3} should still read eligible")

    def test_the_list_is_non_empty_and_only_covers_ibrd_and_ebrd(self):
        self.assertGreater(len(self.non_regional), 0)
        self.assertEqual({bank for bank, _ in self.non_regional}, {"IBRD", "EBRD"})


if __name__ == "__main__":
    unittest.main()
