# Data sources

A provenance appendix for every raw external dataset behind `mdb_panel_final.csv`
and the UNGA-positions charts: who published it, where it came from, what
version, when it was obtained, and what it's licensed under, where that's
known. This complements [`codebook.md`](codebook.md), which documents what
each *column* in the final panel means; this file documents where the raw
*inputs* to those columns came from.

The machine-readable version of this table — one row per source, same
content — is `docs/data_sources.csv` in the `mdb_eligibility` code repo; that
CSV is the source of truth if the two ever drift, since it lives next to the
scripts that actually read these files.

**A rule this project holds itself to**: where an access date, a version
number, or a license isn't recorded anywhere in the project (scripts, commit
history, or the files as downloaded), the cell below says so explicitly
(`not recorded`) rather than guessing one. A few of those are flagged with a
concrete next step to close the gap before the thesis is submitted.

---

## 1. UNGA voting data

The independent variable at the center of the coalition/alignment analysis:
Erik Voeten's dynamic ideal-point estimates from UN General Assembly
roll-call votes.

| Dataset | Publisher | Version / release | Accessed | License |
|---|---|---|---|---|
| UNGA Ideal Point Estimates (main release) | Bailey, Strezhnev & Voeten (Georgetown University) | `IdealpointsJuly2025.dta`, July 2025 vintage | not recorded | not stated; Harvard Dataverse entry not independently re-checked |
| UNGA Ideal Point Estimates — FP-only 2025 extension | Bailey, Strezhnev & Voeten | `IdealpointestimatesFP_2026FP.csv`, "2026FP" vintage | not recorded | same as above |
| *(collected, unused)* AgreementScores, IdealPointDyads, IdealpointestimatesAll_Jun2024 | Bailey, Strezhnev & Voeten | various | not recorded | same as above |

Source: <https://dataverse.harvard.edu/dataverse/Voeten>

**Citation**: Bailey, Michael A., Anton Strezhnev, and Erik Voeten. "Estimating
Dynamic State Preferences from United Nations Voting Data." *Journal of
Conflict Resolution* 61, no. 2 (2017): 430–456.

**Notes**:
- The main release and the FP-only extension are **different model
  vintages** — a new release re-estimates the entire dynamic series, so the
  two don't stitch together at full precision (correlation r=0.9996 on
  overlapping years, not identical). The extension is used only to carry
  `idealpoint_fp` one additional year (through 2025); `idealpoint_all` stays
  capped at the main release's coverage (through 2024) rather than being
  patched from a different vintage.
- `idealpoint_all` is genuinely null for **every** country in 2024 in the
  main release — verified directly, not a processing bug — which is why the
  `idealpointall` chart's x-axis stops a year earlier than the `idealpointfp`
  chart's.
- Several other files from the same Dataverse download (agreement scores,
  dyadic ideal points, an older "All" vintage) were collected alongside these
  two but aren't used anywhere in the pipeline — listed here for
  completeness rather than silently left out.

---

## 2. World Bank institutional & classification data

| Dataset | Publisher | Version / release | Accessed | License |
|---|---|---|---|---|
| Historical classification by income, lending & fragile status | World Bank | Dataset `DR0095347`, covers 1988–2026 | fetched live at build time; investigated 2026-09-21 | World Bank Open Data default (CC BY 4.0), not independently re-confirmed |
| Region classification (via a population-indicator metadata file) | World Bank | WDI bulk bundle 430592, `Metadata_Country` file | not recorded | same as above |
| WDI custom extract — macro/trade/governance (45 series) | World Bank (WDI) | extract's own footer: "Last Updated: 07/13/2026" | not recorded separately | same as above |
| WDI custom extract — population (`SP.POP.TOTL`) | World Bank (WDI) | single indicator | not recorded | same as above |
| WDI custom extract — GDP per capita, PPP (`NY.GDP.PCAP.PP.CD`), added 2026-09-30 | World Bank (WDI) | single indicator, **current**-price | not recorded | same as above |

Sources: <https://ddh-openapi.worldbank.org/resources/DR0095347/download> ·
<https://data.worldbank.org/indicator/SP.POP.TOTL> ·
<https://databank.worldbank.org/source/world-development-indicators>

**Notes**:
- The income/lending/fragile-status classification replaced an older World
  Bank file (`OGHIST.xlsx`) that the Bank had quietly stopped updating; the
  replacement was cross-verified against the old file on 4,649 overlapping
  country-years with zero mismatches before being trusted.
- The region classification is a byproduct of an unrelated population
  download — only its `Region` column is used (a static, standard World
  Bank taxonomy); the population figures in that same file are **not**
  used. Population instead comes from the separate WDI custom extract.
- All 45 series in the macro/trade/governance WDI extract are ingested
  (GDP PPP, trade openness, external debt, inflation, literacy,
  unemployment, World Governance Indicators scores, etc.) — see the raw
  file's own column headers for the complete list.
- The GDP-per-capita-PPP extract is genuinely new, not a duplicate of the
  macro extract's total-GDP-PPP series (`NY.GDP.MKTP.PP.CD`) — and it's the
  current-price series (`NY.GDP.PCAP.PP.CD`); no constant-price series
  (`NY.GDP.PCAP.PP.KD`) is present in any WDI extract this project has.

---

## 3. Control-variable covariates

| Dataset | Publisher | Version / release | Accessed | License |
|---|---|---|---|---|
| World Press Freedom Index | Reporters Without Borders (RSF) | per-year files, 2002–2026 (2003/2011/2017 absent) | not recorded | not stated; not independently reviewed |
| Global Restrictions on Religion, 2007–2022 | Pew Research Center | 15th report in the series, published 18 Dec 2024 | not recorded | not stated; treat as all-rights-reserved unless confirmed |
| V-Dem Country-Year dataset | V-Dem Institute, University of Gothenburg | v16 (2026 release) | not recorded | per V-Dem's own bundled citation notice; not independently re-quoted |
| PLAD — Political Leaders' Affiliation Database | *not confirmed — see below* | April 2024 release | not recorded | not stated |
| LGBTI National Policy Dataset | Kristopher Velasco | Version 2.2 | not recorded | **CC BY 4.0**, confirmed |
| UN Tourism bulk statistical data | UN Tourism (UNWTO) | 3 files, dated 03/2026–06/2026 | not recorded | not stated |
| EU membership spells | author-compiled from public treaty record | — | — | n/a — public record |

Sources: <https://rsf.org/en/index> ·
<https://www.pewresearch.org/religion/2024/12/18/government-restrictions-on-religion-stayed-at-peak-levels-globally-in-2022/> ·
<https://www.v-dem.net/data/the-v-dem-dataset/> ·
<https://doi.org/10.17605/OSF.IO/WTA9P> ·
<https://www.unwto.org/tourism-statistics>

**LGBTI Index suggested attribution** (verbatim, from its bundled LICENSE):
> Velasco, Kristopher. 2026. "LGBTI National Policy Dataset, Version 2.2."
> https://doi.org/10.17605/OSF.IO/WTA9P. Distributed under CC BY 4.0.

**Notes**:
- **PLAD's publisher/citation is an open item.** The bundled
  `PLAD Codebook.pdf` (in `Control variables/datasets/dataverse_files (1)/`)
  has the authoritative citation but its text couldn't be extracted
  programmatically this session — open it directly and fill in the
  publisher/URL here and in `docs/data_sources.csv` before the thesis is
  submitted, rather than leaving the placeholder in the final appendix.
- V-Dem's usage is reduced to 11 indices (electoral, liberal, participatory,
  deliberative, egalitarian democracy indices; civil-liberties and
  free-expression indices; corruption, rule-of-law, and gender-empowerment
  indices).
- Of the many UN Tourism "Bulk" indicator folders available, only 3 are
  used (macroeconomic, employment, SDG indicators); the tourism-flow tables
  (domestic/inbound/outbound/accommodation) sit alongside them but aren't
  read by any script.
- EU membership is a closed roster compiled by the author from well-known
  treaty dates (Treaty of Rome 1958, the accession treaties of
  1973/1981/1986/1995/2004/2007/2013, Brexit on 31 Jan 2020) rather than a
  single external download; every country-year gets a confident yes/no,
  never a blank.
- RSF's per-year files have three gaps (2003, 2011, 2017) — no file for
  those years exists locally; not investigated further whether RSF itself
  didn't publish an index those years or it simply wasn't downloaded.

---

## 4. MDB institutional & governance data

The shareholding, voting-power, and mandate data behind each bank's
eligibility rules and the independent-variable panel.

**Shareholding & voting-power snapshot (14 banks)** — one official primary
source (plus a secondary cross-check source) per bank: IBRD, IDA, AfDB,
AsDB, IDB, EBRD, EIB, IsDB, CAF, CDB, AIIB, BADEA, NDB, CABEI. `as_of` dates
range 2024–2026 depending on the bank; the extraction workbook itself is
dated 2026-08-25. Full per-bank detail (official source, secondary source,
and each bank's own caveats about what the reported figures do and don't
cover) is in `data/manual/shares_snapshot_source.json` in the code repo
rather than repeated here for all 14 banks. That manifest's own caveat,
quoted directly: *"Extracted verbatim from the workbook's own Source_Map
sheet. Not independently verified against the cited primary URLs."*

**Annual reports / financial statements corpus** — 287 individual documents
across all 14 banks, 2002–2025, cited one-by-one (bank, year, URL) in
`data/manual/annual_reports.csv`. The cached PDFs themselves are not
redistributed (kept out of git); the CSV's URLs are the durable citation.

**EIB External Lending Mandate decisions** — four specific EU legal acts
(EUR-Lex CELEX-numbered decisions, e.g. `CELEX:32006D1016`), defining the
years and countries covered by the mandate.

---

## 5. MDB project-lending data

Project-level commitments for eight sources — ADB, AfDB, IsDB, CABEI, IDB,
EBRD, World Bank (IBRD+IDA), and AIIB — collected via a companion scraper
project (`mdbs_scraper_corrected`). This is the best-documented layer of the
whole data-collection effort: every one of the 8 sources has a recorded
`publisher_url`, an `as_of` date (ranging December 2017 – June 2026
depending on the source), a `retrieved_on` date (mostly 2026-09-16), and a
SHA-256 hash of the exact file used — see
`mdbs_scraper_corrected/mdbs_scraper/official_sources.json` for the full
manifest rather than repeating all 8 rows here.

---

## 6. Conflict, financial crisis, and MDB-governance data (added 2026-09-30)

| Dataset | Publisher | Version / release | Accessed | License |
|---|---|---|---|---|
| UCDP/PRIO Armed Conflict Dataset (ACD) | Uppsala Conflict Data Program (UCDP) & PRIO | v26.1, covers 1946–2025 | not recorded | not independently confirmed; UCDP data is typically free for research use with citation |
| Systemic Banking Crises Database: 1970–2025 | Luc Laeven and Fabian Valencia, IMF | Working Paper WP/26/94, May 2026 | not recorded | not independently confirmed |
| Who controls multilateral development finance? | Rebecca Ray | *Global Governance* 27(1): 118–143 (2021) | 2026-09-30 (excerpt only) | not independently confirmed |

Sources: <https://ucdp.uu.se/downloads/> (UCDP); IMF Working Paper WP/26/94
— no direct URL was captured from the file itself, search "Systemic Banking
Crises Database" at <https://www.elibrary.imf.org>; Ray (2021) — only a
pasted excerpt (an image) of the article was available, not the full text
or a DOI.

**Notes**:
- **UCDP** is the Armed Conflict Dataset only — not the Georeferenced Event
  Dataset or the Battle-Related Deaths dataset, neither of which is present
  in this project's files. Its `location` field names the conflict's
  contesting government(s), which its own codebook says is not necessarily
  where fighting physically occurs — this affects only the ~4% of
  conflict-years in this project's study window that are interstate wars
  (credited to every country `location` lists, per the user's own confirmed
  choice); the rest are intrastate/internationalized-intrastate conflicts
  naming exactly one country. **No battle-death count column exists in this
  file** — a `ucdp_conflict_deaths` variable was not built, omitted rather
  than proxied.
- **Laeven & Valencia** covers systemic **banking** crises only — no
  currency-crisis, sovereign-debt-crisis, or IMF-lending-arrangement data
  anywhere in the 47-page working paper (confirmed by full-text search) —
  only a `banking_crisis` flag was built from it.
- Both UCDP and Laeven & Valencia are used as **closed rosters within their
  own documented coverage window** (through 2025) for `ucdp_armed_
  conflict`/`ucdp_war`/`banking_crisis` — a confident 0 for a covered year
  with nothing listed, genuinely blank for 2026 (outside what either source
  covers). UCDP's own coverage-bias caveat — "biased against the inclusion
  of conflicts in the earlier decades and in the less-developed world" — is
  inherited by those 0s and documented here rather than silently absorbed.
  See `docs/coding_decisions.md`, 2026-09-30, for the full reasoning.
- **Ray (2021)** is used for `bank_classification.csv`, a separate
  bank-level table (not a panel column). Only a pasted excerpt was
  available, naming 11 of this project's 14 canonical banks; **NDB and
  BADEA's classifications were supplied directly by the user**, not from
  the paper — recorded as such in that file's own `classification_source`
  column.

---

## 6b. PPP and currency inputs for the PPP-adjusted lending outcome (added 2026-10-04)

These are used by the sibling scraper (`mdbs_scraper_corrected`) to build
`ppp_2025_total` and `usd_*`; `mdb_eligibility` reads only the finished totals.

| Dataset | Publisher | Version / release | Accessed | License |
|---|---|---|---|---|
| GDP (current US$), `NY.GDP.MKTP.CD` | World Bank (WDI) | scraper reference cache, 2000–2025, 257 countries | not recorded | CC BY 4.0 (WB default) |
| GDP, PPP (current intl $), `NY.GDP.MKTP.PP.CD` | World Bank (WDI) | scraper reference cache, 2000–2025 (2025: 228 countries) | not recorded | CC BY 4.0 (WB default) |
| Exchange rate, LCU per USD, annual average, `XDC_USD.PA_RT.A` | International Monetary Fund (IFS) | scraper cache, 2000–2025, 17 currencies | not recorded | IMF terms of use (not re-checked) |
| US GDP implicit price deflator, `A191RD3A086NBEA` | BEA via FRED | through 2025-01-01 | not recorded | US government work / FRED terms |

Method note: the PPP amount is the GDP price-level ratio, not the official
`PA.NUS.PPP` conversion factor (a deliberate choice, 2026-10-04), and
everything is deflated to constant 2025 USD with a US deflator, not a local
CPI. Unpriced years are blank in the panel (see `codebook.md`, section 2).

## 7. Collected, not used in the final pipeline

Listed for transparency rather than silently omitted — these were gathered
during data collection but don't feed any column in the final panel or
either chart:

- **OWID "World regions according to the World Bank" data package**
  (Our World in Data, sourced from the World Bank; downloaded 2026-09-28 per
  its own bundled readme). `wb_region()` uses the World Bank's own metadata
  file instead (§2 above).
- Several Voeten Dataverse files beyond the two actually used (§1 above).

---

*Generated from `docs/data_sources.csv` in the `mdb_eligibility` repo. If
that CSV is updated, re-render this page from it rather than editing the
two independently.*
