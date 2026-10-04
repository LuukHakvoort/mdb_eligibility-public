# Manual data checklist

Every row in this document needs something only a person can do: read a primary
source, exercise judgement, or make a decision the code can't make for you.
Nothing here is scraped. The pattern is the same one already working in
`../mdbs_scraper_corrected/online pulled data/`: you retrieve a file or a fact,
note where it came from, and the code checks it rather than trusting it
silently.

Organized by the plan's phase order (`docs/eligibility_data_collection_plan.md`
section 8). Check off a row's `status` as you go; this file is meant to be
edited over the life of the project, not written once.

**Two outputs, not one.** `data/output/membership.csv` (who is a
shareholder, and are they a recipient) and `data/output/eligibility.csv`
(could this bank have lent here) are separate, standalone files built by
separate scripts (`build_membership.py`, `build.py`) — see
`docs/coding_decisions.md`, 2026-09-21, "Two separate outputs." Component B
work below feeds both, but through different columns; don't assume a row you
enter for one automatically means the same thing in the other.

## Already handled — nothing needed from you here

- **Bank existence (Component A).** Drafted (`data/manual/bank_existence.csv`)
  with citations. Review it; only NDB's start-year choice (2015 existence vs.
  2016 first lending) is a genuine judgement call.
- **Structural bars, the sanctions half (Component E).** Drafted
  (`data/manual/bar_events.csv`) for Russia/Belarus/Afghanistan/Myanmar at
  World Bank/EBRD/NDB. Spot-check the dates.
- **Country-name normalisation.** Fixed upstream in the scraper
  (`mdbs_scraper_corrected` commit `854d58e`) after this repo's own review
  surfaced the gap. Nothing to do unless a new unresolvable name turns up.
- **Current shareholder/member lists and shares, all 14 banks.** Already
  assembled and sourced (`data/manual/shares_snapshot_2026-08-25.xlsx`) —
  see Phase 1 below for what still needs extending backward in time.

## Phase 1 — Membership (Component B)

### Already assembled: current shares and members for all 14 banks

A sourced capital-share/voting-power snapshot for every bank already exists —
`data/manual/shares_snapshot_2026-08-25.xlsx` (moved here from the scraper
repo's `online pulled data/`, see Part 2.1 of the plan). It gives, per bank, a
current-as-of member/shareholder list, capital and voting shares, and — in its
`Source_Map` sheet — the exact official document and table/note/schedule to
pull for a *different* year (e.g. CDB "Note 19(c)" of the annual financial
statements, IDB "Schedule I-4," EIB "Note H.1"). ADB, BADEA, CDB and EIB
already have two years each.

**This replaces most of what would otherwise be a from-scratch research task**
for the current member list and current shareholder weights across all 14
banks. What it does not give you is the full 2002–2026 time series — only
current-ish snapshots (2020–2026 depending on bank). Two things remain:

1. **Spot-check it.** I haven't verified any of its cited figures against the
   underlying document, only that the workbook is internally consistent (its
   own `QA_Totals` sheet: every institution's shares sum to ~100%). Pick two or
   three banks and confirm one row each against the cited URL before leaning
   on the rest.
2. **Extend it backward, bank by bank, using the exact roadmap `Source_Map`
   already gives you** — download the same named note/schedule from earlier
   years' annual reports. This is real work, but it's no longer "figure out
   where to even look" — that part is done. **Started 2026-09-24, CDB pilot
   done**: `scripts/annual_reports_cdb.py` fetches and parses CDB's own
   Note 19(c)/21(c) (the note *number* shifts year to year; found by
   content, not a fixed number), 4 real years so far (2018-2019, 2023-2024,
   `data/manual/annual_reports.csv` indexes the source documents). Real
   findings along the way, not assumed: `pdfplumber`'s `extract_tables()`
   doesn't work on these borderless statement tables (0 tables found);
   `extract_text()` + a regex line-parser does. Each financial-statement
   document actually contains *two* years (current + comparative prior
   year, confirmed live), doubling the yield per document once the parser
   correctly splits on the bare year-label line instead of assuming one
   year per document. QA: every detected year's capital shares sum to
   ~100%, and a hand-checked spot value (Jamaica, all 4 years) matches
   exactly. **EIB done, 3 real years** (2010, 2019, 2024 —
   `scripts/annual_reports_eib.py`): a genuinely different parser than
   CDB's was needed — EIB's table gives raw EUR amounts (capital share
   computed against the table's own Total row) and, confirmed real, older
   documents use space-grouped numbers with no other column delimiter,
   which a line regex can't parse reliably. Rewritten to use
   `pdfplumber.extract_words()`'s x-positions instead — see
   `docs/coding_decisions.md` for the real gap measurements this was based
   on. EIB has no per-member voting-power percentage at all (a real
   structural fact, not a gap — `Source_Map`'s own caveat). **BADEA, CABEI,
   NDB also done** (`scripts/annual_reports_badea.py`/`_cabei.py`/`_ndb.py`)
   — real per-bank quirks found and fixed in each (BADEA's long official
   country names; CABEI's two different percentage concepts, used the
   source's own self-declared subscribed-capital share, not a re-derived
   one; NDB's two-column slide layout and correctly-excluded prospective
   members) — see `docs/coding_decisions.md` for the full account of each.
   **IDB and CAF both blocked**: `publications.iadb.org`/`iadb.org` return a
   real Cloudflare bot-challenge (`cf-mitigated: challenge`); `caf.com`
   returns an Incapsula bot-challenge page disguised as a `200 OK` (checked
   the actual response body, not just the status). Neither is a
   user-agent issue — no plain HTTP client gets through either, and this
   project has never used a JS-executing browser (`docs/architecture.md`'s
   own "Deliberately not built" list excludes Playwright explicitly). Both
   left open. Also fixed while wiring these three in: `build_shareholders_panel.py`
   was silently duplicating rows whenever a bank had both a workbook
   snapshot *and* a fresh extraction for the same year — now deduplicates,
   preferring the more independently-auditable source and reporting every
   real disagreement (not just the exact duplicates) to
   `data/output/reports/shareholders_panel_conflicts.csv`.
   **AfDB voting power also done** (`scripts/annual_reports_afdb.py`,
   1 real year so far — 30 Nov 2024): a different document family again —
   AfDB's monthly "Distribution of Voting Powers by Executive Director"
   statement, which publishes `voting_power_pct` only, no capital-
   subscription amounts (left blank with a note, same honest-null pattern
   as EIB). The real parsing problem here wasn't a new table layout but a
   redundant one: every row repeats each country twice (once in a plain
   alphabetical block, once inside an Executive-Director-constituency
   block), and no fixed x-position threshold reliably separated the two
   across every row (tried twice, both failed for documented reasons — see
   `docs/coding_decisions.md`). Fixed by extracting every candidate
   regardless of position and deduplicating by name instead. Final result:
   81 rows, voting powers sum to exactly 100.00%, 0 disagreements between
   the two redundant readings. AfDB-proper's *capital* share and ADF's own
   shares (a separate document series, not yet fetched) remain open.
   **EBRD's shares history now goes all the way back to 2000**
   (`scripts/annual_reports_ebrd.py`, 14 real years, 2000-2013 — the
   Wayback route already covered 2014-2025). Checked live before building
   anything: the Wayback CDX API returns zero captures of EBRD's
   shareholders page before Dec 2014, a confirmed dead end, so this uses
   EBRD's own annual financial-statement PDFs instead (the plan's own
   documented fallback). The best-shaped document found all session — one
   table gives *both* capital share and voting share directly, no
   word-position clustering needed — but still needed four real per-year
   fixes found by inspecting the actual sums, not assumed: one year's
   capital columns carry a decimal place; one year's total-votes cell has
   a corrupted glyph baked into the source PDF itself (worked around by
   summing member rows instead of trusting the printed total); one year's
   table heading drops a letter; and 2000 alone has a genuine
   unattributable reserve row for shares pending reallocation after
   Yugoslavia's breakup. See `docs/coding_decisions.md` for the full
   account. 850 rows, every year within 99.9-100.1% of the document's own
   stated total.
   **IsDB's shares and voting power now cover 2011-2025**
   (`scripts/annual_reports_isdb.py`, 15 real years, 57 members from 2016) —
   the one bank whose Wayback route only ever gave accession dates. Both a
   capital and a voting share are published every year. The real work was
   layout drift (eight different print layouts of the same annex across 15
   reports, including one where director names are glued onto the front of
   rows, and one where the capital table has amounts but no share counts);
   every year reconciles to the document's own printed Sub-Total within 0.1%
   for both shares and votes. Shares are recomputed from raw counts as a
   share of members' subscribed capital (the printed % is relative to
   authorized capital, including an unallocated reserve, in some years).
   Extended to 2006-2010 the same day (2002-2005's reports carry no annex). See `docs/coding_decisions.md`.
   **IBRD's shares and votes now cover every fiscal year FY2003-FY2026**
   (`scripts/annual_reports_ibrd.py`, 24 years, 182-189 members): IBRD files
   its annual reports on SEC EDGAR, so this was one uniform table per year, not
   a per-year hunt for PDFs. Two user decisions recorded in
   `docs/coding_decisions.md`: the User-Agent now carries the project contact
   (sec.gov refuses requests without one), and a June-30 position takes the
   calendar year of its date (FY2024 -> 2024). **IDA now covers FY2005-FY2026**
   (`scripts/annual_reports_ida.py`) from its own financial statements — and
   checking it exposed that **the workbook's `IDA` sheet is IBRD's numbers
   relabelled** (all 189 rows equal IBRD's FY2026 shares; the US is 15.98% there
   vs 9.52% of votes in IDA's audited statement). The panel no longer reads that
   sheet. IDA's "capital share" is its share of subscriptions and contributions
   committed (IDA has no share capital). FY2006-2007 were read by OCR.
   **IDB FY2022-FY2025 now covered** (`scripts/annual_reports_idb.py`, via its SEC filings — the
   Cloudflare-blocked bank has ordinary HTML annual reports on EDGAR; 48 members, exact reconciliation).
   IDB 2002-2021 still needs the manual PDF download.
   **ADB (`AsDB`) now covers every year 2002-2025** (`scripts/annual_reports_adb.py`, 61-69 members,
   from the Financial Report's OCR-8 statement) — each year's shares and votes sum *exactly* to the
   printed total. Kerning artifacts in the text layer (a space after the first digit) and one
   font-garbled page (2009, read by OCR) needed handling; see `docs/coding_decisions.md`.
   **AfDB now has a capital share too, 2005-2025** (`scripts/annual_reports_afdb_sec.py`):
   AfDB files its annual report on SEC EDGAR, with a per-member table of shares
   and votes at each 31 December (77-81 members, every year reconciled).
   **EDGAR also carries ADB (CIK 311669) and IDB (CIK 311670)** — IDB's own site is
   Cloudflare-blocked but its FY2022-25 annual reports on sec.gov are plain HTML.
   2002-2004 (plain-text filings) and ADF still open.
   **AIIB's shares now cover 2016-2024, with voting power published for
   2022-2024** (`scripts/annual_reports_aiib.py`): capital from each
   year-end financial statement's share-capital note (76 -> 98 members),
   voting from the annual report's voting-power appendix. 2016-2018 are
   scanned image-only PDFs and were read by OCR (`scripts/ocr.py`), with a
   per-row double check on every misreadable digit (`docs/coding_decisions.md`).
   Voting power is *not* capital share (China 2024: 30.69% vs 26.57%);
   the Article 28 formula was checked against the three published years
   (mean error 0.019pp, but Iran 0.55pp off from suspended votes on overdue
   payments) and kept in a separate file (`aiib_voting_computed.csv`) rather
   than filling 2019-2021's `voting_power_pct` — your call whether to use
   it. Also found: AIIB's own membership dates (2022 annex, 92 members)
   resolve 8 of 9 undated members but disagree with 15 existing dated rows
   (different meaning: effective date vs approval/opening) — see
   `docs/coding_decisions.md`; nothing overwritten.
   **2026-09-25 -- with the hand-downloaded reports, the shares history is now
   essentially complete** (`docs/coding_decisions.md`, newest entry): CDB 2002-2025,
   IDB 2002-2021, CAF 2002-2022 (capital only), BADEA 2002-2019 *with voting power*
   (its annex prints votes), NDB 2015-2024, IsDB and AfDB 2002-2004, EIB 2002-2020.
   Later that day: EIB complete 2002-2025, AIIB 2025, EBRD voting 2016-2025, IDA FY2002/FY2004,
   BADEA 2020-2022. Open: CABEI 2002-2023 and 2025 (bcie.org migrated to a JS site; needs
   hand download), IDB 2017 (corrupt file), CAF 2023/2025, BADEA 2023-2025 votes, IsDB 2005, IDA
   FY2003, IBRD FY2002, ADF/AsDF (not separate bank codes). Panel: 19,219 rows.
   Priority order beyond IDB/CAF, since these are the banks whose
   membership genuinely moved inside 2002–2026 (collection plan §3.2):
   the other eight as time
   allows — for most of those eight, the current snapshot plus a handful of
   known accessions (Montenegro 2007, South Sudan 2012, Kosovo where
   recognized) may already be enough.

| Bank | Snapshot as-of | What still moved inside 2002–2026 | Status |
|---|---|---|---|
| AIIB | 30 Jun 2024 | 57 founding members (2016) → 111 approved; needs the earliest years filled in | mostly done — 41/50 dated (30 founding members at the 2016 opening; 6 from specific AIIB press releases 2017-2023). 9 remain undated (Bahrain, Benin, Fiji, Hong Kong, Hungary, Madagascar, Papua New Guinea, Romania, Rwanda) — searched for, no source found with enough confidence to write down |
| NDB | 31 Dec 2025 | BRICS-5 (2015) → +Bangladesh/UAE (2021), Egypt (2023), Algeria (2025), Uzbekistan (2026) | done — all 9 members dated and sourced (ndb.int/about-ndb/members) |
| EIB | 31 Dec 2023 & 2024 | Tracks EU membership: 2004, 2007, 2013 enlargements; UK exit 2020 — these dates are public record independent of any annual report | done — `data/manual/eu_membership.csv`, all real dates, `scripts/seed_eu_membership.py` |
| CAF | 31 Dec 2024 | Steady accession of new shareholder countries | not started |
| ADB | 31 Dec 2020 & 2021 | Close to static; already has two years | not started |
| BADEA | current | Non-Arab AU membership, close to static | done — all 44 members dated and sourced (badea.org/who-we-serve) |
| CABEI | current | Close to static | started — 12 of its members dated and sourced (bcie.org/paises/xx), including a real judgement call already logged: Mexico is non-regional and does not borrow |
| EBRD | 2023–2026 | Close to static — a handful of accessions | done — 73/73 members dated (Wayback reconstruction of ebrd.com's own "Date joined" column, `scripts/shares_wayback_ebrd.py`) |
| IsDB | 2023–2026 | Close to static | mostly done — 57/71 dated (Wayback reconstruction of isdb.org's member_countries.json, `scripts/shares_wayback_isdb.py`); the other 14 are non-members with real observed lending, not a gap (see the "Borrowing status" section below) |
| AfDB, CDB, IBRD, IDA, IDB | 2023–2026 (varies) | Close to static — a handful of accessions, per the collection plan's own "low effort" tier | IDB: 26 borrowing / 22 non-borrowing members sourced (iadb.org's own published lists), but *accession dates* specifically still not entered — this is `recipient_status`, a different fact from `accession_date`; the rest not started |

Progress so far lives directly in `data/manual/accession_dates.csv`; `scripts/merge_accession_dates.py` folds in hand-edited work from a CSV or Numbers file without disturbing rows already there — use it instead of hand-copying rows across whenever accession research happens somewhere other than the CSV directly. (`data/extracted/commitments.csv` has been rebuilt and every row already carries an `earliest_observed_year` hint — the "narrow it down" step this paragraph used to describe as future work is already done.)

### Borrowing status, not bare membership — done, 2026-09-21

Researched and written to `data/manual/recipient_status.csv` (449 rows, all
nine banks whose `b_basis` in `data/manual/banks.json` is
`needs_recipient_research`: AfDB, AsDB, IDB, IsDB, CAF, CDB, AIIB, NDB,
CABEI — a slightly different, more precise set than this section originally
named, per `docs/architecture.md` section 2's own per-bank table).
`data/output/membership.csv` (`scripts/build_membership.py`) is the finished
output that combines this with bare membership and shareholding into a
standalone, documented file — see `docs/coding_decisions.md`, 2026-09-21
entries, for every source and the two corrections (AIIB, CAF) that
`check_revealed.py` caught and forced. Remaining genuine gaps, left `unknown`
rather than guessed: CABEI's 7 extra-regional members, several AIIB
high-income/ambiguous members, IsDB's Gulf-state founding members — a future
pass could research these specifically if the thesis needs them resolved.

### Wayback reconstruction — done for EBRD and IsDB; AIIB is a confirmed dead end

`scripts/wayback.py` plus `shares_wayback_ebrd.py`/`shares_wayback_isdb.py`
are built and have already run: EBRD 73/73 members dated, IsDB 57/71.
**AIIB's member page is client-side JavaScript-rendered** — checked live
across 2017-2026 snapshots, every one has an empty table where the member
data should be, since Wayback's crawler never executes the page's JS. Not
fixable by this route; AIIB's remaining accession gaps were closed instead
via its own annual-report/press-release text (see the Phase 1 table above).

## Phase 2 — Geographic mandate (Component C) — done, 2026-09-21, except EIB's external mandate

All ten `trivial_region` banks (IBRD, IDA, AfDB, AsDB, IDB, IsDB, CAF, CDB,
NDB, CABEI, and **AIIB**, moved here after its own FAQ turned up "any member,
no income or regional gate") mirror Component B directly — no research
needed, see `docs/coding_decisions.md`.

| Bank | Status |
|---|---|
| EBRD | done, mostly — `data/manual/mandate_spells.csv` covers the six well-documented expansion cohorts (Mongolia 2006, Turkey 2009, 2012 SEMED round, 2024 Sub-Saharan Africa/Iraq cohort); the founding Central/Eastern European and former-Soviet cohort falls back to its own EBRD membership date (a sourced choice, not a guess — see `scripts/seed_mandate_spells_ebrd.py`'s docstring for why it wasn't individually re-researched) |
| EIB | done, 2026-09-27 — `data/manual/eu_membership.csv` (in-EU case) plus `mandate_spells.csv`'s 264 `EIB` rows (`scripts/seed_mandate_spells_eib.py`), read directly from the four EUR-Lex decisions the user supplied, covering the External Lending Mandate's four historical regimes (2000-2006, 2007-2013, 2014-2020, 2021+ approximated). A country outside every regime's own annex for that year is still `None`, not a guessed False — see `docs/coding_decisions.md`, 2026-09-27, for exactly what's approximated (2021+) and what's left unresolved (countries only ever "potentially," not "actually," eligible in a given regime). |
| BADEA | done — computed (AU member AND NOT Arab League member) from `data/manual/au_membership.csv`/`arab_league_membership.csv`, both real, dated, complete rosters |

## Phase 3 — Window criteria (Component D) — done for IBRD/IDA; simplified elsewhere

| Bank | Status |
|---|---|
| IBRD, IDA | done, full 2002-2026 coverage — `scripts/build_oghist.py` fetches and parses the World Bank's `CLASS_hist` file (`ddh-openapi.worldbank.org/resources/DR0095347`), a single historical panel with both income group and a direct IDA/IBRD/Blend lending category for every year 1988-2026. **The 2023-2025 gap this row used to describe wasn't a real gap** — the old `OGHIST_URL` had gone stale (the Bank moved its published files elsewhere; refetching it returned byte-identical FY2023-capped content) — see `docs/coding_decisions.md`, 2026-09-27, for the verification (0 mismatches against the old source on 4,649 overlapping rows) before switching. Two known, deliberate hedges remain in `components/window.py` for the rare row without a direct lending category (never a guessed False): small-state IDA exception, blend-country IBRD ambiguity. |
| AfDB, AsDB, IsDB | simplified, not researched — `window_ok=1` unconditionally for confirmed recipients (`no_formal_window`) for all three. AfDB's ordinary-vs-concessional (ADF) split (decision 2, resolved 2026-09-24, merged back into one AfDB code 2026-09-28 — see `docs/coding_decisions.md`) lives as commitments-level columns, not a separate eligibility window. AsDB/AsDF stays combined (decision 2 unresolved there, blocked on scraper-side `funding_window` coverage, not a judgement call). |

Non-accrual status for Component E (below) is a different, still-open thing
— don't confuse it with this section's income/creditworthiness window.

## Phase 4 — Structural bars, the non-accrual half (Component E)

The sanctions events are already drafted (see top of this file). Non-accrual
status is different: it's disclosed per bank, per year, in a financial
statement note, and I don't have a citable date for any specific country
without reading that note. While you're pulling annual reports for capital
tables (Phase 1), also flag the page with the non-accrual list — the
collection plan's own advice is to do both passes over the same PDF at once.

Recurring cases already named in the collection plan §6, with blank rows
waiting in `bar_events.csv`: Zimbabwe, Sudan, Somalia, Syria, Eritrea. Add
rows for any other country you find; the schema is `bank, iso3, event_type,
start_date, end_date, source, note`.

**The one rule that matters here**: a country in arrears but still receiving
some lending is a decision, not a bar. Only code `barred` when the annual
report explicitly states new commitments were suspended — the revealed-
eligibility check will catch you if this is coded wrong, since any bank that
actually lent to a "barred" country/year will show up as a contradiction the
moment you run `make validate`.

## Phase 5 — the estimation panel is now built (2026-09-27)

`data/output/mdb_panel.csv` (`make panel`, `scripts/build_mdb_panel.py`) now
exists: 17,726 eligible-or-revealed dyad-years, lending outcomes attached
(project counts, USD nominal and constant-2025 amounts, zero-filled where
eligible but quiet). This unblocked mostly on its own, in two passes the same
day — see `docs/coding_decisions.md`, 2026-09-27 (both entries): first,
Component E's not-evidenced default (`eligible = 1` resolved for 15,735 rows
instead of 126); then, once the user's already-supplied EIB/EUR-Lex PDFs and
World Bank income-guidelines PDFs were picked up, EIB's External Lending
Mandate got built and the IBRD/IDA 2023-2025 window gap turned out to be a
stale source URL, not a real gap — `eligible = 1` is now 17,044, `unknown`
down to 4,231. What's still worth your input, in priority order:

1. ~~**123 logged contradictions**~~ — **done, 2026-09-30.** All 220
   revealed-eligibility violations (123 contradiction + 97 not-yet-coded)
   are now resolved: 25 got a real `mandate_spells.csv` fix (a Lomé IV-to-
   Cotonou transition gap, Croatia's and Serbia's own pre-2007 EIB country
   mandates, the Maldives' 2006 post-tsunami inclusion), and the remaining
   195 are formally logged in `data/manual/accepted_revealed_exceptions.csv`
   with a specific, individually-researched reason each (not a blanket
   "leave it" — several, like Afghanistan/Myanmar's humanitarian-channel
   financing and Bhutan's genuinely blended IBRD+IDA project, were
   newly confirmed this pass, not just carried forward). `check_revealed.py`
   now distinguishes an "accepted exception" from a genuinely new,
   unexplained violation, so `make validate` passes cleanly while still
   catching a real future bug. Full account: `docs/coding_decisions.md`,
   2026-09-30; row-by-row detail: `docs/remaining_problems_checklist.md`.
2. **75 `unknown` recipient_status rows** (priority 3 in `docs/remaining_
   problems_checklist.md`) — only matters if a specific bank/country pair is
   needed for your analysis. Not touched by this pass.

Neither blocks `make panel` from running; they only mean some dyad-years stay
out of the `eligible = 1` grid (or are only in the panel via revealed
lending) until resolved.

## Not needed from you

- **OECD CRS bulk files.** Located and downloaded in the sibling repo as of
  2026-09-20 (`../mdbs_scraper_corrected/data/external/oecd_crs/`), checked
  directly this session for this repo's purposes: covers only 5/14 banks as
  "donors," and the sibling repo's code exposes no income-group or
  non-accrual field at all — built purely to measure a possible early-year
  project-count backfill for ADB/AfDB/IsDB, a scraper-completeness question,
  not an eligibility-judgement source. Not a fit for Components B-E; not
  worth re-investigating.
- **Currency conversion rates.** The scraper's `reference.py` already
  maintains IMF FX rates + FRED deflator data if a later analysis stage needs
  constant-USD comparisons. The eligibility panel itself doesn't need this —
  components B-E are membership/mandate/window/bar flags, not dollar amounts.

## Status legend

Update the `status` you'd naturally track per row/table as you go: `not
started` / `sources identified` / `data entered` / `reviewed`. This file has
no enforcement of its own — `make validate`'s four checks are what actually
catch a mistake, not this checklist.
