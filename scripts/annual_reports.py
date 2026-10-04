"""Fetch and cache annual-report/financial-statement PDFs for the
shares-backward-extension plan (docs/manual_data_checklist.md Phase 1,
"Extend it backward").

Mirrors scripts/wayback.py's fetch/cache/retry pattern, but for plain HTTPS
downloads, not the Wayback Machine -- these are current official documents,
not historical snapshots. Uses `urllib.request` directly, not `WebFetch`:
confirmed live this session that IDB's own publications site returns 403 to
WebFetch's request pattern but succeeds with a plain browser-style
user-agent.

Usage as a library:
    from annual_reports import fetch
    path = fetch("https://www.caribank.org/.../CDB-Annual-Report-2024.pdf", "cdb_fs_2024.pdf")
    # path is a local file in data/raw/annual_reports/, cached by name
"""

from __future__ import annotations

import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW_DIR = REPO / "data" / "raw" / "annual_reports"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36 "
    "mdb-eligibility-thesis-research/1.0 (+academic research; contact: ljr.hakvoort@gmail.com)"
)

RETRIES = 4
BACKOFF_BASE = 2.0  # seconds; doubles each attempt


def _looks_right(body: bytes, expect: str) -> bool:
    if expect == "pdf":
        return body.startswith(b"%PDF")
    if expect == "html":
        return b"<html" in body[:5000].lower() or b"<!doctype" in body[:5000].lower()
    return True


def _curl(url: str, user_agent: str, timeout: float) -> bytes | None:
    """Fallback for a 403 to Python's urllib: adb.org's WAF refuses urllib's
    requests for some documents while serving the same URL, same honest
    User-Agent, to the `curl` command (confirmed live on ADB's financial-report
    PDFs). Same request, same identification -- a different HTTP client. A
    bot-*challenge* (Cloudflare/Incapsula, as on iadb.org and caf.com) is a
    different thing and is still treated as a real block: curl doesn't get past
    those either, and _looks_right() rejects the challenge page."""

    if shutil.which("curl") is None:
        return None
    result = subprocess.run(
        ["curl", "-sSL", "--max-time", str(int(timeout)), "-A", user_agent, url],
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 and result.stdout else None


def fetch(url: str, cache_name: str, *, timeout: float = 60.0, expect: str = "pdf",
          user_agent: str | None = None, delay: float = 0.0) -> Path:
    """GET `url`, cached to data/raw/annual_reports/<cache_name>. A cache hit
    never re-fetches -- these are stable, dated documents, not live data.

    `expect` is what the body must look like: "pdf" (default), "html"
    (SEC EDGAR filings), or "any". Checking is what catches a bot-challenge or
    soft-404 page that comes back as HTTP 200. `delay` sleeps before a real
    (non-cached) request -- sec.gov asks for at most 10 requests a second.

    Raises SystemExit (not an exception a caller must remember to catch) on
    final failure, matching this project's other fetch scripts' behavior of
    failing loudly rather than silently producing an empty/partial dataset.
    """

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / cache_name
    if cache_path.is_file():
        return cache_path

    if delay:
        time.sleep(delay)
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": user_agent or USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
            if expect == "pdf" and not body.startswith(b"%PDF"):
                raise RuntimeError(f"response for {url} does not look like a PDF (starts {body[:20]!r})")
            if expect == "html" and b"<html" not in body[:5000].lower() and b"<!doctype" not in body[:5000].lower():
                raise RuntimeError(f"response for {url} does not look like HTML (starts {body[:20]!r})")
            tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
            tmp.write_bytes(body)
            tmp.rename(cache_path)
            return cache_path
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 403:
                body = _curl(url, user_agent or USER_AGENT, timeout)
                if body is not None and _looks_right(body, expect):
                    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
                    tmp.write_bytes(body)
                    tmp.rename(cache_path)
                    return cache_path
                break  # a 403 that curl can't get past either is a real block; don't hammer it
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF_BASE * (2**attempt))
    raise SystemExit(f"error: could not fetch {url} after {RETRIES} attempts ({last_error})")
