"""KEZI 05 ZNMBVB — Zustellungs-/Nichtzustellungsnachricht MB/VB inbound parser.

The Mahngericht emits a ZNMBVB on every Mahnbescheid / Vollstreckungs-
bescheid Zustellung attempt. Each row carries:

  * GNR (the court's Geschäftsnummer of the originating Antrag)
  * Zustellungs-Status (zugestellt / nicht-zustellt)
  * Zustellungs-Datum (Datum6)
  * Schuldner-Nr (when multiple Antragsgegner)
  * Nicht-Zustellungs-Grund (when not delivered)

Downstream, the bea_service consumer routes a ``zugestellt`` ZNMBVB into
:func:`record_delivery_confirmation` (which maps ``filing_type='mahnantrag'``
to a 14-day Widerspruchsfrist per ZPO § 692).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pyeda_mahn.errors import EDAInvariantError
from pyeda_mahn.format.record import EDA_TEXT_CODEC, RECORD_LENGTH

ZustellungsStatus = Literal["zugestellt", "nichtzugestellt", "unknown"]


class ZustellungsnachrichtEntry(BaseModel):
    """One parsed ZNMBVB row."""

    model_config = ConfigDict(frozen=True)

    gnr: str
    zustellungsstatus: ZustellungsStatus = "unknown"
    zustellungs_datum: date | None = None
    schuldner_nr: str | None = None
    nichtzustellungs_grund: str | None = None


class ZustellungsnachrichtParsed(BaseModel):
    model_config = ConfigDict(frozen=True)

    entries: list[ZustellungsnachrichtEntry] = Field(default_factory=list)


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


def parse_zustellungsnachricht(payload: bytes) -> ZustellungsnachrichtParsed:
    """Parse a KEZI 05 ZNMBVB EDA file payload.

    Minimal field layout (matches the published Satzbeschreibung row width
    and order; full validation is Phase B):

      * Pos. 1-2  = SA = ``05``
      * Pos. 3-4  = KZ = ``ZN``
      * Pos. 7-26 = GNR (20 X)
      * Pos. 27-32 = Zustellungs-Datum JJMMTT
      * Pos. 33   = Status flag: ``Z`` = zugestellt, ``N`` = nicht-zugestellt
      * Pos. 34-43 = Schuldner-Nr (10 X)
      * Pos. 44-125 = Nichtzustellungs-Grund (Freitext) when N
    """
    if len(payload) % RECORD_LENGTH != 0:
        raise EDAInvariantError(
            invariant_name="znmbvb_payload_length",
            detail=(
                f"ZNMBVB payload length {len(payload)} is not a multiple of "
                f"{RECORD_LENGTH}"
            ),
        )
    entries: list[ZustellungsnachrichtEntry] = []
    for offset in range(0, len(payload), RECORD_LENGTH):
        record = payload[offset : offset + RECORD_LENGTH]
        sa = _decode(record, 0, 2)
        kz = _decode(record, 2, 2)
        if sa in ("AA", "BB"):
            continue
        if sa != "05" or kz != "ZN":
            continue
        gnr = _decode(record, 6, 20)
        if not gnr:
            continue
        datum = _parse_datum6(_decode(record, 26, 6))
        flag = _decode(record, 32, 1).upper()
        status: ZustellungsStatus
        if flag == "Z":
            status = "zugestellt"
        elif flag == "N":
            status = "nichtzugestellt"
        else:
            status = "unknown"
        schuldner_nr = _decode(record, 33, 10) or None
        grund = None
        if status == "nichtzugestellt":
            grund = _decode(record, 43, 82) or None
        entries.append(
            ZustellungsnachrichtEntry(
                gnr=gnr,
                zustellungsstatus=status,
                zustellungs_datum=datum,
                schuldner_nr=schuldner_nr,
                nichtzustellungs_grund=grund,
            )
        )

    return ZustellungsnachrichtParsed(entries=entries)
