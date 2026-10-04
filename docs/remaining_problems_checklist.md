# Remaining problems checklist

Everything left open after the 2026-09-21 sessions (two-output split, then
Phase 1-4 automation). Organized by priority, each item says exactly what to
look for, where, and how to decide you're done. `docs/manual_data_checklist.md`
covers *new* research (the five components' remaining phases); this file
covers *fixing what's already flagged* — the logged contradictions, the
still-undated rows, and the deliberately deferred pieces.

**Updated 2026-09-27** (see `docs/coding_decisions.md`, both entries that
day): Component E now defaults an unlogged bar to "not evidenced," and
Component D (`window_ok`) now reads a corrected, far more complete World Bank
source. Both make `eligible`/`eligible_strict` resolve confidently far more
often — which is *why* the contradiction count below grew from 24 to 123,
not because more went wrong. See "Priority 1" for what's actually new.

**Updated 2026-09-30 — Priority 1 is done.** All 220 revealed-eligibility
violations (123 contradiction + 97 not-yet-coded, as of 2026-09-28) are now
resolved or formally accepted: 25 rows got a real `mandate_spells.csv` fix
(Group A's bar-scope items turned out to be a different finding than
expected — see below — plus a new EIB mandate-spell gap this pass found and
fixed), and the remaining 195 are logged in the new `data/manual/accepted_
revealed_exceptions.csv` with a specific, researched reason each.
`make validate` passes cleanly. Full account: `docs/coding_decisions.md`,
2026-09-30. Groups A-E below are kept for their research trail, each marked
with its actual outcome (not always what this checklist originally guessed).

## How to use this

Work top to bottom; priority 1 is the only thing that blocks `make validate`
from passing (`check_revealed.py` exits non-zero while any contradiction
exists). Priorities 2-4 are real gaps but don't fail anything — they just
mean some `eligible`/`recipient_status` cells stay `None` instead of
resolving. After each fix: `make build && python3 scripts/check_revealed.py`,
then commit that one fix with a message naming the row(s) it resolves. Don't
batch unrelated fixes into one commit — if a contradiction turns out wrong,
you want `git bisect`/`git log` to point at exactly the row that changed.

## Priority 1 — the 123 logged contradictions

Full list: `data/output/reports/revealed_violations.csv`, `kind=contradiction`.
Every one of these is a dyad-year where the panel says "ineligible" but the
scraper's own project data shows real lending — a direct conflict, not a
gap. Grouped by what's actually being asked:

### Group A — Afghanistan and Myanmar bar-event scope (6 rows) — resolved as an understood exception, 2026-09-30

| Row | Issue |
|---|---|
| `IDA,AFG,2022` / `2024` / `2025` / `2026` | `bar_events.csv`'s IDA/AFG row (start `2021-08`, no end date) is open-ended and may be too broad |
| `IDA,MMR,2025` / `2026` | No `bar_events.csv` row exists for IDA/MMR at all yet |

**Resolved, differently than expected.** Checked directly against the
scraper's own raw IDA project data: every one of these rows' observed
projects is an `IDA Grant` (not a loan) in an explicitly humanitarian/
emergency sector — Emergency Food Security, Health Emergency Response,
Education Emergency Response, Community Resilience. Web research confirms
the World Bank did suspend direct government-channel disbursements (as
`bar_events.csv` already correctly codes) but separately approved
channeling IDA-funded humanitarian financing through international
organizations/alternative implementation arrangements, which continued
through the suspension period. **No `bar_events.csv` edit made** — the
suspension itself is accurately coded; `bars.py`'s schema just doesn't
distinguish a government-channel bar from a parallel humanitarian channel.
Logged in `data/manual/accepted_revealed_exceptions.csv` as
`humanitarian_channel_exception_confirmed`. See `docs/coding_decisions.md`,
2026-09-30.

### Group B — AsDB Malaysia and Brunei (6 rows) — resolved as an accepted exception, 2026-09-27

| Row | Issue |
|---|---|
| `AsDB,BRN,2008` | Brunei classified `non_borrowing` in `recipient_status.csv` (not a DMC), but one observed project |
| `AsDB,MYS,2006/2014/2021/2022/2023` | Same — Malaysia is a well-known ADB graduate, but shows repeated observed lending after graduation |

**Resolved.** All six checked directly against `../mdbs_scraper_corrected/
output/adb_projects.csv`: every one is `financing_instrument = "Technical
Assistance"`, $50,000-$3.2 million (e.g. "Support of Improved Economic
Modeling," a BIMP-EAGA/IMT-GT subregional cooperation grant), matching
ADB's own graduation policy's exception for "exceptional, non-regular
assistance." No data change; `recipient_status.csv` stands, and these rows
stay in `mdb_panel.csv` via `eligibility_basis = revealed`. See
`docs/coding_decisions.md`, 2026-09-27.

### Group C — EBRD Montenegro and Kosovo (10 rows) — root cause confirmed, 2026-09-27; extended to Turkey/Egypt/Mongolia/Russia, 2026-09-30

| Row | Issue |
|---|---|
| `EBRD,MNE,2002` / `2003` / `2005` | Observed EBRD lending attributed to Montenegro predates its 2006 independence |
| `EBRD,XKX,2005-2011` (7 rows) | Observed EBRD lending attributed to Kosovo predates its 2008 independence and EBRD's 2012 SEMED addition |

**Confirmed, not fixable at the eligibility layer.** Checked the actual
projects (`../mdbs_scraper_corrected/output/ebrd_projects.csv`): Kosovo's
rows are essentially all *regional* Western Balkans facilities (the Local
Enterprise Facility, the Western Balkans MSME Framework, the Regional Trade
Facilitation Programme) reaching a Kosovo-based partner bank (NLB Prishtina,
Raiffeisen Bank Kosovo, FINCA Kosovo) years before Kosovo's own 2012 EBRD
accession -- a regional facility's own approval is a different, earlier
process than an individual country's accession. Montenegro's rows are real
sovereign/near-sovereign lending (airport and road rehabilitation, bank
recapitalisation) dated 2002-2005, entirely before its 2006 independence,
when these operations were legally within Serbia and Montenegro -- the
scraper's data evidently attributes them by current geography, not the
entity that was the actual EBRD recipient at the time. This is a country-
universe/state-succession question (decision 6, still open), not a wrong
date or missing spell -- `mandate_spells.csv`/`bar_events.csv` can't fix it.
`mdb_panel.csv` correctly keeps all 10 rows via `eligibility_basis =
revealed`. See `docs/coding_decisions.md`, 2026-09-27, for the full account.

**2026-09-30 update: the same regional-facility-attribution mechanism
explains `EBRD,TUR,2004-2007`, `EBRD,EGY,2009`, `EBRD,MNG,2004`, and
`EBRD,RUS,2017`** (see the former "still open" items below) — checked
against the raw project data, every one is a regional CEE/SEE private-
equity fund or facility (Advent CEE III, Alpha CEE II/IV, the Balkan
Accession Fund, the European Fund for Southeast Europe, Green for Growth
Fund Southeast Europe) reaching a portfolio asset in that country years
before its own formal country-of-operations accession. All logged as
`regional_facility_attribution_confirmed` (or `state_succession_pre_
independence` for RUS, grouped with the sanctions-era MNE rows). See
`docs/coding_decisions.md`, 2026-09-30.

### Group D — Two single-instance findings (2 rows) — both resolved, 2026-09-30

| Row | Issue |
|---|---|
| `IBRD,BTN,2026` | The World Bank's current classification lists Bhutan as pure `IDA`, but one observed IBRD-attributed project in 2026 |
| `EBRD,RUS,2017` | Predates the earlier-logged 2014/2022 sanctions puzzle |

**Bhutan: confirmed genuinely blended, not a scraper mislabel.** Checked the
raw World Bank project data directly: Bhutan's "Dorjilung Hydroelectric
Power Project" is scraped as two rows for the same project — one
`funding_window=IBRD` ("IBRD Loan"), one `funding_window=IDA` ("IDA Credit;
IDA Grant") — a real blended IBRD+IDA operation despite Bhutan's general
country-level classification being pure IDA. Logged as `confirmed_blended_
financing_exception`.

**`EBRD,RUS,2017`: same mechanism as Group C above, not a bar-scope issue.**
The single observed project is "Alpha CEE IV," a regional Central/
Southeastern Europe/Caucasus/Central Asia/Russia/Turkey private-equity
fund-of-funds (EBRD's own disclosed project page, approved/disclosed
9 Nov 2016, signed 30 Jan 2017) — a regional-facility attribution, not a
bilateral new Russia investment breaching the 2014 curtailment. No
`bar_events.csv` edit made; logged under `state_succession_pre_
independence` alongside the Montenegro/sanctions-era rows. See `docs/
coding_decisions.md`, 2026-09-30.

### Group E — IBRD/IDA post-graduation residual lending (99 rows) — resolved as a class, 2026-09-27

`data/output/reports/revealed_violations.csv`, every `IBRD`/`IDA` row not
already in Group D. Appeared the moment `components/window.py` started
reading a direct, year-by-year lending category (`docs/coding_decisions.md`,
2026-09-27) instead of hedging to `unknown` whenever income group alone
couldn't rule a country in or out. The shape is consistent across nearly all
99 rows: a country's official World Bank lending category changes (almost
always IDA→IBRD/None, i.e. graduation) and the scraper's project data shows
one or a handful of operations in the same or a following year or two — e.g.
`IDA,IND,2014` (11 projects, India's own graduation year), `IDA,VNM,2017`
(11 projects), plus smaller counts for China, Georgia, Armenia, Montenegro,
North Macedonia, Serbia, Romania, Bulgaria, Türkiye, Moldova, Ukraine and
several others at their own graduation years.

**Resolved.** India (2014-2024) and Vietnam (2018-2024) spot-checked against
`../mdbs_scraper_corrected/output/ida_projects.csv`: both show real, large
(tens to hundreds of millions of USD), `funding_window=IDA`,
`financing_instrument` explicitly "IDA Credit" operations for a decade after
their own graduation year — not small residual amounts, not a scraper
mislabel. IDA's own graduation policy (World Bank/CGD sources, researched
live) confirms two real mechanisms: previously committed credits keep
disbursing over a multi-year project lifecycle, and large/strategic graduates
specifically get an individually negotiated "transitional support"
arrangement (India's own reported as "two-thirds of what it would have
received" over an "undetermined transition period" — not a fixed rule
anywhere, so not something to encode as a lookup). **Decision (user-
confirmed): accepted as a class**, the same way AsDB's Malaysia/Brunei rows
already were — no `window_ok`/`oghist_lending_category.csv` edit, no
per-country override built. `eligibility.csv`'s confident `False` for these
rows is correct per IDA's general rule; `mdb_panel.csv` already keeps every
one via `eligibility_basis = revealed`. See `docs/coding_decisions.md`,
2026-09-27, "IDA post-graduation contradictions."

## Priority 2 — 9 undated AIIB accession rows

`data/manual/accession_dates.csv`: Bahrain, Benin, Fiji, Hong Kong, Hungary,
Madagascar, Papua New Guinea, Romania, Rwanda. Searched for this session, no
source found with enough confidence to write a year down. Try AIIB's own
per-year "AIIB Approves Membership of ..." press releases
(`aiib.org/en/news-events/news/<year>/`) — the pattern that resolved the
other 36 rows. If you find a real, dated announcement, add it directly (keep
the existing `source` URL already on each row, just fill `accession_date`
and append to `note` — see `docs/coding_decisions.md`, 2026-09-21, "AIIB
accession gap-fill," for exactly how the other 36 were done this way without
triggering `merge_accession_dates.py`'s source-conflict protection).

## Priority 3 — 47 `recipient_status.csv` rows still marked `unknown`

**28 of the original 75 resolved 2026-09-27** (see `docs/coding_decisions.md`):
every `unknown` row that had any observed lending in `commitments.csv` was
checked directly against that bank's own raw project data and reclassified
`borrowing`, sourced to the observed lending itself — 15 AIIB, 4 CABEI, 2
CAF, 7 IsDB.

The remaining 47 (`grep ',unknown,' data/manual/recipient_status.csv`) have
no observed lending at all, so they don't affect the panel's output — only
its coverage. Still open-ended, not a fixed punch list — resolving one means
finding that bank's own real borrowing-vs-non-borrowing statement for that
specific country (the same methodology as `scripts/seed_recipient_status.py`).
Prioritize only if a specific country/bank pair matters to your analysis.

## Priority 4 — deferred by design, not forgotten

These were explicitly scoped out of the automation plan, not overlooked:

- ~~**EIB's External Lending Mandate**~~ — done 2026-09-27, see
  `docs/coding_decisions.md`. `mandate_spells.csv` now has 259 `EIB` ELM rows
  from the four EUR-Lex decisions the user supplied, plus 85 more from the
  ACP/Cotonou and OCT tracks (same day, second pass) that closed 346 of the
  418 "not yet coded" EIB dyad-years this gap had produced. **2026-09-30: 25
  more of the remaining 72 closed** with a real, sourced fix — a single-year
  2000-2003 Lomé IV-to-Cotonou transition gap for 14 ACP countries (EIB
  lending continued under Lomé IV's own financial protocol before Cotonou's
  1 April 2003 entry into force), Croatia's and Serbia's own pre-2007
  country-specific EIB mandates (Council Decisions 2000/688/EC and
  2001/778/EC respectively — this project had only seeded the later, 2007+
  regional decision), and the Maldives' one-off 2006 post-tsunami inclusion
  (European Parliament approval, 17 Jan 2006). What's left (47 rows:
  Switzerland/Norway/Andorra/Iceland's own-risk lending, confirmed directly
  against the decision texts to have no country-list coverage at all;
  Israel/Chile's post-2017-delegated-act removal) has no further country
  list to encode against and is logged in `data/manual/accepted_revealed_
  exceptions.csv` as `eib_own_risk_no_country_list`. See `docs/coding_
  decisions.md`, 2026-09-30.
- ~~**OGHIST calendar years 2023-2025**~~ — done 2026-09-27; turned out to be
  a stale source URL, not a real data gap. See `docs/coding_decisions.md`:
  `build_oghist.py` now reads the World Bank's `CLASS_hist` file, which
  covers every year 1988-2026 with a direct lending category, not just a
  current-year snapshot.
- **Component E's non-accrual evidence** (annual-report PDF parsing). Cut
  entirely from this session's plan — no `pdfplumber`, no
  `sources/annual_reports/*` infrastructure exists. This is genuinely the
  next big infrastructure investment if Component E needs to go beyond the
  ~20 hand-coded sanctions events already in `bar_events.csv`.
- **Decision 2 (AsDF split, specifically)** and **decision 6 (country
  universe/succession, `countries.csv`)** — architecture.md section 6, still
  open. (Decision 2's AfDB/ADF half, and decision 7's AfDB special-funds
  crosswalk, were both resolved 2026-09-24 — see `docs/coding_decisions.md`,
  "Decision 2 resolved for AfDB/ADF.") `docs/coding_decisions.md` records
  exactly what current code assumes in AsDF's and decision 6's absence.

## Deciding when a contradiction is actually resolved

A contradiction is resolved when you can point to a specific source that
either (a) confirms the current `bar_events.csv`/`recipient_status.csv`/
`mandate_spells.csv` row is wrong and changes it, or (b) confirms the
observed lending was a real, understood exception and you've logged that
understanding in `docs/coding_decisions.md`. It is **not** resolved by:

- Deleting or loosening a rule just to make the count go down — that's the
  exact failure mode `check_revealed.py` exists to catch (see the AIIB/CAF/
  small-state incidents this session, all real bugs the check caught).
- Leaving it silently uncoded — every row still needs a decision, logged.

If you genuinely can't find a primary source after a reasonable search, the
honest move is what this project has done throughout: leave the row coded
as-is, write down exactly what you tried and why it's still open, in
`docs/coding_decisions.md`. A documented, understood gap is not a failure —
an undocumented wrong guess is.

## Workflow: validate, commit, push

```
# after each fix:
python3 scripts/validate_manual.py
make build
python3 scripts/check_revealed.py      # confirm the count you targeted actually dropped
python3 -m unittest discover -s tests  # if you touched any components/*.py logic
git add <only the files that one fix touched>
git commit -m "..."                    # name the specific row(s)/bank(s) resolved
git push
```

Commit and push after each resolved item, not in one giant batch at the end
— the `docs/coding_decisions.md` entry for that fix is what makes a later
`git log` search ("why does EBRD/MNE 2003 show eligible now?") actually
answerable.

**One thing to check before your next commit, unrelated to any of the
above:** `git status` currently shows `data/manual/shares_snapshot_2026-08-25.xlsx`
as modified. Nothing in this session's scripts writes to that file (they
only ever open it read-only) — comparing cell contents directly, the
underlying data is unchanged, only the file's internal XML serialization
differs, consistent with some other application (Excel, Numbers, an OS
preview) having opened and re-saved it. Worth a `git diff --stat` check and
your own judgment call on whether to include it before you push.
