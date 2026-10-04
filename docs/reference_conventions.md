# Reference conventions: `../mdbs_scraper_corrected/`

This documents how the existing project-level scraper is written, so the eligibility repo reads as if the same person wrote it. Originally based on the code as read on 2026-09-15 (HEAD `d86365a`); updated 2026-09-17 against HEAD `9a0d439` after ten commits of rework, several of them fixes this document itself recommended (a copy of it, `docs/reference_conventions copy.md`, was used as a to-do list in that repo). This is a one-way sync — that copy is not being kept current from here. File paths are relative to `../mdbs_scraper_corrected/`.

Each section has two parts, kept strictly apart:

- **Observed** is what the scraper does, with a short quote.
- **Would do differently** is a recommendation for this repo (and sometimes for the scraper).

Appendix A lists defects found in the scraper along the way.

---

## 0. Read first: four facts that affect the merge

1. **Bank codes do not match `docs/CLAUDE.md`.** The scraper's `bank_id` values are lowercase: `adb afdb aiib badea cabei caf cdb ebrd eib ibrd ida idb isdb ndb`, plus `imf`, which is disabled. Its `bank_abbreviation` values are `ADB AfDB AIIB BADEA CABEI CAF CDB EBRD EIB IBRD IDA IDB IsDB NDB`.
   - No `AsDB`, `ADF` or `AsDF` code exists anywhere in the scraper.
   - **AfDF** rows can be recovered from `afdb` rows, but only through the `funding_window` column (`"African Development Fund"`). That value can also be `"; "`-joined with other windows, in which case `concessional` is `Blended`.
   - **AsDF** cannot be separated at all. `funding_window` is blank on every `adb` row; only `concessional` (from IATI flow type) exists.
   - `cabei` is scraped but is not in the eligibility code list.

   "Must match exactly" therefore needs an explicit crosswalk, not string equality.
2. **Resolved 2026-09-16 (`854d58e`).** The country normaliser used to miss every name in this list: `United Kingdom`, `United States`, `Netherlands` / `The Netherlands`, `Turkey`, `Cape Verde`, `The Gambia`, `The Bahamas`, `British Virgin Islands`, `Micronesia`, `Palestine`, `Korea, Rep.`, `Egypt, Arab Rep.`, `Yemen, Rep.`, `Congo, Dem. Rep.`, `Congo, Rep.`, `Venezuela, RB`, `Hong Kong SAR, China`, `Macedonia, FYR`, `Taiwan, China` — all now resolve (re-verified live 2026-09-17). ~25 aliases were added, including two this document didn't originally catch: IsDB's "Iran"/"U.A.E." and a double-encoded "TÃ¼rkiye" mojibake from ADB, repaired at read time. Still deliberately unmapped, matching the policy this document already recommended: `Czechoslovakia`, `Yugoslavia`, `Serbia and Montenegro` — each splits into multiple successor states with no single correct answer. See §7.
3. **Partially built since.** A raw-response cache and FX/deflation still don't exist for *this repo's* purposes (build them here, §5/§8), but the scraper itself now has: a configurable user-agent contact (`MDBS_SCRAPER_CONTACT`, §3), and its own currency/deflation pipeline for project amounts (`reference.py`/`dyad.py`, §8) — useful reference infrastructure, not a substitute for what this repo needs. robots.txt handling is still absent everywhere.
4. **Still true.** The shared number parser still misreads three-decimal numbers: `parse_decimal("0.123")` returns `123` and `parse_decimal("12.345%")` returns `12345`. This was fixed for the specific case of a number immediately before an English magnitude word (`"1.448 billion"`, §8) and for EBRD specifically (a per-bank `amount_period_is_decimal` override, after this exact bug inflated its 2002-2026 total roughly tenfold — confirmed live). The general bare-number case is unchanged. Voting-power and share percentages in capital subscription tables are exactly this shape; never feed them through this parser without `period_is_decimal=True`. See §8.

---

## 1. Project structure and module organisation

### Observed

```
mdbs_scraper_corrected/
├── main.py                  # 7-line shim: from mdbs_scraper.cli import main
├── pyproject.toml           # setuptools; zero core deps; extras xlsx/browser/dev; script mdb-scrape
├── requirements.txt
├── mdbs_scraper/
│   ├── __init__.py __main__.py
│   ├── errors.py            # exception hierarchy (no internal imports)
│   ├── http.py              # stdlib HTTP client: retries, per-host throttle
│   ├── browser.py           # optional Playwright helpers
│   ├── cleaning.py          # text/number/date/currency normalisation (pure functions)
│   ├── parsers.py           # stdlib HTMLParser: links, tables, label/value pairs
│   ├── tabular.py           # CSV/TSV/JSON/XML(IATI)/XLSX -> list[dict]
│   ├── iati_geography.py    # country/region codelists + ISO-3 derivation
│   ├── dac_sectors.py       # OECD DAC sector codelists + category mapping
│   ├── schema.py            # ProjectRecord dataclass, validate(), to_row()
│   ├── config.py            # loads banks.json / year_filter.json into frozen dataclasses
│   ├── banks.json           # bank registry + per-bank knobs (data, not code)
│   ├── year_filter.json     # default 2002-2026 scope
│   ├── base.py              # ScrapeOptions, LoadedSource, BaseScraper (finalize/dedupe/notes)
│   ├── registry.py          # bank_id -> adapter class; fails at import on mismatch
│   ├── output.py            # CSV/JSON/XLSX writers, sha256, coverage summary
│   ├── report.py            # per-bank markdown quality report
│   ├── cli.py               # argparse, per-bank isolation, manifest.json
│   └── adapters/
│       ├── common.py        # FIELD_ALIASES, generic_record_from_row, reusable base scrapers
│       └── <bank_id>.py     # one file per bank; many are 7-15 lines (`pass` subclasses)
├── tests/                   # unittest, one file per module/bank, fixtures/ subdir
└── docs/                    # PROBLEMS.md (issue log), VALIDATION.md, CHANGES_*.md
```

The layering runs one way: `errors` → `http`/`browser` → `cleaning`/`parsers`/`tabular`/codelists → `schema` → `base` → `adapters/common` → `adapters/<bank>` → `registry` → `cli`.

Generic behaviour lives in reusable base classes (`TabularScraper`, `CkanOrganizationScraper`, `HTMLPortfolioScraper`). A bank gets its own module only for bespoke logic. Wiring is explicit and fails at import time:

```python
# mdbs_scraper/registry.py:43
_missing = set(BANKS) - set(SCRAPER_CLASSES)
if _missing:  # fail during development, not mid-collection
    raise RuntimeError(f"Adapter registry mismatch; missing concrete adapters for: {_missing}")
```

Every adapter has the same template-method shape: `scrape()` collects, `finalize()` normalises, dedupes and validates, and `run()` does both.

```python
# mdbs_scraper/base.py:78
    @abstractmethod
    def scrape(self) -> list[ProjectRecord]:
        """Collect unfinalized records from the bank-specific source."""

    def run(self) -> list[ProjectRecord]:
        return self.finalize(self.scrape())
```

### Would do differently

- Keep the one-way layering, the tiny `errors.py` at the bottom, and "data in JSON, behaviour in Python".
- The scraper is organised **by bank**. Eligibility data is organised **by source and component**: OGHIST, Wayback, annual reports, and manual CSVs feed components A–E. Don't force a `adapters/<bank>.py` tree onto that. The architecture session (setup guide step 3) should decide the layout; this doc only notes the mismatch.
- The scraper is a flat package at the repo root. This repo already has `src/`. Either is fine; pick one and note it in `coding_decisions.md`.

---

## 2. Naming conventions

### Observed

| Thing | Convention | Examples |
|---|---|---|
| Core modules | short noun per concern | `http.py`, `cleaning.py`, `parsers.py`, `tabular.py`, `schema.py`, `output.py`, `report.py` |
| Reference-table modules | named after the standard | `iati_geography.py`, `dac_sectors.py` |
| Adapter files | lowercase bank id | `adapters/afdb.py`, `adapters/isdb.py` |
| Adapter classes | `<Abbreviation>Scraper`, keeping the institution's casing | `AfDBScraper`, `IsDBScraper`, `CABEIScraper`, `IBRDScraper` |
| Functions | `verb_noun` | `parse_amount`, `normalize_text`, `extract_links`, `write_csv`, `load_source` |
| Lookups/derivations | `x_from_y` | `country_name_from_code`, `alpha3_from_alpha2`, `iso3_country_code_from_name`, `format_from_content_type` |
| Private helpers/methods | leading `_` | `_money`, `_throttle`, `_records_from_payloads`, `_listing_pages` |
| Public constants | `UPPER_SNAKE` | `USER_AGENT`, `FIELD_ALIASES`, `BANKS`, `STANDARD_FIELDS`, `IATI_COUNTRY_CODES` |
| Module-private constants | `_UPPER_SNAKE` | `_PAGE_SIZE`, `_REGISTRY_PATH`, `_AFDB_GROUP_WINDOW_REFS` |
| Logger | module-level `LOG` | `LOG = logging.getLogger(__name__)` |
| Variables | full words, no abbreviations | `response`, `payload`, `rows`, `row`, `record`, `fields`, `source`, `bank` |
| Booleans | adjective or `x_is_y` | `dynamic`, `enabled`, `include_raw`, `day_first`, `amount_period_is_decimal` |
| Provenance flags | `<field>_from_<origin>` | `country_from_code`, `status_from_code`, `sector_from_dac_code` |
| Output columns | snake_case, companions by suffix | `loan_amount` / `loan_currency` / `loan_amount_usd`; `concessional` / `concessional_flag`; `interest_rate` / `interest_rate_pct` |
| Coverage counters | `with_<field>` | `with_sector`, `with_cofinancing` |
| Output files | `{bank_id}_<thing>.<ext>` | `afdb_projects.csv`, `reports/afdb_quality.md` |
| Multi-value cells | `"; "`-joined, deduplicated case-insensitively | `join_values()` |
| Tests | `test_<module or bank>.py`; methods read as full sentences | `test_a_disclosed_window_outranks_a_contradictory_flow_type` |

Dataclasses are `@dataclass(slots=True)`; config dataclasses are also `frozen=True`. Most modules start with `from __future__ import annotations` and use builtin generics (`dict[str, str]`, `X | None`).

**Comment and docstring style** is a defining trait. Module docstrings explain *why* a source was chosen. Inline comments record the live evidence behind each rule, often dated, with `--` as the dash:

```python
# mdbs_scraper/adapters/common.py:415
    if bank_abbreviation and cofinancing_partners:
        # A funder can be the reporting bank itself, disclosed under its own
        # abbreviation rather than its full name (confirmed live: EIB lists
        # itself as "EIB", not "European Investment Bank", on 67% of its
        # activities) -- not a real external cofinancier.
```

Other traits:

- No linter or formatter config exists. Lines are mostly ≤110 characters.
- Commit subjects are imperative ("Fix EIB undercounting its portfolio by ~12x"), with a body explaining the root cause.

### Would do differently

- Keep all of the above, including the "confirmed live (date)" comments. For a thesis appendix they are the audit trail.
- Bank codes are the one place to deliberately diverge. This repo's canonical codes (`AsDB`, `ADF`, …) should live as data, with an explicit crosswalk to the scraper's `bank_id` and `funding_window` (see §0.1 and §10). Don't rename anything in the scraper.
- If you add a formatter, set the line length to ~110 so new code doesn't look reflowed next to old code.

---

## 3. HTTP requests

### Observed

- **Library:** standard library only (`urllib.request`); no `requests`/`httpx`. One class, `HttpClient` (`mdbs_scraper/http.py:128`).
- **Defaults:** timeout 45 s, 0.75 s minimum gap between requests **to the same host**, 3 retries (4 attempts in total). `--timeout` and `--request-delay` override the first two per run.
- **Retries:**
  - Retried: HTTP 408/425/429/500/502/503/504, plus any `URLError`/`TimeoutError`/`OSError`.
  - Backoff is `2**attempt + random()`, capped at 30 s.
  - `Retry-After` is honoured only in integer-seconds form.
  - The final failure raises `SourceError` naming the URL.
- **Throttle (changed 2026-09-16, `854d58e`):** a module-level `_HOST_LAST_REQUEST` dict behind a per-host lock, not an instance attribute. Throttling is now shared across every `HttpClient` in the process, so a `--parallel` run hitting one host from several banks (e.g. `iatiregistry.org` serves four) is actually coordinated.
- **Headers:** `User-Agent`, `Accept` (callers pass e.g. `"application/json"` or `"text/html"`), `Accept-Encoding: gzip` (decompressed manually).
- **User agent (changed 2026-09-16):** the contact now comes from the `MDBS_SCRAPER_CONTACT` environment variable, adopted from this document's own §3 recommendation. It's optional, not enforced: unset, a warning is logged once per process and the user agent carries "no contact configured" instead of failing the run.
- **Response decoding:** `HttpResponse.text()` tries the declared charset, then `utf-8-sig`, `utf-8`, `latin-1`.
- **TLS quirk handling:** if a server omits its intermediate certificate, the client fetches it from the leaf's AIA URL and retries with full verification. Verification is never disabled.
- **Retry-After (changed 2026-09-16):** now parses both legal forms — delta-seconds and an HTTP-date — via `_retry_after_seconds()`.
- **Fetch logging (new 2026-09-16):** every successful fetch (method, URL, status, byte count, sha256, timestamp) is appended to a module-level `_FETCH_LOG`, read back into `manifest.json`'s input-hash trail. `--save-raw DIR` additionally archives raw response bodies to disk.
- **Not present:** robots.txt checks. Response caching (beyond `--save-raw`, which is an archive, not a cache with a lookup path) and conditional requests (ETag/If-Modified-Since) are still absent.

```python
# mdbs_scraper/http.py:29-42
CONTACT_ENV_VAR = "MDBS_SCRAPER_CONTACT"
_USER_AGENT_BASE = "MDB-Thesis-Scraper/2.0 (+academic research"

def build_user_agent() -> str:
    """The one user agent every request (HTTP and browser) sends.

    The contact comes from the MDBS_SCRAPER_CONTACT environment variable
    (e.g. an e-mail address) so it is never committed. Unset, the agent says
    so plainly rather than promising a contact that does not exist.
    """
    contact = os.environ.get(CONTACT_ENV_VAR, "").strip()
    return f"{_USER_AGENT_BASE}; contact: {contact})" if contact else f"{_USER_AGENT_BASE}; no contact configured)"
```

```python
# mdbs_scraper/http.py:268 (trimmed)
    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc.lower()
        with _host_lock(host):
            elapsed = time.monotonic() - _HOST_LAST_REQUEST.get(host, 0.0)
            wait = self.request_delay - elapsed
            if wait > 0:
                time.sleep(wait)
            _HOST_LAST_REQUEST[host] = time.monotonic()
```

Pagination is written inline per adapter as a `while True` loop that stops on a short page.

### Would do differently

- **Check robots.txt** with stdlib `urllib.robotparser`, cached per host — the one recommendation from this section not yet adopted anywhere.
- **Make the contact mandatory, not just warned-about**, if this repo wants a harder guarantee than the scraper settled for: fail at startup if unset, rather than logging a warning and proceeding with "no contact configured."
- **`--save-raw`'s archive-by-URL-hash is not yet a cache** — nothing checks it before fetching. This repo's own cache (§5) needs a lookup path the scraper's version doesn't have.
- Log each request at DEBUG: method, URL, status, bytes, cache hit/miss — the scraper's fetch log records this after the fact, into the manifest, but doesn't surface it live at DEBUG either.
- Keep the stdlib-only approach and the retry/backoff numbers, and the newly-adopted process-wide throttle and dual-form `Retry-After` parsing. They are sensible and the new repo should behave the same.

---

## 4. Playwright / Chromium

### Observed

- **Optional dependency.** Playwright is the `browser` extra and is imported lazily inside each function. If it is missing, the call raises `OptionalDependencyMissing` with the exact install command.
- **Three helpers in `browser.py`:**
  - `render_page`: renders the page, captures JSON responses up to 25 MB, and scrolls up to 12 times to trigger lazy loading.
  - `download_via_browser`: navigates to a file URL and captures either the download or the inline body.
  - `download_from_last_button`: clicks the last visible exact-text "Download" control.
- **Nothing is reused.** Every call opens `sync_playwright()`, launches Chromium, creates a context and page, and closes both. There is no shared browser, context, or storage state.
- **Launcher (unified 2026-09-16):** `launch_chromium` (public now, was `_launch_chromium`) globs for a macOS cached "Google Chrome for Testing" binary and falls back to Playwright's default. All four call sites — `render_page`, both download helpers, and `adapters/badea.py` — now go through it; none bypasses it any more.
- **User agent (fixed 2026-09-16):** all four call sites now send `build_user_agent()` — the same contact-bearing agent HTTP uses (§3) — instead of BADEA/`render_page` sending one literal string and the download helpers sending Chromium's default.
- **Opt-in** is per bank: `"dynamic": true` in `banks.json`.
- **Error wrapping:** `PlaywrightError` becomes `SourceError`.
- **Per-process isolation (new 2026-09-16, `f0c48c1`):** a browser-driven bank (`aiib`/`badea`/`ebrd`) now runs in its own child process whenever more than one bank is requested, via `python -m mdbs_scraper --bank X --child-result FILE`, its result read back through a pickle. This replaces the old in-process retry, which could not recover from the documented macOS crash (several `sync_playwright()` launches sharing one process can segfault — a real `fork()` crash inside Apple's Network.framework, not a catchable Python exception). Getting the isolation itself right took two attempts: the first still crashed every child, because `subprocess.run()`'s default `fork()` on macOS segfaults once the parent has touched networking frameworks, which ordinary scraping does. `close_fds=False` with no `cwd` makes CPython use `posix_spawn` instead, which runs no atfork handlers — confirmed fixed live (`--banks adb badea`, previously crashed every BADEA child). One retry remains, now of the whole isolated subprocess rather than an in-process object.

```python
# mdbs_scraper/browser.py:51-72 (trimmed)
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise OptionalDependencyMissing(
            "This bank's portal requires Playwright. Run: python -m pip install '.[browser]' "
            "and then: playwright install chromium"
        ) from exc
    ...
        with sync_playwright() as playwright:
            browser = launch_chromium(playwright, headless=headless)
            context = browser.new_context(
                locale="en-US",
                user_agent=build_user_agent(),
                accept_downloads=False,
            )
            page = context.new_page()
            page.set_default_timeout(int(timeout * 1000))
            ...
            context.close()
            browser.close()
    except PlaywrightError as exc:
        raise SourceError(f"Browser rendering failed for {url}: {exc}") from exc
```

```python
# mdbs_scraper/cli.py:279-291 (trimmed)
def _run_bank_isolated(args: argparse.Namespace, bank_id: str) -> tuple[list[ProjectRecord], dict]:
    last_error = ""
    for attempt in range(2):
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.pickle"
            # close_fds=False and no cwd let CPython use posix_spawn on macOS
            # instead of fork: a forked child segfaults (exit -11) once the
            # parent has used macOS networking frameworks with fork handlers,
            # which happens during ordinary scraping (confirmed 2026-09-16:
            # --banks adb badea crashed every BADEA child). Python opens its
            # own files non-inheritable, so nothing leaks into the child.
            completed = subprocess.run(_child_argv(args, bank_id, result_path), close_fds=False, check=False)
```

### Would do differently

- **Avoid Playwright in this repo unless a source proves it's needed.** OGHIST and the income-guideline files, annual report PDFs, the Wayback CDX API and snapshots, and EUR-Lex are all static HTTP. Snapshots served by `web.archive.org` with an `id_` suffix return the original bytes without the Wayback toolbar.
- If a JS-only page is unavoidable, the scraper's own current state (all adopted since this was first written) is now the pattern to copy directly, not just describe in the abstract:
  - Keep the lazy import and the install message.
  - Use one public launcher everywhere — no per-call-site duplication.
  - Send the same contact-bearing user agent as HTTP (`build_user_agent()`).
  - Write the rendered HTML or downloaded bytes into the raw cache (§5), so the browser runs once per URL, not once per pipeline run — the scraper's `--save-raw` is an archive, not this; a real cache with a lookup path still needs building here.
  - Run each browser job in its own subprocess, `posix_spawn`-launched (`close_fds=False`, no `cwd`) rather than the default `fork()`, which segfaults on macOS once the parent process has touched networking frameworks — confirmed the exact fix, not just a plausible one.

---

## 5. Raw response caching

### Observed

There is no cache. Every run re-fetches every page and file. The nearest mechanisms:

- **`--source-file BANK=PATH` snapshots** (`base.py:62-67`). A hand-saved official download replaces the network fetch. This is also how the whole test suite runs offline.
- **`--include-raw`** appends a per-row `source_fields_json` column to the *output*, not the raw response.
- **`manifest.json`** records SHA-256 of *output* files only, not inputs.
- **`docs/VALIDATION.md`** recommends manually keeping "unchanged official downloads, dated in filenames" under `data/raw/`.
- Browser downloads are read into memory and discarded.
- **New 2026-09-16, still not a cache:** `--save-raw DIR` archives every fetched body, and `manifest.json` now records each fetch's sha256 (§3). This is a write-only archive with no lookup path — nothing checks it before fetching, so a re-run still re-fetches everything. The gap this section flags is unchanged.

```python
# mdbs_scraper/base.py:62
        if self.options.source_file:
            path = Path(self.options.source_file).expanduser()
            if not path.is_file():
                raise SourceError(f"Local source file does not exist: {path}")
            fmt = self.options.source_format or infer_format(str(path), source_format or self.bank.source_format)
            return LoadedSource(path.read_bytes(), path.resolve().as_uri(), fmt)
        target = self.options.source_url or url or self.bank.source_url
        response = self.client.get(target, accept=accept)
```

### Would do differently

This repo requires a cache (`docs/CLAUDE.md`: "Cache every fetch"). A shape that fits the scraper's style:

- **Wrap, don't fork, the client.** A `CachedHttpClient` (or a `fetch()` function) checks the cache *before* throttling and only calls `HttpClient.get` on a miss.
- **Key** = `sha256` of the URL, including the query string. For POST, hash method + URL + body. Store the body at `data/raw/<key>.<ext>`, with a sidecar `data/raw/<key>.json` holding:
  - `url` and `final_url`
  - `status` and `content_type`
  - `fetched_at` (in `utc_now()` format)
  - `sha256` of the body
- **Cache only 2xx responses.** Write to a temp file and rename, so an interrupted run never leaves a truncated PDF that is treated as a hit.
- **Add `--refresh`** (all entries, or a URL pattern) to force a re-fetch. The default is cache-forever. That is correct for timestamped Wayback URLs, which are immutable, and for dated annual-report PDFs.
- **Record every raw file's hash in `manifest.json`.** This closes the gap above: the outputs become provably tied to specific downloads. The scraper itself adopted exactly this for its own fetches (§3) after this recommendation, though still without the lookup-before-fetch that makes it a cache rather than an archive.
- Keep a `--source-file`-style override. Tests should feed fixtures the same way the scraper's tests do.

---

## 6. Error handling and logging

### Observed

**A typed hierarchy**, the whole of `errors.py`:

```python
class ScraperError(RuntimeError):
    """Base class for an expected collection failure."""

class SourceError(ScraperError):
    """The configured source could not be retrieved or decoded."""

class SourceLayoutChanged(ScraperError):
    """The source responded, but no longer matches the supported layout."""

class OptionalDependencyMissing(ScraperError):
    """A collector needs an optional dependency that is not installed."""

class ValidationError(ScraperError):
    """A record violates a non-negotiable schema rule."""
```

How each is used:

- **`SourceError`**: network, browser, missing local file, invalid JSON/XML. Low-level exceptions are chained with `raise ... from exc`.
- **`SourceLayoutChanged`**: the source answered but yielded zero records or lacks an expected structure. The message says what to do next:

  ```python
  # mdbs_scraper/adapters/common.py:913
              raise SourceLayoutChanged(
                  f"{self.bank.abbreviation}: no recognizable projects were exposed by the official "
                  "page. Save an official CSV/JSON export and rerun with --source-file BANK=PATH, "
                  "or update the bank adapter after verifying the site's new layout."
              )
  ```

- **`ValidationError`**: raised by `ProjectRecord.validate()` inside `finalize()`. Examples: missing id or name, year outside 1900–2200, negative amounts.
- **Per-bank isolation at the CLI boundary.** A broad `except Exception` stores `"{type}: {message}"` in `manifest.json["failures"]` and writes a failure report. The run exits with code **2** unless `--allow-partial` is passed. There is never a silent empty success.

  ```python
  # mdbs_scraper/cli.py:202
              try:
                  collected[bank_id] = _run_bank(args, bank_id)
              except Exception as exc:  # manifest must record bank-specific failures
                  LOG.error("%s failed: %s", bank_id, exc)
                  failures[bank_id] = f"{type(exc).__name__}: {exc}"
  ```

- **Optional enrichments degrade and warn** rather than fail:

  ```python
  # mdbs_scraper/adapters/worldbank.py:109
      except Exception as exc:  # noqa: BLE001 -- a bonus enrichment must not fail the primary scrape
          LOG.warning("Finances One loan-terms fetch failed for %s (interest_rate/last_repayment_date "
                      "will be blank this run): %s", asset_id, exc)
          return {}
  ```

- **Soft data problems are written into the data, not raised.** Blanks are never silent: `add_note` appends an explanation to `data_quality_notes`, deduplicated by `join_values`.

  ```python
  # mdbs_scraper/base.py:127
              if record.total_disbursement is None:
                  self.add_note(
                      record,
                      "Total disbursement is not exposed by this source; blank does not mean zero.",
                  )
  ```

- **Lookups never guess.** Codelist functions return `""` for unknown input instead of raising or approximating. The caller adds a note.

**Logging is sparse:**

- Only `cli.py` (`LOG = logging.getLogger("mdbs_scraper")`) and `adapters/worldbank.py` (`getLogger(__name__)`) log.
- `logging.basicConfig(level=DEBUG if --verbose else INFO, format="%(asctime)s %(levelname)s %(message)s")` runs once in `main()`.
- Messages use %-style arguments.
- The final summary is a `print`; failures go to stderr.
- **Fixed 2026-09-16:** `http.py` now logs every request and retry at DEBUG (method, URL, status/exception, byte count, attempt number), so `--verbose` does something. Still the only module that does.

There are a few silent swallows: `HTMLPortfolioScraper._records_from_payloads` does `except Exception: continue`, and `CkanOrganizationScraper.rows_from_source` returns `[]` on undecodable JSON.

### Would do differently

- Keep the hierarchy and the fail-loud manifest/exit-code contract. Keep the "explain every blank" rule. In this repo it maps onto the `note` column plus `data/manual/unresolved.csv`.
- **An unresolved fact must not become a silent blank.** Where the scraper writes `""` and a note, this repo should write `null` **and** append a row to `unresolved.csv`. A small writer function makes that a one-liner.
- Add DEBUG logging for each fetch and cache hit/miss, plus an INFO summary per source (e.g. "OGHIST: 1 fetched, 0 cached, 218 countries, 3 unresolved names"). Use `getLogger(__name__)` everywhere, not a literal name.
- Keep broad `except Exception` only at the CLI boundary and for explicitly optional enrichments, with the same `# noqa: BLE001 -- reason` style.

---

## 7. Country names → ISO codes

### Observed

All logic lives in `mdbs_scraper/iati_geography.py`. The module has no internal imports.

Its data tables:

- **`IATI_COUNTRY_CODES`**: alpha-2 → name. 257 entries, generated from IATI's Country codelist, including withdrawn codes.
- **`IATI_ALPHA2_TO_ALPHA3`**: alpha-2 → alpha-3, sourced from `lukes/ISO-3166-Countries-with-Regional-Codes`.
- **`COUNTRY_NAME_TO_ISO2`**: 28 hand-curated aliases.
- **`_NAME_TO_ALPHA2`**: built from IATI names, plus a generic pass that strips a trailing `" (the)"`.

`iso3_country_code_from_name` then works in four steps:

1. Normalise the name: NFKD accent fold, lowercase, non-alphanumerics to spaces.
2. Match exact IATI names, with and without the `(the)` suffix.
3. Match the alias table.
4. Convert alpha-2 → alpha-3. Anything else returns `""`.

```python
# mdbs_scraper/iati_geography.py:640
def _normalize_geo_text(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()
```

```python
# mdbs_scraper/iati_geography.py:683
    if not name:
        return ""
    normalized = _normalize_geo_text(name)
    code = _NAME_TO_ALPHA2.get(normalized) or COUNTRY_NAME_TO_ISO2.get(normalized)
    return alpha3_from_alpha2(code) if code else ""
```

**Wiring.** In `generic_record_from_row` (`adapters/common.py:340-378`), a code the source disclosed is *not* trusted by default. IDB's `"PR"` means Peru, not Puerto Rico. The ISO-3 code is derived from the name text. The only exception is when the name itself came from an IATI alpha-2 code; that code is converted directly. World Bank and EIB build records themselves and call `iso3_country_code_from_name` directly (`worldbank.py:221`, `eib.py:105`).

```python
# mdbs_scraper/adapters/common.py:374
    if country_from_code:
        iso3_code = alpha3_from_alpha2(country_code)
    else:
        iso3_code = iso3_country_code_from_name(country)
    country_code_unresolved = bool(country) and not iso3_code
```

**Decisions already encoded** (verified by calling the function):

| Input | Result | Note |
|---|---|---|
| `Kosovo` | `XKX` | User-assigned code (no official ISO code); the World Bank uses the same |
| `Serbia` / `Montenegro` | `SRB` / `MNE` | |
| `Serbia and Montenegro`, `Yugoslavia` | `""` | Deliberately unmapped: "no single unambiguous successor state" |
| `South Sudan` / `Sudan` | `SSD` / `SDN` | |
| `Timor-Leste`, `East Timor` | `TLS` | |
| `Burma` → `MMR`; `Zaire` → `COD`; `Swaziland` → `SWZ` | | Historical names with one successor |
| `West Bank and Gaza` | `PSE` | Alias table |
| `Gambia, The`, `Bahamas, The` | `GMB`, `BHS` | Work by accident: they normalise to IATI's `"gambia the"` |
| `Regional`, `Africa, regional`, `OECS Countries` | `""` | Groupings are never guessed |

**Resolved 2026-09-16 (`854d58e`).** Every name below used to return `""`; all now resolve (re-verified live 2026-09-17). ~25 aliases were added, following exactly the recommendation this section used to end with (fix `COUNTRY_NAME_TO_ISO2` upstream, not a local wrapper) — a copy of this document in the scraper repo was the to-do list.

- **Plain names:** `United Kingdom` → `GBR`, `United States` → `USA`, `Netherlands`/`The Netherlands` → `NLD`, `Turkey` → `TUR`, `Cape Verde` → `CPV`, `The Gambia` → `GMB`, `The Bahamas` → `BHS`, `British Virgin Islands` → `VGB`, `Micronesia` → `FSM`, `Palestine` → `PSE`.
- **World Bank short forms:** `Korea, Rep.` → `KOR`, `Egypt, Arab Rep.` → `EGY`, `Yemen, Rep.` → `YEM`, `Congo, Dem. Rep.` → `COD`, `Congo, Rep.` → `COG`, `Venezuela, RB` → `VEN`, `Hong Kong SAR, China` → `HKG`, `Macedonia, FYR` → `MKD`, `Taiwan, China` → `TWN`.
- **Two this document didn't originally catch:** IsDB's `Iran`/`U.A.E.`, and a double-encoded `"TÃ¼rkiye"` mojibake from ADB, now repaired at read time rather than aliased.
- **Not checked this pass:** `Channel Islands`, `St. Martin (French part)`, `Korea, Dem. People's Rep.`, `Macao SAR, China` — these weren't in the ~25-alias diff's own worked examples; treat as unverified rather than assuming either way.

**Impact.** `output/all_mdb_projects.csv` had about **634 rows with a real single country but a blank `country_code`** as of 2026-08-25 (EIB's UK/Netherlands/Palestine/Cape Verde/… rows, CDB's own `The Bahamas`/`British Virgin Islands` canonical names from `adapters/cdb.py`). All of the specific cases this document identified are now fixed; a full recount hasn't been redone.

Still deliberately unmapped, unchanged: `Czechoslovakia`, `Yugoslavia`, `Serbia and Montenegro` — each splits into multiple successor states with no single correct answer, matching the policy this section already described for `XKX`/`COD`/`SWZ` above.

Also still true: a multi-country IATI activity keeps only its first `<recipient-country>`.

### Would do differently

- **Import this module; do not copy it** (§12). If the eligibility grid and the project data resolve a name differently, the merge drops rows silently. That is exactly the risk `docs/CLAUDE.md` names.
- **In this repo an unresolved name is an error, not a blank.** Wrap the import:
  1. `require_iso3(name, source)` calls `iso3_country_code_from_name`.
  2. On `""` it logs to `unresolved.csv` and raises (or returns `None`) under an explicit policy.
  3. The (bank, iso3, year) grid never receives a blank key.
- When a source ships its own codes (OGHIST has a code column), still cross-check that the name resolves to the same code. The IDB `"PR"` lesson applies, and World Bank files include non-ISO codes.
- Territorial changes need decisions logged in `coding_decisions.md` before building the grid:
  - Serbia and Montenegro, 2002–June 2006. The scraper leaves it unmapped, so project rows naming it will not merge regardless.
  - South Sudan, from 2011.
  - Kosovo, `XKX`.
- Add a test here that pins the §7 table above. It then fails loudly if an upstream change alters any mapping.

---

## 8. Currency conversion and deflation

### Observed

**A real pipeline now exists for project amounts, added 2026-09-16** (`reference.py`, `dyad.py`) — this is genuinely new since this document was first written, not a fix to something described here before:

- `reference.py` fetches and caches per-currency annual-average IMF exchange rates and the FRED US GDP implicit price deflator, committed under `mdbs_scraper/data/reference/` so a rebuild doesn't need a fresh network fetch; `--refresh-reference` re-downloads.
- `dyad.py` writes `all_mdb_projects_usd.csv` (every row plus nominal and constant-2025 USD, original columns untouched), and the `dyad_country_year*.csv` files (§12) carry USD totals by instrument category and concessionality.
- A bank-reported USD figure is used as-is; anything else converts at the approval year's IMF rate, then deflates by FRED's `D(2025)/D(approval_year)` ratio. 2026 is left unconverted (no published annual figure yet for either series).
- A scraped (non-official-file) non-sovereign amount labelled `"USD"`, above $1bn, in a country whose currency trades at 10+ per dollar is flagged `excluded-currency-suspect` and excluded from totals rather than converted — found live: ADB IATI mislabels several large local-currency amounts as USD (e.g. Indonesia rupiah reported as if it were dollars).

**Does this change the recommendation below?** No. This is project-amount infrastructure, useful if this repo's later analysis (beyond the eligibility panel itself) needs constant-USD lending comparisons — components B–E still need membership/shares/existence flags, not dollar totals, so the panel construction doesn't gain anything from importing it.

Everything below this point describes what the scraper does at the *individual project record* level, unchanged except where noted. The policy is stated in the README:

> Original currencies are preserved. USD fields are filled only when USD is explicit in the source; the code performs no undocumented FX conversion.

It is implemented as an explicit-USD check. `*_usd` is a copy of the amount when USD was stated, otherwise `None`:

```python
# mdbs_scraper/adapters/common.py:221
    explicitly_usd = currency == "USD" or "usd" in key or "us_dollar" in key
    return amount, currency, explicitly_usd
```

```python
# mdbs_scraper/adapters/common.py:451
        loan_amount=loan,
        loan_currency=loan_currency,
        loan_amount_usd=loan if loan_usd else None,
```

**Parsing helpers** (`cleaning.py`):

- **`parse_amount(value, default_currency)`** returns `(Decimal | None, currency_code)`. It expands magnitude words (`k`, `m`, `mn`, `million`, `millones`, `bn`, …) and understands US/European separators and parenthesised negatives.
- **`detect_currency` (fixed 2026-09-16, `854d58e`)** now checks, in order:
  1. symbols (`US$`, `€`, `£`)
  2. names (`SDR` → `XDR`, `UA` → `XUA`, `EURO` → `EUR`, `RMB` → `CNY` — new)
  3. an isolated three-letter token, **restricted to an ISO 4217 whitelist plus XDR/XUA** — no longer any three-letter uppercase token. It used to accept bank acronyms (`IDA`, `ADF`, `OCR`) and AIIB's literal `TBC`/`TBD` placeholders as if they were currencies; all now correctly return `""`.
- **Per-bank default currency** comes from `banks.json` (`"default_currency": "EUR"`). IATI values fall back to the activity's `default-currency`.
- Amounts stay `Decimal` end to end and are written as plain strings (`format(value, "f")`), never floats or scientific notation.

**Edge cases, verified by calling the functions** (these matter for annual report tables):

| Call | Result | Why |
|---|---|---|
| `parse_decimal("0.123")` | `123` | Still misreads a lone `.` followed by exactly 3 digits as a thousands separator — **unchanged** |
| `parse_decimal("12.345%")` | `12345` | Same rule, still unchanged |
| `parse_decimal("2.500")` | `2500` | Same rule, still unchanged |
| `parse_decimal("0.123", period_is_decimal=True)` | `0.123` | The escape hatch (`banks.json` `amount_period_is_decimal`) |
| `parse_decimal("(1,234.5)")` | `-1234.5` | Accounting negatives work |
| `parse_amount("1.448 billion")` | `(1448000000, "")` | **Fixed 2026-09-16**: a number immediately before an English magnitude word is now always read as a decimal point first, then multiplied — it used to apply the thousands-vs-decimal heuristic *before* the multiplier, reading this as 1.448 trillion. Confirmed live to have inflated EBRD (three-decimal EUR amounts) and NDB ("X.XXX billion" RMB amounts) by 1000x before the fix. Spanish `"millones"` deliberately keeps the old thousands-grouping reading, since Spanish sources legitimately write `"1.448 millones"` to mean 1,448 million. |
| `detect_currency("IDA credit")`, `("ADF grant")`, `("OCR loans")`, `("TBC")` | `""` | **Fixed** — see above |
| `detect_currency("ISD 500")` | `""` | IsDB's Islamic Dinar was never a real currency match here to begin with; now correctly blank rather than a false match |
| `parse_amount("UA 12.5 million")` | `(12500000.0, "XUA")` | |
| `parse_date("2015")` | `"2015-01-01"` | A bare year becomes 1 January |
| `parse_date("FY2015")` | `""` | Fiscal-year labels are not understood |
| `parse_date("03/04/2022")` | `""` | Ambiguous slash dates are refused unless `day_first` is set |

The bare-number bug (row 1) is the one that matters most for annual-report capital tables: voting-power and share percentages are exactly this shape, and it is **not** fixed by the magnitude-word change above, which only fires when a number is immediately followed by a word like "billion"/"million". A percentage or a plain subscribed-capital figure with three decimal places still needs `period_is_decimal=True` passed explicitly, or a dedicated parser that never touches this heuristic at all (§12's recommendation).

### Would do differently

- **The eligibility panel shouldn't need FX at all.** Use **shares or voting-power percentages** from capital subscription tables as weights. They are unitless and comparable across banks. Keep subscribed capital in its original currency and unit (USD, XDR, XUA, ISD, EUR; thousands vs millions) in separate columns, exactly as the scraper does.
- **Don't deflate income thresholds.** Compare Atlas GNI per capita (current USD) with the *same fiscal year's* threshold, both nominal. Record the fiscal-to-calendar year mapping once in `coding_decisions.md`.
- **If conversion is ever needed** (e.g. a USD capital series): make it a separate, documented step with year-specific rates from a cited source (e.g. IMF SDR rates), written to new `*_usd` columns. Never overwrite the original. This matches the scraper's philosophy.
- **Don't feed annual-report numbers through `parse_decimal`/`parse_amount` without `period_is_decimal=True`,** and never let `detect_currency` see row text containing bank acronyms. Pass the currency explicitly from the table header. Better still, write a table-specific numeric parser and test it against real extracted rows.

---

## 9. Output formats and schemas

### Observed

- **Schema is a dataclass.** `ProjectRecord` is `@dataclass(slots=True)`. Its field order *is* the CSV column order (`STANDARD_FIELDS`). Strings default to `""`; numbers are `Decimal | None`. `validate()` enforces invariants; `to_row()` serialises:
- **New fields, added 2026-09-16 (`cbc8e62`):**
  - `approval_year` — now the one year definition used for the 2002-2026 scope filter and for country-year aggregation, replacing ad-hoc `commitment_year`/`approval_date` use. `commitment_year` still exists alongside it, not replaced.
  - `instrument_category` — one of `loan`/`grant`/`technical_assistance`/`guarantee`/`equity`/`trade_finance`/`other`, keyword-classified from each source's own instrument wording (`instruments.py`). Never guesses; blank when nothing matches.
  - `official_source_id`, `source_record_ids` — an audit trail: which registered official file (if any) defines a record, and which scraped/official records were merged into it (§10, §12).
- **`validate()` now also requires `source_url`** (previously optional) and checks `instrument_category` against the known set — this document used to recommend exactly the `source_url` change ("would do differently," below).

  ```python
  # mdbs_scraper/schema.py:123
          for key, value in raw.items():
              if value is None:
                  row[key] = ""
              elif isinstance(value, Decimal):
                  row[key] = format(value, "f")
              else:
                  row[key] = value
  ```

- **CSV** is UTF-8 **with BOM** (`utf-8-sig`, for Excel/Stata/R), `newline=""`, `csv.DictWriter`:

  ```python
  # mdbs_scraper/output.py:26
      with path.open("w", encoding="utf-8-sig", newline="") as handle:
          writer = csv.DictWriter(handle, fieldnames=_fieldnames(include_raw), extrasaction="ignore")
  ```

- **JSON:** `indent=2`, `ensure_ascii=False`, trailing newline. **XLSX** (optional): bold header, frozen first row, auto-filter.
- **Dates** are ISO `YYYY-MM-DD` strings. **Timestamps** come from `utc_now()`: UTC, second precision, e.g. `2026-09-09T14:36:33+00:00`.
- **Yes/No values** get a text column plus a numeric companion: `concessional` is `Yes`/`No`/`Blended`, and `concessional_flag` is `1`/`0`/blank (blank for Blended, rather than forcing a side).
- **Blank means "not disclosed", never zero.** Every row carries provenance: `source_url` (the stable requested URL, not a short-lived redirect target), `source_format`, `source_updated_at`, `scraped_at`, `data_quality_notes`.
- **Row identity:** dedupe key `f"{bank_id}:{project_id}".casefold()`. When a source has no id, a labelled synthetic id is used: `"synthetic-" + sha256(url|name|country|date)[:16]`.

**Run artefacts** in `output/` (gitignored). New since 2026-09-16 are marked; the rest is unchanged:

- `{bank_id}_projects.csv`
- `all_mdb_projects.csv` (with `--combine`, or rebuilt standalone from existing per-bank files with `--combine-only` — new, see §12/Appendix A)
- `all_mdb_projects_usd.csv` — **new**: every row plus nominal and constant-2025 USD (§8)
- `dyad_country_year.csv`, `dyad_country_year_balanced.csv`, `dyad_unallocated_year.csv` — **new**, see §12
- `cabei_private_approvals_country_year.csv` — **new**, CABEI's private-sector approvals, disclosed only as country-year totals with no project ids
- `project_counts_and_coverage.csv`: `bank_id`, `status`, `error`, `project_count`, `with_<field>` counts, `rows_seen`, `rows_retained`, `duplicates_removed`, `source_total`, `completeness`
- `reports/{bank_id}_quality.md`: coverage percentages plus frequency of each distinct note combination
- `reports/coverage_by_year.csv`, `reports/backstop_summary.csv`, `reports/backstop_{bank_id}.md`, `reports/{bank_id}_reconciliation.csv` — **new**, §10
- `manifest.json`, whose top-level keys are shown here (new keys marked):

```json
{
  "schema_version": "2.0",
  "mode": "collect",
  "started_at": "...", "finished_at": "...",
  "git_commit": "9a0d439",
  "requested_banks": [...], "successful_banks": [...], "failures": {},
  "record_count": 8084,
  "bank_metadata": {"ebrd": {"rows_seen": 9415, "rows_retained": 8084, "duplicates_removed": 71,
                             "source_total": null, "completeness": "source-total-unavailable"}},
  "coverage_summary_path": "...",
  "outputs": {"ebrd": {"path": "...", "sha256": "73ee..."}},
  "inputs": [{"url": "...", "sha256": "...", "status": 200, "bytes": 12345}],
  "filters": {"min_year": 2002, "max_year": 2026},
  "source_overrides": {"files": {}, "urls": {}, "formats": {}},
  "backstop": {"passed": true}
}
```

`git_commit` and `inputs` are exactly this document's own earlier "would do differently" recommendation, adopted; `mode` and `backstop` are new (§10).

### Would do differently

- Keep: dataclass schema with `validate()`, `utf-8-sig` CSV, `Decimal` written as plain strings, ISO dates, `utc_now()`, blank-not-zero, `manifest.json` with SHA-256, and a markdown quality report per bank.
- **Booleans in `eligibility.csv`:** write `1`/`0`, with blank for null, to match `concessional_flag` and import into Stata without `destring`. `docs/CLAUDE.md` says `bool`; state the on-disk encoding once in `coding_decisions.md`.
- ~~Make `source` non-optional in `validate()`~~ — **adopted upstream 2026-09-16**: `validate()` now requires `source_url`. Still worth doing the equivalent for this repo's own `eligibility.csv` schema (`source` is already listed as required by `docs/CLAUDE.md`; enforce it in code, not just in the doc).
- ~~Hash inputs as well as outputs in the manifest, and record the scraper's git commit~~ — **adopted upstream 2026-09-16**: `manifest.json` now carries both. This repo's own manifest (`build_commitments.py`'s `commitments_manifest.json`) already does the git-commit part; extend it to hash manual CSVs too once they're being written to.
- Sort `eligibility.csv` by (`bank`, `iso3`, `year`), so reviewing diffs of the output is practical.

---

## 10. Config management

### Observed

- **All bank metadata and per-bank tuning is data** in `mdbs_scraper/banks.json`:
  - top level: `reviewed_on`, `aliases`, `banks[]`
  - per bank: `id`, `name`, `abbreviation`, `website`, `source_url`, `source_format`, `method`, `coverage_notes`, `dynamic`, `enabled`, plus optional knobs — now including `coverage_start_year`/`coverage_end_year` (added 2026-09-16)
  - `coverage_notes` doubles as a dated evidence log ("Confirmed live (2026-09-15): …")

  ```json
  {
    "id": "ndb",
    "name": "New Development Bank",
    "abbreviation": "NDB",
    "website": "https://www.ndb.int",
    "source_url": "https://www.ndb.int/projects/all-projects/",
    "source_format": "html",
    "method": "official-portfolio",
    "coverage_notes": "NDB published project cards and detail pages. Founded 2015; first approvals 2016.",
    "dynamic": false,
    "enabled": true,
    "day_first": false,
    "project_href_pattern": "ndb\\.int/project/(?!all-projects|page/)[^?#]+/?$",
    "pagination_href_pattern": "(?:/page/\\d+/?|[?&](?:page|paged)=\\d+)",
    "max_listing_pages": 60,
    "coverage_start_year": 2016
  }
  ```

  `coverage_start_year`/`coverage_end_year` mark **data coverage** in the source, not bank existence — they answer "does this feed have anything for this year," which is a different question from this repo's own Component A. Present for AIIB (`coverage_start_year: 2016` — genuinely also its founding year), NDB (as above), CAF (`2006` — CAF has operated since 1970; its IATI file simply starts later), CDB (`2013`/`2023` — its source lists only projects "Under Implementation," so completed projects are invisible inside the window too, not just outside it), BADEA (`coverage_end_year: 2022`). Absent from the other nine banks, meaning "covered for the whole run."

- **`mdbs_scraper/official_sources.json`** (new 2026-09-16) registers officially-supplied files the same way `banks.json` registers scraped sources — publisher URL, `as_of` date, sha256, and a `role` (`backbone`: defines which operations exist; `supplement`: adds what the backbone lacks; `extra-fields`: fills blanks only, never adds/drops rows; `backstop`: checked against, not merged). `reconcile.py` applies the merge per role; `backstop.py` checks every registered file's counts/fields/amounts against the final output regardless of role, writing `reports/backstop_summary.csv` (`--strict-backstop` turns a failure into exit code 3). The files themselves live in `online pulled data/` — supplied by the operator, not fetched by any adapter. That directory also held a shares/voting-power workbook not registered in `official_sources.json` and not part of this system at all (`mdb_country_shares_with_caf_cabei_loan_votes copy.xlsx`, dated 25 Aug 2026, untracked by git); it has since been copied into this repo as `data/manual/shares_snapshot_2026-08-25.xlsx` — see `docs/manual_data_checklist.md`.

- **Loaded at import time** into a frozen dataclass whose defaults document each knob. `BankDefinition(**entry)` is strict: an unknown key raises `TypeError` at import.

  ```python
  # mdbs_scraper/config.py:47
  def _load_registry(path: Path) -> tuple[dict[str, BankDefinition], dict[str, str]]:
      payload = json.loads(path.read_text(encoding="utf-8"))
      banks = {entry["id"]: BankDefinition(**entry) for entry in payload["banks"]}
      aliases = dict(payload["aliases"])
      return banks, aliases
  ```

- **Derived views:**
  - `BANKS` keeps only enabled banks.
  - `canonical_bank_id()` lowercases and applies aliases (`cabi` → `cabei`, `worldbank` → `ibrd`).
  - `get_bank()` raises with the list of valid ids.
- **`year_filter.json`** holds `{"enabled": true, "min_year": 2002, "max_year": 2026}`, loaded into `YearFilterDefault`. An explicit CLI flag wins.
- **Per-run settings** go CLI → `ScrapeOptions` dataclass → scraper. There are no env vars, no `.env` loading (though `.env` is gitignored), and no secrets.
- **Packaging:** `pyproject.toml` `[tool.setuptools.package-data]` lists only `banks.json`.

### Would do differently

- Use the same pattern here: a bank registry JSON loaded into a frozen dataclass with a strict loader, plus a `_load_*(path)` seam for tests. Suggested fields:
  - canonical eligibility code (`AfDB`, `ADF`, …)
  - `project_bank_id` (`afdb`) and `project_funding_window` (`"African Development Fund"`, or null)
  - founding year
  - member-page and annual-report URLs
- **Keep judgement facts out of JSON.** Accession dates, mandate timelines and sanctions belong in `data/manual/*.csv`, per `docs/CLAUDE.md`, with reasoning in `coding_decisions.md` rather than free-text `coverage_notes`.
- Put all JSON files in package data (`"*.json"`). The scraper's omission of `year_filter.json` breaks a non-editable install (Appendix A).
- Put the user-agent contact in config or an env var (§3). It is the one setting that should not be committed.

---

## 11. Testing approach

### Observed

- **Standard library only.** `unittest`, `unittest.mock`, `tempfile`; no pytest. Run with `python -m unittest discover -s tests -v`. All **210 tests pass offline in ~1.2 s** (checked 2026-09-17, was 127 on 2026-09-15) — the growth tracks the new modules (`official.py`, `reconcile.py`, `backstop.py`, `dyad.py`, `reference.py`, `coverage.py`, `instruments.py`).
- **Layout:** one test file per module or bank. Fixtures live in `tests/fixtures/` and are small, redacted, real-shaped captures (CSV, JSON, IATI XML, HTML, a Tableau payload). Each file locates them with `FIXTURES = Path(__file__).parent / "fixtures"`.
- **Network isolation** without extra libraries:
  - `ScrapeOptions(source_file=...)`
  - replacing `scraper.client.get` with a `Mock`
  - `patch("mdbs_scraper.adapters.common.render_page", ...)`
  - temporarily patching module constants (`eib_module._PAGE_SIZE = 2`)
- **End to end:** `test_cli.py` runs every enabled bank from fixtures into a `TemporaryDirectory` and asserts on `manifest.json` and the coverage CSV. It also tests partial failure, the exit code, and the dynamic-bank retry.
- **Tests assert on explanations, not just values**, e.g. `assertIn("blank does not mean zero", ...)`. Regression tests carry a comment citing the live evidence that motivated them.
- There is no CI, coverage configuration, or linting.

```python
# tests/test_registry_and_adapters.py:42
        scraper = AIIBScraper(get_bank("aiib"), ScrapeOptions())
        scraper.client.get = Mock(return_value=Mock(
            url=detail.url,
            text=Mock(return_value=detail.html),
        ))
        with patch("mdbs_scraper.adapters.common.render_page", return_value=listing):
            records = scraper.run()
```

```python
# tests/test_iati_geography.py:109
    def test_regional_and_institutional_text_is_never_guessed(self):
        self.assertEqual(iso3_country_code_from_name("Regional"), "")
        self.assertEqual(iso3_country_code_from_name("Africa, regional"), "")
        self.assertEqual(iso3_country_code_from_name("OECS Countries"), "")
        self.assertEqual(iso3_country_code_from_name("BADEA"), "")
```

### Would do differently

- Same framework, same fixture layout, same sentence-style names, same "assert the note too" habit.
- **Fixtures for PDFs:** commit one or two extracted pages per bank table layout, or the table extractor's JSON output, not whole annual reports. Test each per-bank parser against them.
- **Test the cache** (hit, miss, refresh, no caching of non-2xx) and **the normaliser pin** from §7.
- **The four validation checks** from `docs/CLAUDE.md` are data assertions over the built panel. Implement them as functions that `make validate` calls, and unit-test the functions themselves on tiny synthetic panels.
- `docs/CLAUDE.md` assumes `make`. Add a `Makefile` whose `test` target runs the `unittest` command above.

---

## 12. What to import, copy, or leave

**Rule of thumb:** *import* what must stay identical across the two repos, *copy* what this repo will need to change, and *leave* anything tied to `ProjectRecord`.

| Item | Location | Action | Notes |
|---|---|---|---|
| `iso3_country_code_from_name`, `alpha3_from_alpha2`, `country_name_from_code`, `IATI_COUNTRY_CODES` | `mdbs_scraper/iati_geography.py` | **Import** | Must be identical for the merge. Fix gaps upstream (§7) and wrap in `require_iso3` here |
| `normalize_text`, `ascii_fold`, `normalized_key`, `join_values`, `extract_year`, `NULL_TEXT` | `mdbs_scraper/cleaning.py` | **Import** | Pure, well-tested |
| `parse_date` | `cleaning.py` | Import, with care | Bare `"2015"` → `2015-01-01`; `FY` labels unsupported |
| `detect_currency` | `cleaning.py` | **Import** | Fixed 2026-09-16 (ISO 4217 whitelist); safe to import directly now |
| `parse_decimal`, `parse_amount` | `cleaning.py` | Import only with `period_is_decimal=True` and an explicit currency | The bare-number bug (§8) is unchanged; the 2026-09-16 fix only covers the magnitude-word case |
| `dyad_country_year.csv`, `dyad_country_year_balanced.csv`, `dyad_unallocated_year.csv` | `output/` (generated by `main.py --dyad`) | **Consume directly** | New 2026-09-16. Already uses `approval_year`, already backbone-reconciled, already coverage-window aware (the balanced file's `observed`/`in_coverage` flags). Re-deriving country/year placement independently from the 14 per-bank CSVs would only duplicate this logic and drift out of sync with it — this repo's `build_commitments.py` reads it as a thin re-projection, not a re-derivation |
| `parse_tables`, `table_to_dicts`, `extract_links`, `html_to_text`, `extract_label_values`, `extract_labelled_sequence` | `mdbs_scraper/parsers.py` | **Import** | Stdlib-only; good for member pages and Wayback snapshots |
| `decode_bytes`, `delimited_rows`, `json_rows`, `format_from_content_type`, `infer_format` | `mdbs_scraper/tabular.py` | **Import** | |
| `xlsx_rows` | `tabular.py` | **Don't use for OGHIST** | It takes the sheet with the most rows and guesses the header as the densest of the first 25 rows. OGHIST has several sheets and multi-row headers: open the named sheet with `openpyxl` and read explicit header rows |
| `HttpClient`, `HttpResponse`, retry/throttle/AIA logic | `mdbs_scraper/http.py` | **Copy**, then add cache, robots.txt, contact user agent, process-wide throttle | ~240 self-contained lines. Importing would tie this repo's exceptions to `mdbs_scraper.errors` |
| Exception hierarchy | `mdbs_scraper/errors.py` | **Copy** (rename base to fit this package) | Keep the same five-class shape |
| `utc_now`, `iso_date` | `mdbs_scraper/schema.py` | Copy (two small functions) | |
| `sha256`, manifest structure, coverage CSV, quality report | `output.py`, `cli.py:269-294`, `report.py` | **Copy the pattern** | The writers are typed to `ProjectRecord` |
| `BankDefinition` + `_load_registry` + aliases + registry fail-fast | `config.py`, `registry.py` | **Copy the pattern** | New fields (§10) |
| Playwright helpers | `mdbs_scraper/browser.py` | Leave unless forced (§4) | Per-call launch, macOS-specific path, known crash |
| `FIELD_ALIASES`, `generic_record_from_row`, `BaseScraper.finalize`, adapters, `dac_sectors.py` | `adapters/`, `base.py` | **Leave** | Project-record specific |

**How to import.** Install the scraper into this repo's venv in editable mode: `python -m pip install -e ../mdbs_scraper_corrected`. The package-data bug that used to make editable mode load-bearing (Appendix A) is fixed as of 2026-09-16 — `pyproject.toml` now ships every JSON/data file, not just `banks.json` — but editable mode is still the sensible choice for a sibling repo under active development regardless.

`import mdbs_scraper.iati_geography` runs `mdbs_scraper/__init__.py`, which loads `config` (reads the two JSON files) and `schema`. It makes no network calls and does not import adapters, the registry, or Playwright. Record the scraper's commit hash in this repo's manifest.

---

## Appendix A: defects noticed in the scraper

Originally an open list for fixing in `mdbs_scraper_corrected`. As of the 2026-09-17 pass, **every item below is resolved** — re-verified live, not just read off a commit message — mostly in `854d58e` and `d288101` (both 2026-09-16). A copy of this document in that repo (`docs/reference_conventions copy.md`) was used as the fix list. Kept here as a record, not a to-do.

1. ~~Country normaliser gaps.~~ **Resolved.** About 634 output rows had a real country but a blank `country_code` (§7); `docs/PROBLEMS.md`'s then-current "zero real countries slipped through" was itself already stale at the time. All specific cases this document named now resolve.
2. ~~CDB's own canonical member names don't resolve.~~ **Resolved.** `"The Bahamas"` and `"British Virgin Islands"` both map correctly now.
3. **Not resolved, and not expected to be from this fix round.** Three-decimal numbers are still read as thousands by `parse_decimal` for any bank without `amount_period_is_decimal`, e.g. `"2.500"` → `2500` (§8). What *was* fixed is a related but distinct bug — a number immediately before an English magnitude word (`"1.448 billion"`) — plus a per-bank override for EBRD specifically. The general bare-number case is a live hazard for annual-report tables; see §8's parsing guidance before importing this function.
4. ~~`detect_currency` treats any isolated three-letter capitalised word as a currency.~~ **Resolved.** Restricted to an ISO 4217 whitelist plus XDR/XUA; RMB now maps to CNY.
5. ~~`year_filter.json` is missing from package data.~~ **Resolved.** `package-data` now lists every JSON and data file, not just `banks.json`.
6. **User agents — resolved:**
   - The contact now comes from `MDBS_SCRAPER_CONTACT` (optional, warns once if unset, no longer a false claim).
   - All four Playwright call sites — `render_page`, both download helpers, and BADEA's — now send the same `build_user_agent()` as HTTP.
   - `download_from_last_button` now goes through the same public `launch_chromium` as everything else.
7. ~~Self-reference stripping is skipped for HTML banks.~~ **Resolved.** `HTMLPortfolioScraper.map_row` now passes `bank_abbreviation`, matching `TabularScraper.map_row`.
8. ~~The throttle is per client, not per host process-wide.~~ **Resolved.** A module-level `_HOST_LAST_REQUEST` dict behind a per-host lock now coordinates every `HttpClient` in the process.
9. ~~`CkanOrganizationScraper` reads one `package_search` page without paging.~~ **Resolved.** Now pages through CKAN's results beyond the first 100.
10. ~~`--verbose` does nothing.~~ **Resolved.** `http.py` now logs every request/retry at DEBUG.
11. **Minor — all resolved:** the unreachable `return ""` in `dac_sectors.py` is gone; the CLI failure row now includes `with_sector_category`; the README's IDB URL now matches `banks.json`'s `files/download`.

**New, unrelated to this list:** a shares/voting-power workbook (`online pulled data/mdb_country_shares_with_caf_cabei_loan_votes copy.xlsx`) was found sitting untracked in that repo — not a defect in the scraper, just something nobody had registered or moved. See §10 and `docs/manual_data_checklist.md`.
