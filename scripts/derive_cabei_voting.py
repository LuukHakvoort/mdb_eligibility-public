"""Fill CABEI's voting_power_pct = capital_share_pct in data/extracted/
shares_cabei_ar.csv and shares_cabei.csv, sourced to CABEI's own Constitutive
Agreement (Convenio Constitutivo), Article 4(b): "La participacion de los
Estados miembros en el capital del Banco estara representada por acciones
expedidas a favor de los respectivos Estados. Cada accion suscrita conferira
un voto" -- each subscribed share confers one vote. Fetched and read directly
this session (http://www.ordenjuridico.gob.mx/TratInt/2022ml/BCIE.pdf, a
mirror of the agreement -- bcie.org's own copy was unreachable, "Sitio en
Mantenimiento" at fetch time).

**Why this had been left blank until now**: `annual_reports_cabei_ar.py` and
`annual_reports_cabei.py` both extract `capital_share_pct` from each
document's own "acciones suscritas" (subscribed shares) column but leave
`voting_power_pct` blank, because CABEI's *current* investor presentation
(the 2024 snapshot in `shares_cabei.csv`) carries its own footnote saying its
reported shareholding percentage is conditional on a capital-payment vesting
condition -- i.e., some *newly subscribed* shares (typically from a capital
increase) may not yet confer a vote until paid in, per Resolution AG-1/98
("Special contributions do not grant voting rights [until paid]"). That
caveat is real, but it describes an exception for specific increments of
capital, not CABEI's general rule -- the Constitutive Agreement's own
Article 4(b) is unconditional for ordinarily subscribed shares. Since
`shares_cabei_ar.csv`'s own capital_share_pct is already computed from
"acciones suscritas" (the general-rule quantity, not a payment-vested
figure), applying the general one-share-one-vote rule there is a direct,
sourced application of CABEI's own charter, not a guess.

`shares_cabei.csv`'s single 2024 row keeps the caveat about that specific
document's own footnote in its note, since that source explicitly flagged
its own percentage as vesting-conditional -- this fill is still applied
(better than leaving it blank), but the note says so plainly rather than
silently dropping the caveat.

Usage:  python3 scripts/derive_cabei_voting.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, REPO, read_csv, write_csv  # noqa: E402

SOURCE_NOTE = (
    "voting_power_pct derived from capital_share_pct: CABEI's Convenio Constitutivo, "
    "Article 4(b) (\"cada accion suscrita conferira un voto\" -- each subscribed share "
    "confers one vote), http://www.ordenjuridico.gob.mx/TratInt/2022ml/BCIE.pdf, read "
    "directly 2026-09-27. See scripts/derive_cabei_voting.py for why this wasn't applied earlier."
)
_2024_CAVEAT = (
    " This document's own reported percentage is flagged as conditional on a capital-payment "
    "vesting footnote (Resolution AG-1/98: new capital-increase shares don't vote until paid); "
    "applied here as the closest sourced approximation, not a confirmed post-vesting figure."
)

TARGETS = [
    (EXTRACTED_DIR / "shares_cabei_ar.csv", False),
    (EXTRACTED_DIR / "shares_cabei.csv", True),
]


def main() -> int:
    total = 0
    for path, is_current_snapshot in TARGETS:
        if not path.is_file():
            print(f"skip: {path} does not exist")
            continue
        rows = read_csv(path)
        fieldnames = list(rows[0].keys()) if rows else ["bank", "iso3", "year", "capital_share_pct", "voting_power_pct", "source_url", "note"]
        changed = 0
        for row in rows:
            if row.get("bank") != "CABEI":
                continue
            if row.get("voting_power_pct"):
                continue  # already filled -- don't overwrite a real extracted value
            capital = row.get("capital_share_pct", "")
            if not capital:
                continue
            row["voting_power_pct"] = capital
            note = SOURCE_NOTE + (_2024_CAVEAT if is_current_snapshot else "")
            row["note"] = (row.get("note", "") + " " if row.get("note") else "") + note
            changed += 1
        write_csv(path, fieldnames, rows)
        print(f"{changed} rows -> {path.relative_to(REPO)}")
        total += changed
    print(f"\n{total} CABEI voting_power_pct rows filled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
