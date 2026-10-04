"""Single seam to the project scraper's country codelists.

Everything that turns a country name or code into an ISO 3166-1 alpha-3 code
goes through this module, so that when the normaliser question is settled
(docs/architecture.md, decision 1) there is exactly one file to change. It
becomes ``src/mdb_eligibility/countries.py`` when the package proper exists.

The reference repository is imported if it is installed (``python -m pip
install -e ../mdbs_scraper_corrected``); otherwise the sibling checkout is put
on the path, so these scripts run with no setup at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

REFERENCE_REPO = Path(__file__).resolve().parents[2] / "mdbs_scraper_corrected"

# Alpha-2 codes IATI keeps for withdrawn/historical entries that share an
# alpha-3 code with a current entry. The current name wins for display.
_HISTORICAL_NAMES = {"Burma", "East Timor", "Zaire"}


def _iati_geography():
    try:
        from mdbs_scraper import iati_geography
    except ImportError:
        if not REFERENCE_REPO.is_dir():
            raise SystemExit(
                f"Cannot find the project scraper at {REFERENCE_REPO}. Either check it out "
                "there, or run: python -m pip install -e ../mdbs_scraper_corrected"
            )
        sys.path.insert(0, str(REFERENCE_REPO))
        from mdbs_scraper import iati_geography
    return iati_geography


_GEOGRAPHY = _iati_geography()

ISO3_CODES: frozenset[str] = frozenset(_GEOGRAPHY.IATI_ALPHA2_TO_ALPHA3.values())
"""Every ISO 3166-1 alpha-3 code the reference repository recognizes."""


def _build_code_to_name() -> dict[str, str]:
    names: dict[str, str] = {}
    for alpha2, alpha3 in _GEOGRAPHY.IATI_ALPHA2_TO_ALPHA3.items():
        name = _GEOGRAPHY.IATI_COUNTRY_CODES.get(alpha2, "")
        if not name:
            continue
        if alpha3 not in names or names[alpha3] in _HISTORICAL_NAMES:
            names[alpha3] = name
    return names


CODE_TO_NAME: dict[str, str] = _build_code_to_name()
"""ISO 3166-1 alpha-3 -> the codelist's own country name."""


def country_name(iso3: str) -> str:
    """Return the codelist name for an alpha-3 code, or "" if unrecognized."""
    return CODE_TO_NAME.get(iso3.strip().upper(), "")


def iso3_from_name(name: str) -> str:
    """Return an alpha-3 code for a free-text country name, or "" if unresolved."""
    return _GEOGRAPHY.iso3_country_code_from_name(name)


def alpha3_from_alpha2(alpha2: str) -> str:
    """Return an alpha-3 code for an ISO 3166-1 alpha-2 code, or "" if unrecognized."""
    return _GEOGRAPHY.alpha3_from_alpha2(alpha2)
