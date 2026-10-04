# MDB Eligibility Dataset

Code for a master's thesis testing whether multilateral development banks
(MDBs) allocate lending according to the same organisational logic. This
repo builds an eligibility panel — for every (bank, country, year) triple,
whether that bank *could have* lent to that country that year — and merges
it with lending outcomes, control variables, conflict and financial-crisis
indicators, and UN General Assembly voting-alignment measures into a single
estimation panel.

See [`docs/CLAUDE.md`](docs/CLAUDE.md) for the full architecture, and
[`docs/coding_decisions.md`](docs/coding_decisions.md) for a running log of
every judgement call made while building it, with reasoning.

## This is a publication export, not the primary development history

This repo is a **sanitized, single-commit export** of a private development
repository. The full commit-by-commit history lives elsewhere and isn't
published; this copy exists to make the code and results available without
carrying personal information (author identity, local file paths, etc.)
that has no bearing on the analysis. Nothing about the analysis itself is
different here — same code, same logic, same documented decisions.

## Reproducing this from scratch

Three things beyond this repo are needed to regenerate everything from raw
inputs, none of which are published here (see
[`docs/data_sources.csv`](docs/data_sources.csv) for exactly where to get
each one, with versions/access dates/licenses where known):

1. **`mdbs_scraper_corrected`** — a sibling code repo this project imports
   directly (project-lending scraping, country-code normalization, and the
   PPP and deflator reference series). Clone it *as a sibling folder named
   exactly `mdbs_scraper_corrected`* (regardless of what its own repository
   is named) — several scripts resolve it via a relative path that assumes
   that folder name.
2. **`Control variables/`** — a sibling *data* folder (not a git repo) of
   third-party covariate datasets (World Development Indicators, V-Dem,
   RSF Press Freedom Index, Pew's Global Restrictions on Religion, the
   UCDP/PRIO Armed Conflict Dataset, Laeven & Valencia's Systemic Banking
   Crises Database, PLAD, the LGBTI Policy Index, UN Tourism data). Not
   redistributed here because several of these datasets' redistribution
   terms aren't confirmed — see `docs/data_sources.csv` for exact download
   links instead.
3. **`Final dataset/`** — a sibling *data* folder (not a git repo) holding
   Erik Voeten's UNGA ideal-point estimates (the raw input this project's
   own UNGA independent variables are built from) and serving as the write
   target for some pipeline outputs. Not redistributed here for the same
   license-caution reason as (2).

Once those three are checked out as siblings of this repo (i.e.
`../mdbs_scraper_corrected`, `../Control variables`, `../Final dataset`),
`make final` reproduces the full pipeline end to end. Missing a sibling
fails with an explanatory message rather than a raw traceback.

## Lending outcomes

The panel carries three lending outcomes per bank-recipient-year, all in
constant 2025 money:

- `usd_2025_total` — nominal USD, deflated with the US GDP deflator.
- `ppp_2025_total` — PPP-adjusted, via the GDP price-level ratio
  (`NY.GDP.MKTP.CD / NY.GDP.MKTP.PP.CD`), not the official `PA.NUS.PPP`
  factor.

Both are blank where a dyad-year cannot be priced: the deflator has no 2026
value, so 2026 is unpriced, and a few dyad-years have an unpriced project.
The other-MDB instrument (H4, total lending by other eligible banks to the
same recipient in the prior year) comes in a USD version and a PPP version,
each with a strict companion. See `docs/CLAUDE.md` and
`docs/coding_decisions.md` (2026-10-04) for the full account.

## Already-computed results, included in this repo

The final estimation panel (`data/output/mdb_panel_final.csv`) and the
UNGA-derived reference-point tables (`data/extracted/unga_ideal_points.csv`,
`data/extracted/unga_bank_year_reference_points.csv`) are already tracked
in this repo at their normal pipeline paths — no separate copy needed.

[`thesis_output/`](thesis_output/) adds the two things that otherwise only
exist in the non-published `Final dataset/` sibling folder: the two
"MDB positions within the UNGA country distribution" charts (with their
underlying per-year data), and the full codebook — including
[`codebook.md`](thesis_output/codebook/codebook.md) (what every column
means) and [`data_sources.md`](thesis_output/codebook/data_sources.md)
(the data-source appendix). All of this is this project's own synthesis/
computation, not a redistribution of anyone else's raw dataset, so it
carries no third-party license concern.

## Tests

```
make test
```

Runs the full offline unit-test suite (hermetic — no network access, no
dependency on the sibling data folders above). 311 tests as of this export.
