"""KEZI 90 QU — Eingangsbestätigung (Quittung) inbound parser.

The Mahngericht emits a QU file for every successfully-received Antrags-
datei. Each QU file is one logical file of 128-byte records:

  * one AA-Satz
  * one or more QU records carrying GNR + Eingangsdatum + Mahngericht
  * one BB-Satz

This parser extracts the QU rows as a typed Pydantic model so callers can
correlate them with the originating ``BeaMessage`` + ``CourtFiling``.

The full QU SA layout lives in
``refs/Satzbeschreibungen-full-bundle.zip`` (not extracted here); the
fields below are the minimum subset Phase A consumes.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from pyeda_mahn.errors import EDAInvariantError
from pyeda_mahn.format.record import EDA_TEXT_CODEC, RECORD_LENGTH


class EingangsbestaetigungEntry(BaseModel):
    """One parsed QU row (one GNR per row)."""

    model_config = ConfigDict(frozen=True)

    gnr: str = Field(..., description="Court Geschäftsnummer")
    eingangs_datum: date | None = Field(default=None)
    mahngericht_safe_id: str | None = Field(default=None)


class EingangsbestaetigungParsed(BaseModel):
    """Parsed contents of one KEZI 90 QU file."""

    model_config = ConfigDict(frozen=True)

    entries: list[EingangsbestaetigungEntry] = Field(default_factory=list)


def _split_records(payload: bytes) -> Iterable[bytes]:
    """Split an EDA byte stream into its 128-byte records."""
    if len(payload) % RECORD_LENGTH != 0:
        raise EDAInvariantError(
            invariant_name="qu_payload_length",
            detail=(
                f"QU payload length {len(payload)} is not a multiple of "
                f"{RECORD_LENGTH}"
            ),
        )
    for offset in range(0, len(payload), RECORD_LENGTH):
        yield payload[offset : offset + RECORD_LENGTH]


def _decode_field(record: bytes, start: int, length: int) -> str:
    """Decode bytes[start:start+length] using the EDA text codec."""
    raw = record[start : start + length]
    return raw.decode(EDA_TEXT_CODEC, errors="replace").rstrip()


def _parse_datum6(raw: str) -> date | None:
    if not raw.strip() or len(raw) < 6 or not raw.isdigit():
        return None
    yy = int(raw[0:2])
    mm = int(raw[2:4])
    dd = int(raw[4:6])
    # Y2K window 00-79 → 21xx (matches encoder); 80-99 → 19xx.
    yyyy = 2000 + yy if yy < 80 else 1900 + yy
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def parse_eingangsbestaetigung(payload: bytes) -> EingangsbestaetigungParsed:
    """Parse a KEZI 90 QU EDA file payload.

    The published QU Satzbeschreibung gives each QU row this minimal field
    set we care about in Phase A:

      * Pos. 1-2 = SA = ``90``
      * Pos. 3-4 = KZ = ``QU``
      * Pos. 7-26 = GNR (20 X)
      * Pos. 27-32 = Eingangs-Datum JJMMTT
      * Pos. 33-50 = Mahngericht SAFE-ID (free-text)

    Anything that isn't a QU body row (AA / BB) is skipped.
    """
    entries: list[EingangsbestaetigungEntry] = []

    for record in _split_records(payload):
        sa = _decode_field(record, 0, 2)
        kz = _decode_field(record, 2, 2)
        if sa == "AA" or sa == "BB":
            continue
        if sa != "90" or kz != "QU":
            continue
        gnr = _decode_field(record, 6, 20)
        datum = _parse_datum6(_decode_field(record, 26, 6))
        mahngericht_safe_id = _decode_field(record, 32, 18) or None
        if not gnr:
            continue
        entries.append(
            EingangsbestaetigungEntry(
                gnr=gnr,
                eingangs_datum=datum,
                mahngericht_safe_id=mahngericht_safe_id,
            )
        )

    return EingangsbestaetigungParsed(entries=entries)
