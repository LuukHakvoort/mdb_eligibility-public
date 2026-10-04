"""Wayback Machine access: CDX snapshot discovery and cached snapshot fetch.

Built defensively because the Internet Archive is, as of this writing, mid-
recovery from a DDoS attack: the CDX search API (`/cdx/search/cdx`) has been
observed returning a "Temporarily Offline" 503 on most attempts, while direct
snapshot fetches and the main site succeed. This is external and not
something a retry count fixes reliably -- so every successful fetch is cached
to `data/raw/` immediately (before the caller does anything else with it), and
a bank/year this can't resolve today is reported as a clean gap, never a
crash, so a partial run's progress is never lost and a later re-run doesn't
re-hit a struggling service for data already in hand.

Usage as a library:
    from wayback import nearest_snapshot, YEARS
    snap = nearest_snapshot("https://www.ebrd.com/...", 2015)
    if snap:
        html = fetch_snapshot(snap)
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW_DIR = REPO / "data" / "raw" / "wayback"
CDX_URL = "https://web.archive.org/cdx/search/cdx"
USER_AGENT = "mdb-eligibility-thesis-research/1.0 (+academic research; contact: ljr.hakvoort@gmail.com)"

RETRIES = 4
BACKOFF_BASE = 2.0  # seconds; doubles each attempt


@dataclass(slots=True)
class Snapshot:
    timestamp: str  # YYYYMMDDhhmmss
    original_url: str
    status: str

    @property
    def year(self) -> int:
        return int(self.timestamp[:4])

    @property
    def archive_url(self) -> str:
        # The "id_" modifier returns the exact original bytes with no Wayback
        # toolbar/banner injected -- without it, a non-HTML capture (JSON, a
        # PDF) comes back wrapped in Wayback's HTML player instead of the raw
        # content, and even an HTML capture carries injected markup ahead of
        # the real page.
        return f"https://web.archive.org/web/{self.timestamp}id_/{self.original_url}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cache_path(url: str) -> Path:
    return RAW_DIR / f"{_sha256(url.encode())}.cache"


def _get(url: str, timeout: float = 30.0) -> bytes | None:
    """GET with retry/backoff. Returns None (not an exception) on final failure --
    callers decide whether that's a fatal gap or something to report and skip."""

    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                # The Internet Archive serves a 200-status HTML "Temporarily
                # Offline" page during an outage rather than a clean error
                # code -- detected here so it isn't cached as if it were real
                # content.
                if b"Internet Archive: Temporarily Offline" in body[:4000]:
                    raise RuntimeError("Internet Archive reports itself temporarily offline")
                return body
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF_BASE * (2**attempt))
    print(f"wayback: giving up on {url} after {RETRIES} attempts ({last_error})")
    return None


def cdx_snapshots(url: str, *, collapse_to_year: bool = True) -> list[Snapshot]:
    """Every capture of `url` the CDX API knows about, oldest first.

    Returns an empty list (not an exception) if the CDX API can't be reached --
    callers should treat that as "unknown right now", not "no snapshots exist".
    """

    params = f"url={urllib.parse.quote(url, safe='')}&output=json&filter=statuscode:200"
    if collapse_to_year:
        params += "&collapse=timestamp:4"
    body = _get(f"{CDX_URL}?{params}")
    if body is None:
        return []
    try:
        rows = json.loads(body)
    except json.JSONDecodeError:
        return []
    if len(rows) < 2:
        return []
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    return [
        Snapshot(timestamp=row[idx["timestamp"]], original_url=url, status=row[idx["statuscode"]])
        for row in rows[1:]
    ]


def nearest_snapshot(url: str, year: int, snapshots: list[Snapshot] | None = None) -> Snapshot | None:
    """The capture closest to 31 December of `year`, from an already-fetched list."""

    candidates = snapshots if snapshots is not None else cdx_snapshots(url)
    if not candidates:
        return None
    target = f"{year}1231235959"
    return min(candidates, key=lambda snap: abs(int(snap.timestamp) - int(target)))


def fetch_snapshot(snapshot: Snapshot) -> str | None:
    """The archived page's HTML, cached to data/raw/wayback/ on first fetch."""

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_path(snapshot.archive_url)
    if cache_path.is_file():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    body = _get(snapshot.archive_url)
    if body is None:
        return None
    text = body.decode("utf-8", errors="replace")
    # Write-then-rename so an interrupted fetch never leaves a truncated file
    # that a later run treats as a valid cache hit.
    tmp = cache_path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.rename(cache_path)
    return text
