"""KEZI 03 KNMB — Kostennachricht Mahnbescheid inbound parser.

The Mahngericht emits a KNMB after the Mahnbescheid is accepted. It carries
the court's reported court fees (Gerichtskosten) for the Antrag, which the
Anwalt's Forderungskonto must record so that:

  * Gerichtskosten line is added to ``ClaimsAccount.expenses``
  * The bookkeeping side mirrors the actual amount the court charged, not
    the estimate computed at filing time
  * The downstream Vollstreckungsbescheid-Antrag (KEZI 08 VBA) can quote
    the recorded Mahngericht-Kostenbeleg-Nr

Field layout per the vendored ``EDA-SB_KEZI_03_4100_KNMB.pdf`` Satzbeschreibung
(Format 4.1 V 4.0). The parser is conservative: only the durable
identification fields are typed here; richer record fields land in Phase B.2
once we have a real-court fixture to pin them.

Spec 367 Phase B.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pyeda_mahn.errors import EDAInvariantError
from pyeda_mahn.format.record import EDA_TEXT_CODEC, RECORD_LENGTH

KostenStatus = Literal["festgesetzt", "ermaessigt", "unknown"]


class KostennachrichtEntry(BaseModel):
    """One parsed KNMB row.

    Attributes:
        gnr: court Geschäftsnummer of the originating Mahnantrag.
        kostenbeleg_nr: court-side fee receipt id (``Kostenbeleg-Nr``).
        gerichtskosten_eur: total Gerichtskosten in EUR (positive Decimal).
        festsetzungs_datum: date the court set the fees (``Datum6``).
        kosten_status: ``festgesetzt`` (full fees) or ``ermaessigt`` (reduced).
    """

    model_config = ConfigDict(frozen=True)

    gnr: str
    kostenbeleg_nr: str | None = None
    gerichtskosten_eur: Decimal | None = None
    festsetzungs_datum: date | None = None
    kosten_status: KostenStatus = "unknown"


class KostennachrichtParsed(BaseModel):
    model_config = ConfigDict(frozen=True)

    entries: list[KostennachrichtEntry] = Field(default_factory=list)


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


def _parse_betrag(raw: str, *, scale: int = 2) -> Decimal | None:
    """Parse an ``N(scale)`` Betrag — zero-padded cents with implicit decimal.

    Empty / non-numeric fields return ``None``.
    """
    if not raw.strip() or not raw.isdigit():
        return None
    cents = int(raw)
    return (Decimal(cents) / Decimal(10**scale)).quantize(Decimal("0.01"))


def parse_kostennachricht(payload: bytes) -> KostennachrichtParsed:
    """Parse a KEZI 03 KNMB EDA file payload.

    Minimal field layout (matches the published Satzbeschreibung row width
    and the offsets used by sibling KEZI parsers; further fields are
    accepted-but-ignored until Phase B.2):

      * Pos. 1-2  = SA = ``03``
      * Pos. 3-4  = KZ = ``KN``
      * Pos. 7-26 = GNR (20 X)
      * Pos. 27-32 = Festsetzungs-Datum JJMMTT
      * Pos. 33-42 = Kostenbeleg-Nr (10 X)
      * Pos. 43-52 = Gerichtskosten Betrag N(10) — cents
      * Pos. 53    = Status flag: ``F`` = festgesetzt, ``E`` = ermaessigt

    AA / BB header/footer rows are skipped. Unknown SA/KZ combinations are
    silently dropped so a future Format 4.x extension does not crash sync.
    """
    if len(payload) % RECORD_LENGTH != 0:
        raise EDAInvariantError(
            invariant_name="knmb_payload_length",
            detail=(
                f"KNMB payload length {len(payload)} is not a multiple of "
                f"{RECORD_LENGTH}"
            ),
        )
    entries: list[KostennachrichtEntry] = []
    for offset in range(0, len(payload), RECORD_LENGTH):
        record = payload[offset : offset + RECORD_LENGTH]
        sa = _decode(record, 0, 2)
        kz = _decode(record, 2, 2)
        if sa in ("AA", "BB"):
            continue
        if sa != "03" or kz != "KN":
            continue
        gnr = _decode(record, 6, 20)
        if not gnr:
            continue
        datum = _parse_datum6(_decode(record, 26, 6))
        kostenbeleg = _decode(record, 32, 10) or None
        betrag = _parse_betrag(_decode(record, 42, 10))
        flag = _decode(record, 52, 1).upper()
        status: KostenStatus
        if flag == "F":
            status = "festgesetzt"
        elif flag == "E":
            status = "ermaessigt"
        else:
            status = "unknown"
        entries.append(
            KostennachrichtEntry(
                gnr=gnr,
                kostenbeleg_nr=kostenbeleg,
                gerichtskosten_eur=betrag,
                festsetzungs_datum=datum,
                kosten_status=status,
            )
        )

    return KostennachrichtParsed(entries=entries)
