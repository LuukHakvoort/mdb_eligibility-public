"""Component E: was country j barred from new commitments by bank i in year t?

Source: data/manual/bar_events.csv. A row with a `start_date` is a real,
dated event; a row with no date at all is a structured placeholder (a
country/bank pair known to need a non-accrual check, per the collection plan
section 6) with nothing to compute from yet -- it contributes None (unknown),
not False, for every year, rather than being silently skipped.

**Whole-year rule** (docs/architecture.md section 3, "Spells covering part of
a year": "E counts only if in force for the whole year", logged as decision 5
in docs/coding_decisions.md): a dated event only marks a year barred if the
event's known range covers that entire calendar year. `start_date`/`end_date`
are read at year granularity (`_year_of`), and a month like "2022-03" tells us
only that the bar started *sometime* in 2022, not that it covered the whole
year -- so the start year (and, symmetrically, the end year) is never counted
as barred by that row, only the full years strictly between them. This is
deliberately conservative: getting it backwards -- treating any overlap as a
whole year barred -- would wrongly zero out months of genuinely eligible
lending in a sample-restriction variable (confirmed against EBRD/Russia:
lending continued into early 2022 before the March suspension).

A bank/country pair with no row in the file at all is None: absence from this
file means "no bar has been logged," which is different from "confirmed not
barred" until the annual-report non-accrual pass (Phase 4 of
docs/manual_data_checklist.md) actually checks.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _panel import MANUAL_DIR, read_csv  # noqa: E402

BAR_EVENTS_CSV = MANUAL_DIR / "bar_events.csv"


def _year_of(date_text: str) -> int | None:
    return int(date_text[:4]) if date_text[:4].isdigit() else None


def load_bar_events() -> dict[tuple[str, str], list[dict]]:
    events: dict[tuple[str, str], list[dict]] = {}
    for row in read_csv(BAR_EVENTS_CSV):
        key = (row["bank"], row["iso3"])
        events.setdefault(key, []).append(row)
    return events


def is_barred(bank: str, iso3: str, year: int, events: dict[tuple[str, str], list[dict]] | None = None) -> bool | None:
    rows = (events if events is not None else load_bar_events()).get((bank, iso3))
    if not rows:
        return None

    saw_dated_event = False
    for row in rows:
        start_year = _year_of(row.get("start_date", ""))
        if start_year is None:
            continue  # undated placeholder; contributes nothing on its own
        saw_dated_event = True
        if year <= start_year:
            continue  # the start year itself may only be partially barred
        end_year = _year_of(row.get("end_date", ""))
        if end_year is not None and year >= end_year:
            continue  # the end year itself may only be partially barred
        return True
    return False if saw_dated_event else None
