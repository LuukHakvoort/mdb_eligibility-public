# Architecture

## 1. Principles

1. **Hand-maintained CSVs are the authority; parsed data is evidence.** Scraped tables never set a component value on their own. They feed a *reconciliation* report against the manual tables, and every discrepancy is resolved by a reviewed CSV edit or a logged decision. A PDF parser that misreads a country name therefore produces a visible diff, not a silently flipped `member` flag.
2. **Three input classes, one fetch path.**
   - **Hand-maintained:** typed into `data/manual/`, every row with a `source`.
   - **Downloaded once:** a single stable file, fetched through the cache so there is a hashed copy to cite. It is either read by a human (EUR-Lex decisions, income guidelines) or, for a published dataset, loaded as-is with no page parsing (COW IGO v3).
   - **Scraped:** fetched through the cache and parsed by code into `data/extracted/`.
3. **Every value carries a source.** Each component function returns *(value, source, note)* per grid row. `validate()` rejects an empty `source`.
4. **Unknown is `null` plus a row in `unresolved.csv`**, never a guess. `make validate` fails while any `eligible` is null.
5. **Each dependency on the scraper repo has one seam.** Country names go only through `countries.py`. Project data is read only by `validate.py`, through the crosswalk in `banks.json`.
6. **The build works without the expensive PDF pass.** If annual-report extractions are missing, B falls back to manual spells alone, and E to hand-coded events alone. The manifest records which inputs were used, matching the plan's "if time is short" path.

## 2. Components: scraped, downloaded once, or hand-maintained

| Component | Hand-maintained (authority) | Downloaded once (cited, read by a human) | Scraped (evidence or input) | Verdict |
|---|---|---|---|---|
| **A. Bank existence** | `bank_existence.csv`: operations start year per bank | Charters or founding press releases for AIIB and NDB, as citations | none | **Hand-maintained** |
| **B. Membership / recipient status** | `recipient_status.csv` spells; `eu_membership.csv` | COW IGO v3 (2002–2014 cross-check); current borrowing-member pages, cached for citation | Annual-report **capital subscription tables** (member set per year, plus shareholder weights); **Wayback** member pages for AIIB, NDB, CAF | **Hand-maintained**, checked against scraped evidence |
| **C. Geographic mandate** | `mandate_spells.csv` (EBRD countries of operations, EIB external mandate periods); `au_membership.csv`, `arab_league_membership.csv` (BADEA rule) | EUR-Lex External Lending Mandate decisions; EBRD Board of Governors resolutions | none | **Hand-maintained**; BADEA and AIIB rules are computed from hand tables |
| **D. Window criteria** | `wb_thresholds.csv` (IDA operational cutoff per fiscal year); `window_classifications.csv` (AfDB A/B/C, AsDB groups, IsDB, IDA exceptions) | Per Capita Income Guidelines documents; IDA borrowing-country lists; replenishment documents | **OGHIST.xlsx**: income group per country and fiscal year; also lending category, *if the file actually contains it* (verify on first download) | **Scraped** (OGHIST) plus **hand-maintained** (thresholds and bank classifications) |
| **E. Structural bars** | `bar_events.csv` (~20 sanctions and suspension events); per-bank policy on whether non-accrual status bars new lending (in `banks.json`, with a source) | Press releases and subsequent-events notes, as citations | Annual-report **non-accrual notes**, extracted in the same PDF pass as the capital tables | **Hand-maintained** events; **scraped** non-accrual evidence, applied only where bank policy says it bars new lending |

Details that change what each component actually means:

- **A:** about 15 rows. Only banks that started operating inside 2002–2026 (AIIB, NDB) need anything other than "existed throughout".
- **B:** what "member" means differs by bank, so `banks.json` declares a `b_basis` for each:
  - **Borrowing-member list** (IDB, AsDB, CDB, AfDB, IsDB, CAF, AIIB, NDB). Rows come from the bank's published list; spells capture accessions.
  - **Membership only**, with the recipient restriction carried by C (EBRD, whose countries of operations sit in C) -- **also IBRD**, with the restriction nominally carried by D's income window. In both cases C/D's own fallback logic turned out to leak the same way B does for a non-regional donor shareholder (the US, Japan, Germany, ...) with no mandate spell/lending-category row of its own; fixed 2026-10-02 with a closed override, `data/manual/non_regional_shareholders.csv` -- see `docs/coding_decisions.md`.
  - **No membership condition** (EIB outside the EU, BADEA, which lends to non-members). `member = 1` with the source "no membership condition for borrowing; see C". These must be logged decisions, because they make `member` mean different things per bank.
  - **Concessional arms** (ADF, AsDF, IDA) take recipient status from their parent bank unless `banks.json` points to rows of their own. The arms differ from their parents in D.
- **B evidence flow:**
  1. Capital tables list *all* shareholders, including non-borrowers, so they cannot set recipient status.
  2. Instead, `reconcile.py` checks that every recipient in a year appears among that year's shareholders, and lists shareholders with no spell.
  3. Wayback snapshots are diffed year on year, which yields *candidate* accession years for a human to confirm. NDB "prospective members" are kept out by the parser's status label.
- **C:**
  - Trivially `1` for banks whose recipient list is already regional.
  - EBRD and EIB-external rows come from dated spells.
  - BADEA is computed: AU member and not Arab League member.
  - AIIB is computed from B and OGHIST (member and not high-income), per plan §4.4. Record the rule in `coding_decisions.md`.
- **D:**
  - IBRD/IDA status comes from OGHIST plus thresholds, and blend countries get `window_ok = 1` for both arms.
  - AfDB/ADF, AsDB/AsDF and IsDB come from classification spells.
  - Every other bank is `1`, with source "no formal income window".
  - The fiscal-to-calendar-year mapping is a single setting in `config.py`.
- **E:**
  - `barred = 1` only for hand events, or for non-accrual under a bank policy that says new commitments stop.
  - The revealed-eligibility check catches the "in arrears but still lending" case.

**Deliberately not built:**

- a crawler that looks for annual-report PDFs (PDF URLs and page numbers are hand-indexed in `annual_reports.csv`);
- scrapers for current member pages, EUR-Lex, or press releases;
- anything using Playwright.

## 3. Data layout

```
data/
├── manual/                         # committed; hand-maintained authority; plain UTF-8, read as utf-8-sig
│   ├── countries.csv               # iso3, name, exists_from, exists_to, source, note
│   ├── bank_existence.csv          # bank, start_year, end_year, source, note                      (A, ~15 rows)
│   ├── recipient_status.csv        # bank, iso3, status, start_year, end_year, source, note         (B, spells)
│   ├── eu_membership.csv           # iso3, start_year, end_year, source                            (B/C for EIB)
│   ├── mandate_spells.csv          # bank, iso3, basis, start_year, end_year, source, note          (C)
│   ├── au_membership.csv           # iso3, start_year, end_year, source                            (C, BADEA)
│   ├── arab_league_membership.csv  # iso3, start_year, end_year, source                            (C, BADEA)
│   ├── wb_thresholds.csv           # fiscal_year, ida_operational_cutoff_usd, source               (D, ~25 rows)
│   ├── window_classifications.csv  # bank, iso3, classification, start_year, end_year, source, note (D)
│   ├── bar_events.csv              # bank, iso3, event_type, start_date, end_date, source, note     (E, ~20 rows)
│   ├── annual_reports.csv          # bank, year, url, capital_pages, nonaccrual_pages, note          (PDF index)
│   ├── annual_report_counts.csv    # bank, year, borrowing_member_count, source                    (spot check, 9 rows)
│   ├── transcribed/                # hand transcriptions where the parser fails; same schema as extracted
│   └── unresolved.csv              # what, bank, iso3, year, needed, tried, logged_on
├── raw/                            # gitignored cache: <sha256>.<ext> + <sha256>.json metadata
├── extracted/                      # committed; generated by `make fetch`; reviewable diffs
│   ├── oghist.csv                  # iso3, fiscal_year, income_group[, lending_category], source_sha256
│   ├── cow_igo.csv                 # iso3, igo, year, status
│   ├── capital_subscriptions.csv   # bank, year, name_raw, iso3, shares, amount, currency, unit, voting_power_pct, source_url, page
│   ├── nonaccrual.csv              # bank, year, name_raw, iso3, source_url, page
│   └── wayback_members.csv         # bank, snapshot_timestamp, name_raw, iso3, status_label, snapshot_url
└── output/
    ├── eligibility.csv             # schema from CLAUDE.md; booleans 1/0/blank; sorted bank, iso3, year
    ├── shareholding.csv            # bank, iso3, year, shares, voting_power_pct, source (secondary output)
    ├── manifest.json               # inputs (manual + raw sha256), scraper commit, outputs sha256, null counts
    ├── reports/                    # reconcile_<bank>.md, validation.md
    └── appendix/                   # appendix_a.csv, appendix_b.csv
```

Conventions:

- **Spells** include both their `start_year` and `end_year`; a blank `end_year` means ongoing.
- **Spells covering part of a year:** one rule, implemented in a single `spell_covers(spell, year)` function. The proposed default:
  - B, C and D count if active on any day of the year;
  - E counts only if in force for the whole year.

  Log the rule in `coding_decisions.md`.
- **Why `data/extracted/` is committed:** the files are small; changes to a parser show up as data diffs; and `make build` runs offline without re-parsing PDFs.

Sizes are rough guesses: `countries.csv` about 220 rows, including CDB territories and `XKX`; `recipient_status.csv` about 500 spells; everything else is under 200 rows each.

## 4. Module structure

```
mdb_eligibility/
├── CLAUDE.md                        # moved to root (pending)
├── Makefile                         # grid, fetch, build, validate, appendix, test
├── pyproject.toml                   # stdlib core; extras: xlsx (openpyxl), pdf (pdfplumber); editable ../mdbs_scraper_corrected
├── docs/                            # eligibility_plan.md, methods_section.md, reference_conventions.md,
│                                    # architecture.md, coding_decisions.md
├── src/mdb_eligibility/
│   ├── __init__.py  __main__.py
│   ├── errors.py                    # copied shape: EligibilityError > SourceError, SourceLayoutChanged,
│   │                                #   OptionalDependencyMissing, ValidationError, UnresolvedValue
│   ├── config.py                    # loads banks.json -> frozen BankDefinition; YEARS, FISCAL_YEAR_MAPPING, contact env var
│   ├── banks.json                   # code, name, b_basis, parent, window_rule, nonaccrual_bars_new_lending (+source),
│   │                                #   project_bank_id, project_funding_window, wayback_url, annual_report_parser
│   ├── http.py                      # copied HttpClient + robots.txt + process-wide per-host throttle + contact user agent
│   ├── cache.py                     # fetch(url) -> cached bytes; sidecar metadata; --refresh; 2xx only; atomic writes
│   ├── countries.py                 # ONLY seam to mdbs_scraper.iati_geography: require_iso3(); country universe
│   ├── manual.py                    # strict typed loaders for every data/manual CSV: columns, iso3, source non-empty,
│   │                                #   start<=end, no overlapping spells, years in range; spell_covers()
│   ├── unresolved.py                # log_unresolved(...) -> data/manual/unresolved.csv
│   ├── schema.py                    # EligibilityRow, ShareholdingRow dataclasses: validate(), to_row(); utc_now()
│   ├── output.py                    # utf-8-sig CSV writer, sha256, manifest
│   ├── sources/                     # fetch via cache.py -> parse -> data/extracted/*.csv
│   │   ├── oghist.py                # named sheet + explicit header rows (not tabular.xlsx_rows)
│   │   ├── cow_igo.py               # one-off download + extract
│   │   ├── wayback.py               # CDX query, id_ snapshot fetch, one per-bank page parser (aiib, ndb, caf)
│   │   └── annual_reports/
│   │       ├── __init__.py          # parser registry; driven by manual/annual_reports.csv; prefers manual/transcribed/
│   │       ├── pdf.py               # pdfplumber page/table helpers; decimal-safe number parser
│   │       └── <bank>.py            # one parser per table layout, e.g. afdb.py, aiib.py (capital + non-accrual)
│   ├── grid.py                      # banks x countries (existing country-years only) x YEARS
│   ├── components/
│   │   ├── existence.py             # A
│   │   ├── membership.py            # B  (by b_basis; arms inherit from parent)
│   │   ├── mandate.py               # C  (spells; BADEA and AIIB rules)
│   │   ├── window.py                # D  (IBRD/IDA from OGHIST + thresholds; classification spells)
│   │   └── bars.py                  # E  (events; non-accrual under bank policy)
│   ├── build.py                     # combine A-E; eligible = A & B & C & D & ~E, 3-valued; member_since; join sources
│   ├── reconcile.py                 # evidence vs authority -> reports/reconcile_<bank>.md (never edits data)
│   ├── validate.py                  # revealed eligibility (via crosswalk), panel balance, zero share, spot check
│   ├── appendix.py                  # Appendix A (rules per bank) and B (panel summary)
│   └── cli.py                       # subcommands matching make targets; --refresh, --source, --allow-partial
└── tests/
    ├── fixtures/                    # OGHIST excerpt, CDX JSON, snapshot HTML, 1-2 PDF pages or pdfplumber JSON per layout
    └── test_<module>.py             # unittest; includes a test that runs manual.py validators on committed CSVs
```

**Layering** runs one way: `errors` → `config`/`http` → `cache` → `countries`/`manual`/`unresolved`/`schema` → `sources/*` and `components/*` → `grid`/`build`/`reconcile`/`validate`/`appendix` → `cli`.

- Components never fetch.
- Sources never write component values.

**What comes from the scraper repo** (per `reference_conventions.md` §12):

- *Imported:* `iati_geography` (only inside `countries.py`), `cleaning.normalize_text`/`join_values`, `parsers.parse_tables`/`table_to_dicts`/`html_to_text`.
- *Copied and adapted:* `http.py`, `errors.py`, the manifest and report patterns, the `BankDefinition` loader.
- *Not used:* `browser.py`, `parse_decimal`/`detect_currency` on report tables.

**Bank identity:**

- `banks.json` `code` holds the canonical output code (`AfDB`, `ADF`, `AsDB`, …); modules and parser files use its lowercase form.
- The crosswalk `project_bank_id` + `project_funding_window` is the *only* place the two repos' bank codes meet.

## 5. Data flow

```
make fetch     sources/* ──fetch──> data/raw (cache) ──parse──> data/extracted/*.csv
make grid      manual/countries + banks.json ──> grid (in memory; optionally output/grid.csv)
make build     manual.py validates data/manual  ──> components A–E over grid ──> build.py
               ──> output/eligibility.csv, shareholding.csv, manifest.json
               └─> reconcile.py ──> output/reports/reconcile_<bank>.md
make validate  eligibility.csv + ../mdbs_scraper_corrected/output/all_mdb_projects.csv (sha256 recorded)
               ──> 4 checks ──> reports/validation.md; exit 2 on any violation or remaining null
make appendix  eligibility.csv + banks.json + coding_decisions.md references ──> output/appendix/
```

Revealed eligibility reports project rows it could not place instead of dropping them: blank `country_code`, unmapped `funding_window`, or no crosswalk entry. `reference_conventions.md` §7 found about 634 such rows today.

## 6. Decisions to log in `coding_decisions.md` before the code that depends on them

1. ~~**Country-name gaps:** fix upstream in the scraper, or wrap them here.~~ **Resolved 2026-09-16** (`mdbs_scraper_corrected` commit `854d58e`): fixed upstream in `COUNTRY_NAME_TO_ISO2`, exactly as recommended — no wrapper needed here. `countries.py` imports the scraper's normaliser directly; see `docs/reference_conventions.md` §7/Appendix A.
2. **AsDF:** a separate institution before 2017 (proxied by the `concessional` flag), or merged into AsDB. This affects the `banks.json` crosswalk and D.
3. **`b_basis` per bank**, including `member = 1` for EIB (external lending) and BADEA.
4. **Fiscal-to-calendar-year mapping** for World Bank classifications.
5. **Partial-year spell rule** (§3 default).
6. **Country universe and succession:** Serbia and Montenegro (to 2006), South Sudan (2011), Kosovo (`XKX`); whether non-existent country-years are dropped from the grid.
7. **AfDB special funds and blended `funding_window` values** in the crosswalk.
8. **On-disk booleans:** `1`/`0`/blank.

## 7. Build order (maps to setup-guide step 4)

| Session | Modules | Manual data started |
|---|---|---|
| 1 Skeleton | `errors`, `config`/`banks.json`, `http`, `cache`, `countries`, `manual`, `schema`, `output`, `grid`, `cli` | `countries.csv`, `bank_existence.csv` |
| 2 Validation first | `validate.py` (+ crosswalk), `build.py` stubs returning null | — |
| 3 OGHIST | `sources/oghist.py`, `components/window.py` (IBRD/IDA) | `wb_thresholds.csv` |
| 4 Manual components | `components/membership.py`, `mandate.py`, `bars.py` | `recipient_status`, `mandate_spells`, `eu`/`au`/`arab_league`, `bar_events`, `window_classifications` |
| 5 COW cross-check | `sources/cow_igo.py`, `reconcile.py` | — |
| 6 Annual reports | `sources/annual_reports/*` | `annual_reports.csv`, `transcribed/` |
| 7 Wayback | `sources/wayback.py` | — |
| 8 Combine | `build.py` final, `appendix.py` | `annual_report_counts.csv` |
