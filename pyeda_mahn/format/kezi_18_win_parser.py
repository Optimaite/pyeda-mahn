"""KEZI 18 WIN — Widerspruchsnachricht inbound parser.

The Mahngericht emits a WIN when the Antragsgegner (debtor) files a
Widerspruch against the Mahnbescheid. WIN is the most consequential inbound
message: it kicks the matter into ``streitiges Verfahren``, which means

  * The MBA branch ends; the Anwalt has to either (a) abandon, (b) file an
    Abgabeantrag (KEZI 16 path) to transition to a regular Klageverfahren,
    or (c) wait out the Widerspruchsfrist for a Teilwiderspruch's residual
    Hauptforderung.
  * A Vollwiderspruch (full objection) blocks the Vollstreckungsbescheid
    entirely; a Teilwiderspruch (partial objection) leaves the residual
    Hauptforderung VB-eligible.

Field layout per the vendored ``EDA-SB_KEZI_18_4100_WIN.pdf`` Satzbeschreibung
(Format 4.1 V 4.0).

Spec 367 Phase B.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pyeda_mahn.errors import EDAInvariantError
from pyeda_mahn.format.record import EDA_TEXT_CODEC, RECORD_LENGTH

WiderspruchsArt = Literal["voll", "teil", "unknown"]


class WiderspruchsEntry(BaseModel):
    """One parsed WIN row.

    Attributes:
        gnr: court Geschäftsnummer of the originating Mahnantrag.
        widerspruchs_datum: date the Widerspruch was filed (``Datum6``).
        widerspruchs_art: ``voll`` blocks VB entirely; ``teil`` leaves the
            uncontested residual Hauptforderung VB-eligible.
        teilforderung_widerspruch_eur: amount the debtor contests (only
            meaningful when ``widerspruchs_art == 'teil'``).
        antragsgegner_nr: when multiple Antragsgegner, identifies which one
            filed (1..n). ``None`` for single-debtor cases.
    """

    model_config = ConfigDict(frozen=True)

    gnr: str
    widerspruchs_datum: date | None = None
    widerspruchs_art: WiderspruchsArt = "unknown"
    teilforderung_widerspruch_eur: Decimal | None = None
    antragsgegner_nr: str | None = None


class WiderspruchsnachrichtParsed(BaseModel):
    model_config = ConfigDict(frozen=True)

    entries: list[WiderspruchsEntry] = Field(default_factory=list)


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


def _parse_betrag(raw: str) -> Decimal | None:
    if not raw.strip() or not raw.isdigit():
        return None
    cents = int(raw)
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))


def parse_widerspruchsnachricht(payload: bytes) -> WiderspruchsnachrichtParsed:
    """Parse a KEZI 18 WIN EDA file payload.

    Minimal field layout (durable identification + workflow-decision fields;
    further metadata records land in Phase B.2):

      * Pos. 1-2  = SA = ``18``
      * Pos. 3-4  = KZ = ``WI``
      * Pos. 7-26 = GNR (20 X)
      * Pos. 27-32 = Widerspruchs-Datum JJMMTT
      * Pos. 33    = Art-Flag: ``V`` = Voll-Widerspruch, ``T`` = Teil-Widerspruch
      * Pos. 34-43 = Antragsgegner-Nr (10 X)
      * Pos. 44-55 = Teilforderungs-Betrag N(12) cents (Teil only)
    """
    if len(payload) % RECORD_LENGTH != 0:
        raise EDAInvariantError(
            invariant_name="win_payload_length",
            detail=(
                f"WIN payload length {len(payload)} is not a multiple of "
                f"{RECORD_LENGTH}"
            ),
        )
    entries: list[WiderspruchsEntry] = []
    for offset in range(0, len(payload), RECORD_LENGTH):
        record = payload[offset : offset + RECORD_LENGTH]
        sa = _decode(record, 0, 2)
        kz = _decode(record, 2, 2)
        if sa in ("AA", "BB"):
            continue
        if sa != "18" or kz != "WI":
            continue
        gnr = _decode(record, 6, 20)
        if not gnr:
            continue
        datum = _parse_datum6(_decode(record, 26, 6))
        flag = _decode(record, 32, 1).upper()
        art: WiderspruchsArt
        if flag == "V":
            art = "voll"
        elif flag == "T":
            art = "teil"
        else:
            art = "unknown"
        antragsgegner_nr = _decode(record, 33, 10) or None
        teil_betrag = _parse_betrag(_decode(record, 43, 12)) if art == "teil" else None
        entries.append(
            WiderspruchsEntry(
                gnr=gnr,
                widerspruchs_datum=datum,
                widerspruchs_art=art,
                teilforderung_widerspruch_eur=teil_betrag,
                antragsgegner_nr=antragsgegner_nr,
            )
        )

    return WiderspruchsnachrichtParsed(entries=entries)
