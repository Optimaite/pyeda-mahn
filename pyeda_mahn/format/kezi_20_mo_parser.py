"""KEZI 20 MO — Monierungsnachricht inbound parser.

The Mahngericht emits a Monierung when the Antrag is technically defective
but fixable: missing/inconsistent fields, ambiguous Antragsgegner, defective
Zinsangaben, missing Vollmachts-Vermerk, etc.

In Optimaite this surfaces as an operator-actionable task: the original
KEZI 01 MBA stays on disk, the operator inspects the Monierungs-Grund
codes/freetext, edits the source draft, and re-files via the corresponding
KEZI 20 MOA (Monierungsantwort) outbound encoder. Until the encoder ships
in Phase B.2, the Monierung surfaces as a typed ``AgentSuggestion``.

Field layout per the vendored ``EDA-SB_KEZI_20_4000_MO.pdf`` Satzbeschreibung
(Format 4.0).

Spec 367 Phase B.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pyeda_mahn.errors import EDAInvariantError
from pyeda_mahn.format.record import EDA_TEXT_CODEC, RECORD_LENGTH

MonierungsSchwere = Literal["fix_required", "warning", "unknown"]


class MonierungsEntry(BaseModel):
    """One parsed Monierung row.

    Attributes:
        gnr: court Geschäftsnummer of the originating Mahnantrag.
        monierungs_datum: date the court raised the Monierung.
        grund_code: structured Monierungs-Grund code (mahngerichte.de codelist).
            Empty when the Mahngericht emitted only freetext.
        grund_freitext: Mahngericht's human-readable description.
        antwort_frist_tage: number of days the Anwalt has to respond before
            the Antrag is rejected. ``None`` if not transmitted.
        schwere: ``fix_required`` (mandatory correction) vs ``warning``
            (informational; Antrag still proceeds).
    """

    model_config = ConfigDict(frozen=True)

    gnr: str
    monierungs_datum: date | None = None
    grund_code: str | None = None
    grund_freitext: str | None = None
    antwort_frist_tage: int | None = None
    schwere: MonierungsSchwere = "unknown"


class MonierungParsed(BaseModel):
    model_config = ConfigDict(frozen=True)

    entries: list[MonierungsEntry] = Field(default_factory=list)


def _decode(record: bytes, start: int, length: int) -> str:
    return record[start : start + length].decode(EDA_TEXT_CODEC, errors="replace").rstrip()


def _parse_datum6(raw: str) -> date | None:
    if not raw.strip() or len(raw) < 6 or not raw.isdigit():
        return None
    yy = int(raw[0:2])
    mm = int(raw[2:4])
    dd = int(raw[4:6])
    yyyy = 2000 + yy if yy < 80 else 1900 + yy
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def _parse_int(raw: str) -> int | None:
    s = raw.strip()
    if not s or not s.isdigit():
        return None
    return int(s)


def parse_monierung(payload: bytes) -> MonierungParsed:
    """Parse a KEZI 20 MO EDA file payload.

    Minimal field layout (matches the published Satzbeschreibung row width;
    code-list expansion to the full Monierungs-Grund taxonomy lands in
    Phase B.2 when the corresponding outbound MOA encoder ships):

      * Pos. 1-2  = SA = ``20``
      * Pos. 3-4  = KZ = ``MO``
      * Pos. 7-26 = GNR (20 X)
      * Pos. 27-32 = Monierungs-Datum JJMMTT
      * Pos. 33-36 = Grund-Code (4 X) — codelist
      * Pos. 37    = Schwere-Flag: ``F`` = fix-required, ``W`` = warning
      * Pos. 38-40 = Antwort-Frist-Tage (3 N)
      * Pos. 41-122 = Grund-Freitext (82 X)
    """
    if len(payload) % RECORD_LENGTH != 0:
        raise EDAInvariantError(
            invariant_name="mo_payload_length",
            detail=(
                f"MO payload length {len(payload)} is not a multiple of "
                f"{RECORD_LENGTH}"
            ),
        )
    entries: list[MonierungsEntry] = []
    for offset in range(0, len(payload), RECORD_LENGTH):
        record = payload[offset : offset + RECORD_LENGTH]
        sa = _decode(record, 0, 2)
        kz = _decode(record, 2, 2)
        if sa in ("AA", "BB"):
            continue
        if sa != "20" or kz != "MO":
            continue
        gnr = _decode(record, 6, 20)
        if not gnr:
            continue
        datum = _parse_datum6(_decode(record, 26, 6))
        grund_code = _decode(record, 32, 4) or None
        flag = _decode(record, 36, 1).upper()
        schwere: MonierungsSchwere
        if flag == "F":
            schwere = "fix_required"
        elif flag == "W":
            schwere = "warning"
        else:
            schwere = "unknown"
        frist_tage = _parse_int(_decode(record, 37, 3))
        freitext = _decode(record, 40, 82) or None
        entries.append(
            MonierungsEntry(
                gnr=gnr,
                monierungs_datum=datum,
                grund_code=grund_code,
                grund_freitext=freitext,
                antwort_frist_tage=frist_tage,
                schwere=schwere,
            )
        )

    return MonierungParsed(entries=entries)
