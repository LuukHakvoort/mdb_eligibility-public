# Data Collection Plan: MDB Eligibility Rules

Building the eligible dyad-year panel. Target: one tidy file mapping every
(bank, country, year) to eligible / not eligible, with a documented reason.

---

## 0. The organising principle

"Eligibility" is not one variable. It decomposes into five components, and they
differ enormously in how expensive they are to collect. Collect them as separate
columns and combine them at the end, rather than trying to code a single
eligibility flag by hand.

| Component | What it is | Cost | Where it comes from |
|---|---|---|---|
| **A. Bank existence** | Was bank *i* operational in *t*? | Trivial | Founding dates; already known |
| **B. Membership** | Was *j* a member of *i* in *t*? | Moderate | Bank websites, annual reports, capital subscription tables |
| **C. Geographic mandate** | Was *j* inside *i*'s lending area in *t*? | Moderate–high for 4 banks, trivial for the rest | Articles of Agreement, board decisions, annual reports |
| **D. Window criteria** | Did *j* meet income/creditworthiness rules? | Low | World Bank OGHIST, IDA lists, bank country classifications |
| **E. Structural bars** | Suspension, sanctions, non-accrual | Low–moderate | Annual report financial statement notes; press releases |

**Final flag:** `eligible = A & B & C & D & ~E`

Keeping them separate means a coding error in one component is traceable, and it
lets you run robustness checks that relax one condition at a time (e.g. "results
hold if non-accrual countries are treated as eligible").

---

## 1. Target output schema

A single long file, `eligibility.csv`:

| Column | Type | Notes |
|---|---|---|
| `bank` | str | Standard code: IBRD, IDA, AfDB, AsDB, IDB, EBRD, EIB, IsDB, CAF, CDB, AIIB, BADEA, NDB |
| `iso3` | str | ISO 3166-1 alpha-3, harmonised across all sources |
| `year` | int | 2002–2026 |
| `bank_exists` | bool | Component A |
| `member` | bool | Component B |
| `in_mandate` | bool | Component C |
| `window_ok` | bool | Component D |
| `barred` | bool | Component E |
| `eligible` | bool | Combined |
| `member_since` | int | Accession year, for auditing |
| `source` | str | Short citation or URL |
| `note` | str | Free text for judgement calls |

Roughly 13 banks × ~190 countries × 25 years ≈ 62,000 rows before filtering.
Generate the full grid programmatically, then set flags — never hand-build rows.

**Also produce `coding_decisions.md`**, a running log of every judgement call with
its date and rationale. You will not remember in March why you coded Kosovo the
way you did, and Alex will ask.

---

## 2. Phase 0 — Free wins, do these first (half a day)

These three shortcuts remove a large share of the manual work and should be done
before any scraping.

### 2.1 Revealed eligibility

**If a bank lent to a country in a year, that dyad was eligible.** This is free,
it comes from data you already have, and it does two jobs:

- It gives you a guaranteed-correct lower bound on the eligibility set.
- It is an **automated error check**. Any dyad-year coded ineligible but showing
  observed lending is a coding error, full stop. Run this as an assertion after
  every revision of the eligibility file.

```python
# after building eligibility.csv
observed = commitments[commitments.amount > 0][['bank','iso3','year']]
merged = observed.merge(elig, on=['bank','iso3','year'], how='left')
errors = merged[~merged.eligible.fillna(False)]
assert len(errors) == 0, errors
```

It also gives you a head start on membership: earliest observed lending year is
an upper bound on accession year.

### 2.2 COW IGO v3 for 2002–2014

The Correlates of War Intergovernmental Organizations dataset (v3) provides
country-year membership for IGOs, and the coverage runs to 2014. It includes the
established MDBs. This hands you roughly half your study period for the older
banks at near-zero cost.

- Data and codebook: correlatesofwar.org/data-sets/igos/
- R package `igoR` wraps it for convenient extraction
- Cite: Pevehouse, Nordstrom, McManus and Jamison (2020), *Journal of Peace
  Research* 57 (3)

Caveats: coverage ends in 2014, so AIIB and NDB are absent entirely and you must
extend the rest forward yourself. Verify COW's coding against one bank you know
well before trusting it wholesale; IGO datasets occasionally conflate
institutions within a group (e.g. AfDB vs. ADF).

### 2.3 World Bank OGHIST

`OGHIST.xlsx` gives historical income classification **and historical lending
category** for every country-year from 1987. This single file covers most of
Component D for IBRD and IDA, and provides the income variable you need for
AIIB, AfDB, and AsDB window rules.

- Linked from the World Bank Country and Lending Groups page (note: `CLASS.xlsx`
  is the current-year file and is *not* what you want)
- The annual **"Per Capita Income Guidelines for Operational Purposes"** document
  gives the exact thresholds each fiscal year, including the IDA operational
  cutoff (USD 1,325 in FY26) and the IBRD graduation discussion threshold

Watch the fiscal-year convention: World Bank classifications are assigned on
1 July and held fixed for the fiscal year. Decide whether to map FY to calendar
year by start or end, and apply it consistently.

---

## 3. Phase 1 — Membership (Component B)

### 3.1 The single best source: capital subscription tables

For every bank, the **audited financial statements** in the annual report contain
a "Subscriptions to Capital Stock" or "Statement of Capital Stock and Voting
Power" table listing every member with its shares, capital subscription, and
voting power.

This is worth prioritising because it solves **two problems at once**:

1. Membership in year *t* is exactly the set of countries in the year-*t* table.
2. It gives you the **time-varying shareholder weights** you need for the
   shareholder-weighted ideal point measure — which also mitigates the
   near-collinearity problem of static shareholder weights.

Practically: download annual report PDFs for each bank for each year, locate the
capital table, and extract it. Structure is stable within a bank across years,
so one parser per bank usually handles the whole series.

```python
import pdfplumber
# tables are usually identifiable by a header keyword
# search pages for "Subscriptions to Capital" / "Voting Power" / "Capital Stock"
```

Where PDF tables resist extraction, `camelot` or `tabula-py` handle ruled tables
better than pdfplumber; for a handful of years, manual transcription is faster
than fighting the parser.

### 3.2 Triage by how much membership actually varies

Do not spend equal effort on all thirteen. Membership is essentially static for
most of them.

**High effort — genuinely time-varying, do these carefully:**

| Bank | What varies | Sources |
|---|---|---|
| **AIIB** | 57 founding members (2016) → 111 approved | Members page lists accession dates; Wayback snapshots; annual reports |
| **NDB** | BRICS-5 → +Bangladesh, UAE (2021), Egypt (2023), Algeria (2025), Uzbekistan (2026) | NDB members page; press releases; note "prospective members" are **not** members until instruments of accession are deposited |
| **EIB** | Tracks EU membership: 2004, 2007, 2013 enlargements, Brexit 2020 | EU accession treaty dates — trivially available |
| **CAF** | Steady accession of new shareholder countries | CAF annual reports, shareholders page |

**Low effort — near-static, a current list plus a handful of accession dates:**

IBRD, IDA, AfDB, AsDB, IDB, CDB, IsDB, BADEA, EBRD. For these, take the current
member list, find the few accessions falling inside 2002–2026 (e.g. Montenegro
2007, South Sudan 2012, Kosovo 2009 where applicable), and treat membership as
otherwise constant. Verify against COW for the pre-2015 portion.

### 3.3 Wayback Machine for historical member lists

For banks whose member pages don't show accession dates, reconstruct the list
year by year from archived snapshots. The CDX API returns all captures of a URL:

```
http://web.archive.org/cdx/search/cdx?url=aiib.org/en/about-aiib/governance/members-of-bank/*&output=json&collapse=timestamp:6
```

`collapse=timestamp:6` gives roughly one capture per month; take one per year,
fetch, parse the list, and diff consecutive years to identify accessions. This is
scriptable and reliable for pages with stable HTML structure.

### 3.4 Membership is not the same as borrowing eligibility

A trap worth flagging now, because it affects several banks:

- **AIIB**: Germany, UK, France are members but will never borrow. 111 approved
  members, but the bank's own reporting notes projects across roughly 40 members.
- **IDB**: 48 members, but only 26 are *borrowing* member countries.
- **EBRD**: members include many non-recipient countries; what matters is the
  **countries of operations** list.
- **AsDB**: 69 members, but lending goes to *developing member countries*; Japan,
  Korea, Australia are members and not borrowers.
- **CDB**: distinguishes borrowing from non-borrowing member countries.

So for these banks, Component B should record **recipient status**, not bare
membership. Bank websites and annual reports generally publish the borrowing
member list explicitly. Use it.

---

## 4. Phase 2 — Geographic mandate (Component C)

Trivial for most banks — the mandate is the region and doesn't change. Four need
real work.

### 4.1 EBRD — countries of operations

This is the most demanding case, because the mandate expanded repeatedly across
your period: Central and Eastern Europe, then Central Asia and Mongolia, then the
Southern and Eastern Mediterranean (from 2012), then sub-Saharan Africa and Iraq
(approved 2023, first countries from 2025).

Each expansion required a Board of Governors resolution and often an amendment to
the Articles of Agreement. Sources: EBRD annual reports (the "where we work"
section and the financial statements' country breakdown), and Board of Governors
resolutions on the EBRD site. Code the *year each country became a country of
operations*, not just the region.

### 4.2 EIB — EU core plus external mandate

Two distinct regimes. Inside the EU, eligibility follows EU membership. Outside,
lending operates under successive External Lending Mandates authorised by
European Parliament and Council Decisions, each with an annex listing eligible
countries and regions.

Find the relevant Decisions on EUR-Lex (search "External Lending Mandate
European Investment Bank"), extract the country annexes, and code by mandate
period. The mandates changed several times inside 2002–2026, so this needs a
period-by-period table.

### 4.3 BADEA — a mechanical rule

BADEA lends to **non-Arab African countries**: African Union members that are not
Arab League members. This is codeable directly from two membership lists, with
the only judgement calls being the handful of AU members in the Arab League
(Algeria, Egypt, Libya, Mauritania, Morocco, Somalia, Sudan, Tunisia, Djibouti,
Comoros). Verify against BADEA's own list of beneficiary countries in its annual
report, and check whether recent mandate expansions have widened it.

### 4.4 AIIB — "Asia and beyond"

AIIB can finance projects outside the region where they benefit members, and it
has non-regional developing members (South Africa, Kenya, Morocco, Argentina,
Uruguay). Decide a rule and state it. Simplest defensible option: eligible =
member AND not high-income, which excludes the European non-regional members
while retaining the developing ones. Show robustness to the alternative of
restricting to regional members only.

---

## 5. Phase 3 — Window criteria (Component D)

Mostly derivable from OGHIST plus a few bank-specific lists.

| Bank | Rule | Source |
|---|---|---|
| **IDA** | GNI p.c. below operational cutoff; plus Blend, Gap, small-island exception | Annual IDA borrowing-country lists; IDA replenishment and Mid-Term Review documents give historical lists and graduation dates |
| **IBRD** | Above IDA cutoff, below graduation threshold, creditworthy | OGHIST lending category column handles most of this |
| **AfDB** | Country category A (ADF-only), B (blend), C (ADB-only) | AfDB Group annual reports; ADF replenishment documents |
| **AsDB** | ADF eligibility vs. OCR; DMC graduation | ADB graduation policy papers; annual reports |
| **IsDB** | ISFD concessional window vs. ordinary | IsDB annual reports |
| Others | No formal income window | — |

**Important structural decision.** If your commitment data pools each bank's
concessional and non-concessional windows into a single institution, the series
mixes two lending logics — the likeliest explanation for the multimodal
distributions you found for the AfDB and IDB. Splitting AfDB into AfDB/ADF and
AsDB into AsDB/ADF would give you sixteen institutions rather than fourteen, and
cleaner comparisons. Worth deciding before you build eligibility, since the
window rules differ by arm.

---

## 6. Phase 4 — Structural bars (Component E)

Genuine structural zeros that are not allocation decisions.

**Non-accrual status.** Countries in protracted arrears cannot receive new
lending. Every MDB's audited financial statements disclose this, usually in a
note headed "loans in non-accrual status" or "overdue amounts". Recurring cases
over your period include Zimbabwe, Sudan, Somalia, Syria, Myanmar, and Eritrea.
This is a per-bank, per-year list to extract while you are already parsing
annual reports for capital tables — do both passes at once.

**Sanctions and suspensions.** Document-and-code by event:

- World Bank: Russia and Belarus, operations halted March 2022; Afghanistan
  post-August 2021; Myanmar post-February 2021
- EBRD: Russia and Belarus, new investment suspended 2014 and again 2022
- NDB: Russia lending put on hold, March 2022
- Various: Syria, Iran, DPRK across the period

Sources: bank press releases and annual report subsequent-events notes. This is
maybe twenty events total — a manual table is fine and faster than automation.

**Arrears vs. decision.** Be careful: a country in arrears but still receiving
some lending is a decision, not a bar. Code `barred = True` only where the bank
states new commitments were suspended.

---

## 7. Validation

Run all four before estimating anything:

1. **Revealed-eligibility assertion** (§2.1). Zero violations required.
2. **Panel balance check.** Plot the count of eligible dyad-years per bank per
   year. Discontinuities should correspond to documented accessions or mandate
   changes. Unexplained jumps are coding errors.
3. **Zero share per bank.** Compute the proportion of eligible dyad-years with no
   lending, by bank. If a bank shows above ~95% zeros, its eligibility set is
   probably too wide — likely the membership-vs-borrowing confusion from §3.4.
4. **Spot-check against annual reports.** For three banks and three years, verify
   your eligible-country count against the number of borrowing members stated in
   the annual report.

---

## 8. Sequencing and effort

Ordered so that the highest-value work happens first, and so that a partial
result is still usable if time runs short.

| Step | Work | Est. | Blocking? |
|---|---|---|---|
| 1 | Build full grid; revealed eligibility; assertion harness | 0.5 day | Yes |
| 2 | OGHIST + income thresholds → Component D for IBRD/IDA | 0.5 day | Yes |
| 3 | COW IGO extraction for 2002–2014 | 0.5 day | No |
| 4 | Current member/borrower lists for all 13 banks | 1 day | Yes |
| 5 | Accession dates for the four high-variation banks | 1 day | Yes |
| 6 | Annual report scraping: capital tables + non-accrual | 3–5 days | Partly |
| 7 | EBRD countries of operations timeline | 1 day | Yes |
| 8 | EIB external mandate periods | 1 day | Yes |
| 9 | Sanctions/suspension event table | 0.5 day | No |
| 10 | Validation and reconciliation | 1 day | Yes |

**Roughly 10–12 working days** for the full version.

**If time is short**, steps 1, 2, 4, 5, 7, 8 and 10 (about 5 days) give you a
defensible eligibility panel. Step 6 is the expensive one; it can be deferred by
using current shareholder weights as a static approximation and treating
non-accrual countries as eligible, provided both simplifications are stated as
limitations and tested in robustness checks.

---

## 9. Documentation for the thesis

Two appendix items, both of which strengthen the paper against the obvious
objection that your finding is an artefact of data construction:

**Appendix A — Eligibility rules table.** One row per bank: membership basis,
geographic scope, window criteria, sources, and any judgement calls.

**Appendix B — Panel construction summary.** Number of eligible dyad-years per
bank, share with positive lending, and first and last year of coverage.

Also state in the main text that eligibility is applied as a *sample restriction*
rather than a covariate, and why — because the alternative would manufacture
apparent divergence in organisational logics out of nothing more than differences
in institutional mandate.
