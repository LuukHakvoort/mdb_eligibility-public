# MDB Eligibility Dataset

## What this repo does

Builds `data/output/eligibility.csv`: a mapping from every
(multilateral development bank, country, year) triple to whether that bank
*could have* lent to that country in that year.

This feeds a thesis testing whether MDBs allocate lending according to the same
organisational logic. The eligibility panel is a **sample restriction**, not a
covariate: dyad-years where lending was structurally impossible are dropped, so
that observed zeros represent genuine decisions not to lend rather than
institutional mandates.

Getting this wrong invalidates the thesis. A bank that appears to follow a
different allocation logic purely because its membership roster differs is a
false positive. Accuracy matters far more than coverage or speed here.

## Read these first

- `docs/eligibility_plan.md` — the full data collection plan. Authoritative on
  sources, per-bank rules, and phasing.
- `docs/methods_section.md` — why the panel is constructed this way.
- `docs/reference_conventions.md` — conventions derived from the existing
  project-level scraper at `../mdbs_scraper_corrected/`. Follow these.
- `docs/coding_decisions.md` — running log of judgement calls. **Append to this
  whenever you make one.**
- `docs/data_sources.csv` — one row per raw external dataset used anywhere in
  the pipeline: publisher, URL, version, access date, license, where it lives,
  what reads it. The thesis-facing rendering of the same rows is
  `../Final dataset/codebook/data_sources.md`. This is the source of truth;
  update it (not just the rendering) when a new raw source is added.

## Three outputs, not one

This repo produces three separate, standalone files — a membership list, an
eligibility list, and the estimation panel built from it — built by separate
scripts from shared inputs, not the same computation exposed twice. The first
two answer different questions and must not be conflated: see
`docs/coding_decisions.md`, 2026-09-21, "Two separate outputs," for the bug
that happened the one time they were.

### `data/output/membership.csv` — who is a shareholder, and are they a recipient

Built by `scripts/build_membership.py`. One row per (bank, iso3, year):

| Column | Type | Notes |
|---|---|---|
| `bank` | str | Canonical code, see below |
| `iso3` | str | ISO 3166-1 alpha-3 |
| `year` | int | 2002–2026 |
| `member` | bool | Bare shareholder/membership status. Not filtered to recipients — Germany belongs here as an AIIB member with `member=1`. |
| `capital_share_pct` | float | Nullable |
| `voting_power_pct` | float | Nullable |
| `accession_date` | str | Nullable |
| `recipient_status` | bool | Could this bank actually lend here — distinct from `member` on purpose. Germany's `recipient_status=0`. |
| `member_source`, `recipient_source` | str | Citations |
| `note` | str | Free text |

### `data/output/eligibility.csv` — could this bank have lent here

Built by `scripts/build.py`. One row per (bank, iso3, year):

| Column | Type | Notes |
|---|---|---|
| `bank` | str | Canonical code, see below |
| `iso3` | str | ISO 3166-1 alpha-3 |
| `year` | int | 2002–2026 |
| `bank_exists` | bool | Component A |
| `member` | bool | Component B — **recipient status** (`membership.csv`'s `recipient_status` column), not bare membership. The column name matches this project's original schema; the value it holds does not come from bare shareholding. |
| `in_mandate` | bool | Component C |
| `window_ok` | bool | Component D |
| `barred` | bool | Component E, defaulted to `0` where no `bar_events.csv` row exists (see `barred_evidenced`) |
| `barred_evidenced` | bool | `1` if E was actually resolved from a `bar_events.csv` row, `0` if defaulted |
| `eligible` | bool | `A & B & C & D & ~E`, using the defaulted `barred` above -- this is the column to filter the panel on |
| `eligible_strict` | bool | Same formula, but E stays `null` (not defaulted) wherever `barred_evidenced = 0` -- the fully-conservative cut, mostly `null` since only ~20 bar events are logged (docs/coding_decisions.md, 2026-09-27) |
| `member_since` | int | Nullable |
| `source` | str | URL or short citation |
| `note` | str | Free text |

Keep the five components as separate columns. Never collapse them into a single
hand-coded flag — separate columns make errors traceable and allow robustness
checks that relax one condition at a time.

### `data/output/mdb_panel.csv` — the estimation panel

Built by `scripts/build_mdb_panel.py` (`make panel`). One row per (bank,
recipient country, year), restricted to `eligibility.csv`'s `eligible = 1`
rows plus any dyad-year the rules still miss but `commitments.csv` shows real
lending for (`eligibility_basis = revealed` — never dropped, per the
revealed-eligibility principle). Zero-filled where eligible but no observed
lending (`any_lending = 0`), not dropped — see `docs/coding_decisions.md`,
2026-09-27. USD amounts (`usd_nominal_total`, `usd_2025_total`) are joined
from the scraper's own `dyad_country_year.csv`, not re-derived here, for
every bank including AfDB. AfDB's own ordinary-vs-concessional split is four
extra columns (`afdb_ordinary_n`/`_usd`, `afdb_concessional_n`/`_usd`, blank
for every other bank) from `data/extracted/afdb_window_breakdown.csv`
(`scripts/build_afdb_window_breakdown.py`) — see `docs/coding_decisions.md`,
2026-09-28, for why this replaced treating AfDB/ADF as two bank codes.
`capital_share_pct`, `voting_power_pct`, `recipient_status` come straight
from `membership.csv`.

**PPP-adjusted lending** (`ppp_2025_total`, added 2026-10-04): the scraper's
constant-2025 international-dollar amount, same deflator as `usd_2025_total`,
via the GDP price-level ratio (not `PA.NUS.PPP`). Blank, not 0, where the
dyad-year is unpriced (any unpriced project) or falls after 2025 (the
deflator has no 2026 value). The USD columns write 0 for 2026 lending, which
is a data gap, not zero lending: see docs/coding_decisions.md, 2026-10-04.

### `data/output/mdb_panel_with_controls.csv` — the panel with covariates

Built by `make controls` (`scripts/build_control_variables.py` ->
`build_project_breakdown.py` -> `merge_control_panel.py`). `mdb_panel.csv`
left-joined with economic/cultural/governance/geographic/"liberal" control
variables (`data/extracted/control_variables.csv`, country-year, from
`../Control variables/datasets/` — a sibling, non-git-tracked folder, see
`docs/coding_decisions.md`, 2026-09-27) and a project sector/instrument-type/
sovereign-status breakdown (`data/extracted/project_breakdown.csv`,
bank-country-year, re-aggregated from the scraper's own project data — no new
source). Two more control columns, `eu_member` (recipient's EU status that
year — a **closed roster**, always `1`/`0`, never blank) and `wb_region`
(World Bank region classification, static per country), added 2026-09-28 —
see `docs/coding_decisions.md` for their sourcing. Row count always equals
`mdb_panel.csv`'s own (a left join, never a filter); a blank control-variable
cell means that source had no value for that country-year, never guessed or
interpolated. Also written, identically,
to `../Control variables/output/mdb_panel_with_controls.csv`. Needs
`pandas`/`pyreadstat` installed (`pip install pandas pyreadstat`) — the only
part of this project that uses pandas rather than the plain-`csv` convention
everywhere else. `scripts/report_control_coverage.py` reports per-column
coverage to `data/output/reports/control_coverage.csv` (and, with
`--by-year`, a `(column, year)` breakdown too — `make controls` writes this
to `data/output/reports/control_coverage_by_year.csv`).

**Added 2026-09-30** (see `docs/coding_decisions.md` for the full judgement
calls): `ucdp_armed_conflict`/`ucdp_war`/`ucdp_conflict_intensity` (UCDP/PRIO
Armed Conflict Dataset v26.1) and `banking_crisis` (Laeven & Valencia's
Systemic Banking Crises Database 2026), each with a `_t1` lag
(`scripts/merge_conflict_crisis_lags.py`, an additive step run right after
`merge_control_panel.py` — doesn't touch that script's own tested merge
logic). Both are **closed rosters within their source's own documented
coverage window** (through 2025; 2026 stays blank, outside what either
source covers) — the one deliberate exception to "blank means no data" in
this file, since both sources are comprehensive-by-design catalogs within
their stated window, the same logic as `eu_member`'s closed roster.
`log_population`, `log_gdp_ppp_per_capita`, `trade_openness` are hand-named
derived columns computed inside `wdi()` itself from columns it already
built (including a newly wired-in GDP-PPP-per-capita extract). Also added:
`other_mdb_usd_t1`/`other_mdb_usd_millions_t1`/`ln1p_other_mdb_usd_t1`/
`other_mdb_usd_strict_t1` (the H4 instrument — total lending by every
*other* eligible bank to the same recipient in year t-1, needing no
external dataset — `scripts/build_other_mdb_lending.py` +
`merge_other_mdb_lending.py`, also additive/overwrite-in-place steps) and
the PPP-adjusted parallel `other_mdb_ppp_t1`/`_millions_t1`/`ln1p_other_mdb_ppp_t1`/
`other_mdb_ppp_strict_t1` (2026-10-04, built from `ppp_2025_total`; an
unpriced pool member counts as 0 in the available total, as USD does, and
makes the strict total blank) and
`data/manual/bank_classification.csv` (Rebecca Ray (2021)'s governance
typology, a **separate bank-level table, not a panel column** — a
time-invariant classification isn't estimable within this project's
per-bank regressions).

### `data/output/mdb_panel_final.csv` — the panel with UNGA independent variables

Built by `make final` (`scripts/build_unga_ideal_points.py` ->
`build_shareholder_weights.py` -> `build_unga_iv.py` -> `merge_unga_iv.py`
-> `report_largest_shareholders.py`). `mdb_panel_with_controls.csv`
left-joined with four independent-variable constructions from Erik
Voeten's UNGA ideal-point estimates (`../Control variables/`'s sibling,
`../Final dataset/` — non-git-tracked, see `docs/coding_decisions.md`,
2026-09-28): **hegemonic** (distance to the bank's largest shareholder),
**G7**/**G10** (distance to a vote-power-weighted average of whichever
fixed-list members are shareholders), **large shareholders** (the same,
for shareholders above a 5% weight threshold), and **coalition** (the
same, across every shareholder) — each computed for both `idealpointall`
and `idealpointfp`, and at both `t` and `t-1`, giving 20 `unga_*_dist_*`
columns plus supporting reference-point/count/identity columns, all
prefixed `unga_`. The four weighted-average constructions (G7/G10/large-
shareholders/coalition) count `idealpointall` and `idealpointfp` coverage
**independently** (`..._n_shareholders_all`/`..._n_shareholders_fp`, two
columns each) — a shareholder missing one measure still contributes to
whichever measure it actually has, which matters because `idealpointfp`
reaches 2025 in this panel and `idealpointall` never does (below). Never
zero-filled — a missing UNGA value anywhere leaves the distance blank. Row
count always equals `mdb_panel_with_controls.csv`'s own (a left join,
never a filter). Also written to `../Final dataset/output/
mdb_panel_final.csv`, alongside the individual-shareholder companion file
`unga_large_shareholder_distances.csv` (long format — doesn't fit as wide
columns since qualifying >5% shareholders vary by bank-year). Full data
dictionary and largest-shareholder-per-bank report: `../Final dataset/
codebook/`.

`idealpoint_fp` extends through **2025** (`build_unga_ideal_points.py`'s
`--fp-extension`, the user's explicit choice after being shown the vintage-
mismatch trade-off); `idealpoint_all` has real coverage only through
**2023** — not 2024: the raw `.dta` itself has zero non-null `idealpointall`
values for 2024, a genuine property of that release, not a processing gap
(see `docs/coding_decisions.md`, 2026-09-28).

`make final`'s last step, `scripts/plot_unga_positions.py`, recreates the
user's "MDB positions within the UNGA country distribution" chart as **two
separate charts**, one per measure — `unga_positions_chart.png`
(`idealpointfp`, 2002-2025) and `unga_positions_chart_idealpointall.png`
(`idealpointall`, 2002-2023), each a percentile-band/median country
distribution with every bank's `coalition_ip_*` trajectory overlaid, and
each with an explicit footnote stating which measure it uses — see
`docs/coding_decisions.md`, 2026-09-28. Needs `matplotlib`
(`pip install matplotlib`), the only script in this project that uses it.
Each chart writes its own PNG + `..._data.csv` to `../Final dataset/output/`.

## Canonical bank codes

`IBRD`, `IDA`, `AfDB`, `AsDB`, `IDB`, `EBRD`, `EIB`, `IsDB`, `CAF`, `CDB`,
`AIIB`, `BADEA`, `NDB`, `CABEI` — fourteen codes.

**AfDB and ADF are not separate codes.** They briefly were (2026-09-24 -
2026-09-28), but ADF never had independent shareholding/membership/mandate
data of its own, and a real subset of projects tagged with both windows had
no honest way to be split between two competing bank-level totals — see
`docs/coding_decisions.md`, 2026-09-28. AfDB's ordinary-vs-concessional split
now lives as columns on `mdb_panel.csv`'s one AfDB row instead. AsDF
(AsDB's concessional arm) was never split out at all — decision 2 remains
unresolved there, blocked on scraper-side `funding_window` coverage (only
~16% of ADB projects have it, vs. ~94% for AfDB), not a judgement call.

## This is not primarily a scraping project

Roughly half this data should be **hand-maintained CSVs in `data/manual/`**,
under version control. They are small, stable, and encode judgement.

**Hand-maintain:**
- Accession / recipient-status dates per bank
- Geographic mandate timelines (EBRD countries of operations, EIB external
  mandate periods)
- Sanctions and suspension events (~20 rows total)
- Any judgement call about ambiguous cases

**Scrape or download:**
- World Bank `OGHIST.xlsx` and annual per-capita income guidelines
- Annual report PDFs → capital subscription tables and non-accrual lists
- Wayback Machine snapshots of member pages (AIIB, NDB, CAF)
- COW IGO v3 dataset (2002–2014 cross-check)

Do not write a scraper for something that is a hundred rows of stable facts.
Ask before building one.

## Hard rules

**Never invent data.** If an accession year, mandate date, or classification
cannot be verified from a source, write `null` and append a row to
`data/manual/unresolved.csv` with what was needed and what was tried. A
plausible-looking wrong date corrupts the panel silently.

**Cache every fetch.** Write raw responses to `data/raw/` keyed by URL hash and
check the cache before requesting. The annual report pipeline will be re-run many
times; it must not re-download hundreds of PDFs each time. `data/raw/` is
gitignored.

**Be polite.** Rate limit requests, set a descriptive user agent with contact
details, respect robots.txt. These are institutional sites being hit from a
university connection.

**Every row needs a source.** The `source` column is not optional. It becomes a
thesis appendix — see `docs/data_sources.csv` and
`../Final dataset/codebook/data_sources.md`.

**Log judgement calls.** Append to `docs/coding_decisions.md` with the date,
the decision, and the reasoning.

## Validation

These run via `make validate` and must pass before any output is considered
usable:

1. **Revealed eligibility.** Every dyad-year with observed positive lending in
   the project data must be coded eligible. Zero **unexplained** violations
   permitted — this is the strongest check available, since it uses ground
   truth. A violation already reviewed and understood (`data/manual/
   accepted_revealed_exceptions.csv`, 2026-09-30 — e.g. IDA's post-graduation
   transitional lending, EIB's own-risk lending with no public country list)
   is reported as its own kind but doesn't fail the build; anything not on
   that list still does. See `docs/coding_decisions.md`, 2026-09-30.
2. **Panel balance.** Count of eligible dyad-years per bank per year. Every
   discontinuity must correspond to a documented accession or mandate change.
3. **Zero share.** Proportion of eligible dyad-years with no lending, by bank.
   Above ~95% suggests the eligibility set is too wide — usually the
   membership-versus-recipient-status confusion.
4. **Annual report spot check.** For three banks × three years, eligible country
   count against the borrowing-member count stated in the annual report.

## Known traps

- **Membership ≠ borrowing eligibility.** AIIB has 111 approved members but
  Germany and the UK will never borrow. IDB has 48 members and 26 borrowing
  members. AsDB lends to developing member countries only. Code recipient status.
  **IBRD and EBRD had exactly this bug until 2026-10-02** — both are
  `b_basis: "membership_only"`, so bare shareholding (the US, Japan,
  Germany, France, UK, Canada, and 29 more combined) was read as recipient
  status, with no file anywhere distinguishing "founding donor shareholder"
  from "borrowing member" the way `recipient_status.csv` does for every
  other bank. `data/manual/non_regional_shareholders.csv` is a closed
  override (not a full re-research of either bank's ~150+ real members) —
  see `docs/coding_decisions.md`, 2026-10-02.
- **The 2017 mergers.** ADB merged ADF lending operations into OCR on
  1 January 2017, leaving ADF grant-only; IDB did the same with FSO. The AfDB/ADF
  and IBRD/IDA splits are clean across the whole period; the AsDB/AsDF split is
  not. See `docs/methods_section.md`.
- **Fiscal vs calendar year.** World Bank classifications are assigned 1 July and
  fixed for the fiscal year. Pick a mapping to calendar years and apply it
  everywhere.
- **Prospective members are not members.** NDB lists countries admitted by the
  Board of Governors that have not deposited instruments of accession. They are
  not members until they do.
- **Blend countries are eligible for both arms.** A blend country appears as an
  eligible dyad-year for both IBRD and IDA.

## Conventions

Follow `docs/reference_conventions.md`. In particular, reuse the country-name
normalisation from `../mdbs_scraper_corrected/` rather than reimplementing it —
if the two repos normalise Kosovo, Serbia/Montenegro, South Sudan, or Timor-Leste
differently, the eventual merge will silently drop rows.

## Commands

```
make wayback      # re-fetch EBRD/IsDB historical shareholder data (Wayback Machine)
make shares       # build data/extracted/shareholders_panel.csv
make membership   # build data/output/membership.csv
make build        # membership.csv, then data/output/eligibility.csv
make panel        # build data/output/mdb_panel.csv, the estimation panel
make controls     # build data/output/mdb_panel_with_controls.csv (needs pandas)
make final        # build data/output/mdb_panel_final.csv, + UNGA independent variables
make validate     # run all four validation checks
make test         # run the offline unit tests
```

(The original `make grid`/`make fetch`/`make appendix` from this section's
first draft are the full-country-universe-grid and thesis-appendix work,
still not built — see `docs/architecture.md` section 4 and decision 6.)
