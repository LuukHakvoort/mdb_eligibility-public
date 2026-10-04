# Setting up Claude Code to build the eligibility scraper

## The core idea

Don't paste the plan into a chat prompt. Claude Code reads files, so the plan
should live **in the repo as a file**, and `CLAUDE.md` should tell Claude Code
that it exists. Context pasted into a prompt is lost between sessions; context in
files persists across every session, every compaction, and every new terminal.

The same applies to the old scraper. Rather than describing your conventions in
prose, put the repo on disk where Claude Code can read it, and have it derive the
conventions itself.

---

## Step 1 — Directory layout

Put both repos under one parent so Claude Code can read across them:

```
~/thesis/
├── mdbs_scraper_corrected/      # existing repo, READ ONLY
└── mdb_eligibility/             # new repo, where you run Claude Code
    ├── CLAUDE.md
    ├── docs/
    │   ├── eligibility_plan.md          # the data collection plan
    │   ├── methods_section.md           # why the panel is built this way
    │   └── reference_conventions.md     # generated in Step 2
    ├── data/
    │   ├── manual/                      # hand-maintained CSVs
    │   ├── raw/                         # scraped, gitignored
    │   └── output/
    ├── src/
    └── tests/
```

Run `claude` from `~/thesis/mdb_eligibility/`. When it needs the old repo, it can
read `../mdbs_scraper_corrected/`. If you'd rather keep everything in one place,
clone the old repo into `reference/` and gitignore it — but the sibling layout is
cleaner because it makes accidental edits to the old repo obvious.

Copy `eligibility_data_collection_plan.md` and `methods_section_draft.md` into
`docs/` before you start.

---

## Step 2 — Learning session (do this first, on its own)

The single most useful thing you can do is make "study the old repo" a **separate
session that writes a document and no code**. If you combine it with building,
Claude Code will skim the reference and start writing, and you'll get generic
scraper code rather than code that matches your conventions.

Start Claude Code, enter plan mode (`shift-tab` twice), and give it:

> Read the repository at `../mdbs_scraper_corrected/` thoroughly. Don't write any
> code yet.
>
> I'm about to build a separate project that scrapes MDB eligibility data —
> membership lists, country classifications, annual report tables. It should feel
> like it was written by the same person as the existing scraper.
>
> Write `docs/reference_conventions.md` documenting:
>
> 1. Project structure and how modules are organised
> 2. Naming conventions for files, functions, variables
> 3. How HTTP requests are made — libraries, retries, timeouts, rate limiting,
>    user agents
> 4. How Playwright/Chromium is set up and reused, if at all
> 5. How raw responses are cached, if at all
> 6. Error handling and logging patterns
> 7. How country names are normalised to ISO codes
> 8. How currency conversion and deflation are handled
> 9. Output file formats and schemas
> 10. Config management — where bank-specific settings live
> 11. Testing approach, if any
> 12. Anything reusable I should import or copy rather than rewrite
>
> For each, quote a short representative example. Flag anything you'd do
> differently and why, but keep the recommendation and the description separate.

Read the output yourself before continuing. It's also a free code review of the
existing scraper, and it will surface things worth fixing there.

---

## Step 3 — Architecture session

New session. Still plan mode.

> Read `CLAUDE.md`, `docs/eligibility_plan.md`, and
> `docs/reference_conventions.md`.
>
> Propose an architecture for this repo. Key constraint: this is **not** primarily
> a scraping project. Roughly half the data should be hand-maintained CSVs under
> version control — accession dates, mandate expansion years, sanctions events —
> because they're small, stable, and require judgement. Only annual report tables,
> Wayback membership snapshots, and the World Bank classification files should be
> scraped.
>
> Tell me, for each of the five eligibility components in the plan, whether it
> should be scraped, downloaded once, or hand-maintained. Then propose the module
> structure. Don't write code yet.

Push back on anything that proposes a scraper for data you'd sooner type by hand.
The accession dates for thirteen banks are a hundred-odd rows; scraping them is
slower and less reliable than looking them up.

---

## Step 4 — Build, in the plan's phase order

One session per phase, matching the plan. Start each with a fresh context and a
concrete deliverable. Suggested order:

| Session | Deliverable |
|---|---|
| 1 | Repo skeleton, config, country-code normalisation, the full (bank, iso3, year) grid |
| 2 | **Validation harness first** — revealed-eligibility assertion, panel balance checks, zero-share report. Write these before the data exists so they fail loudly. |
| 3 | World Bank OGHIST + income threshold ingestion (Component D) |
| 4 | Manual CSVs: accession dates, mandate timelines, sanctions events (Components B, C, E) |
| 5 | COW IGO v3 ingestion and cross-check against the manual membership data |
| 6 | Annual report PDF pipeline: capital subscription tables + non-accrual lists |
| 7 | Wayback membership reconstruction for AIIB, NDB, CAF |
| 8 | Combine components → `eligibility.csv`; run full validation; write appendix tables |

Writing the validation harness second is deliberate. The revealed-eligibility
assertion from the plan is the strongest check you have, and having it in place
before the data lands means every subsequent session gets immediate feedback.

---

## Step 5 — Practical notes

**Caching is mandatory.** You'll re-run the annual report pipeline many times.
Every fetch should write to `data/raw/` keyed by URL hash and check the cache
first. Say this in `CLAUDE.md` or Claude Code will write code that re-downloads
several hundred PDFs on every run.

**Be polite to the sources.** Rate limit, set a real user agent with your contact
details, respect robots.txt. You're hitting institutional sites repeatedly from a
university connection.

**Commit the manual CSVs and review the diffs.** They encode judgement calls.
Version control is your audit trail for the thesis appendix.

**Keep `coding_decisions.md` in the repo**, and tell Claude Code to append to it
whenever it makes a judgement call. This becomes Appendix A more or less directly.

**Don't let it invent data.** Add an explicit instruction: if a membership date or
mandate year can't be verified from a source, leave it null and log it to
`data/manual/unresolved.csv` rather than guessing. This matters more here than in
most projects, because a plausible-looking wrong accession year will silently
corrupt your panel and you'll never notice.

**Use `/clear` between phases.** Each phase is independent; carrying context
forward just crowds out the files it needs to read.

---

## Step 6 — Connecting the two repos later

Once the eligibility data exists, the project scraper output and the eligibility
panel need to be merged on (bank, iso3, year). Two things to settle early, ideally
by making the eligibility repo import the normalisation module from the old repo
rather than reimplementing it:

- **Bank codes must match exactly** across both repos. Fix the canonical list
  now, including the split arms (IBRD, IDA, AfDB, ADF, AsDB, AsDF, …).
- **Country normalisation must be identical.** If the two repos handle Kosovo,
  Serbia/Montenegro, South Sudan, or Timor-Leste differently, the merge will
  silently drop rows.

Make the merge-and-validate step its own small script in the eligibility repo, and
have it fail loudly rather than dropping unmatched rows.
