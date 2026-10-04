"""Component A: was the bank operational in year t?

Depends only on (bank, year), not on the country -- every bank's row applies
uniformly across every country in the grid for that bank/year.

Source: data/manual/bank_existence.csv (drafted with citations; not
per-country judgement, just each bank's own founding record).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _panel import MANUAL_DIR, read_csv  # noqa: E402

EXISTENCE_CSV = MANUAL_DIR / "bank_existence.csv"


def load_existence() -> dict[str, tuple[int, int | None]]:
    """{bank: (start_year, end_year_or_None)}."""

    windows: dict[str, tuple[int, int | None]] = {}
    for row in read_csv(EXISTENCE_CSV):
        bank = row["bank"]
        start = row["start_year"]
        end = row["end_year"]
        if not start.isdigit():
            continue
        windows[bank] = (int(start), int(end) if end.isdigit() else None)
    return windows


def bank_exists(bank: str, year: int, windows: dict[str, tuple[int, int | None]] | None = None) -> bool | None:
    """True/False if bank_existence.csv covers this bank; None if the bank
    isn't in the file at all (never guessed)."""

    windows = windows if windows is not None else load_existence()
    if bank not in windows:
        return None
    start, end = windows[bank]
    if year < start:
        return False
    if end is not None and year > end:
        return False
    return True
