"""KEZI 22 KNVB — Kosten-/Erlassnachricht Vollstreckungsbescheid inbound parser.

The Mahngericht emits a KNVB after a Vollstreckungsbescheid is issued (the VB
analog of the KEZI 03 KNMB). It reports the court fees + RVG for the VB stage,
which the Forderungskonto records.

Byte-precise field layout per the vendored ``EDA-SB_KEZI_22_4000_KNVB.pdf``
(Format 4 V 4.0.00). Each notice is two records: the L01 Kennsatz (``KENNZ=KS``)
carrying GNR + Teilnehmergeschäftszeichen + Erlass-Datum, and the L02
Gebühren/Auslagen record (``KENNZ=AUSGB``) carrying the amounts. Records are
paired by their order within the file (L01 then its L02).

Spec 367 Phase C.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from pyeda_mahn.errors import EDAInvariantError
from pyeda_mahn.format.notice_parsing import decode_field, parse_betrag, parse_datum6
from pyeda_mahn.format.record import RECORD_LENGTH


class KostennachrichtVbEntry(BaseModel):
    """One parsed KNVB notice (Kennsatz + Gebühren merged).

    Attributes:
        gnr: 11-digit court Geschäftsnummer.
        tgz: Teilnehmergeschäftszeichen (the inbound-join key to our filing).
        erlass_datum: date the VB was issued (``ELD``).
        gerichtsgebuehr_eur: Gerichtsgebühr nach GKG (``GERGEB``).
        rvg_gebuehr_eur: RA-Gebühr für den VB-Antrag VV3308 RVG (``RAGEB``).
        auslagen_eur: Auslagen des Antragstellers (``ASAUSL``).
        nebenforderungen_eur: Betrag Nebenforderungen (``NEBF``).
    """

    model_config = ConfigDict(frozen=True)

    gnr: str
    tgz: str | None = None
    erlass_datum: date | None = None
    gerichtsgebuehr_eur: Decimal | None = None
    rvg_gebuehr_eur: Decimal | None = None
    auslagen_eur: Decimal | None = None
    nebenforderungen_eur: Decimal | None = None


class KostennachrichtVbParsed(BaseModel):
    """All KNVB notices parsed from one inbound EDA file."""

    model_config = ConfigDict(frozen=True)

    entries: list[KostennachrichtVbEntry] = Field(default_factory=list)


def parse_kostennachricht_vb(payload: bytes) -> KostennachrichtVbParsed:
    """Parse a KEZI 22 KNVB EDA file payload.

    L01 Kennsatz (``SA=22``, ``KENNZ=KS``): GNR1 11N @17, ASGZ 35X @72,
    ELD 6N @107. L02 Gebühren (``SA=22``, ``KENNZ=AUSGB``): ASAUSL 8N(2) @9,
    GERGEB 7N(2) @17, RAGEB 9N(2) @28, NEBF 10N(2) @62. AA/BB are skipped.
    """
    if len(payload) % RECORD_LENGTH != 0:
        raise EDAInvariantError(
            invariant_name="knvb_payload_length",
            detail=f"KNVB payload length {len(payload)} is not a multiple of {RECORD_LENGTH}",
        )

    entries: list[KostennachrichtVbEntry] = []
    pending: dict | None = None
    for offset in range(0, len(payload), RECORD_LENGTH):
        record = payload[offset : offset + RECORD_LENGTH]
        sa = decode_field(record, 0, 2)
        if sa in ("AA", "BB"):
            continue
        if sa != "22":
            continue
        kennz = decode_field(record, 2, 5)
        if kennz == "KS":
            # Flush a Kennsatz that never got its Gebühren record.
            if pending is not None:
                entries.append(KostennachrichtVbEntry(**pending))
            gnr = decode_field(record, 17, 11)
            if not gnr:
                pending = None
                continue
            pending = {
                "gnr": gnr,
                "tgz": decode_field(record, 72, 35) or None,
                "erlass_datum": parse_datum6(decode_field(record, 107, 6)),
            }
        elif kennz == "AUSGB" and pending is not None:
            pending["auslagen_eur"] = parse_betrag(decode_field(record, 9, 8))
            pending["gerichtsgebuehr_eur"] = parse_betrag(decode_field(record, 17, 7))
            pending["rvg_gebuehr_eur"] = parse_betrag(decode_field(record, 28, 9))
            pending["nebenforderungen_eur"] = parse_betrag(decode_field(record, 62, 10))
            entries.append(KostennachrichtVbEntry(**pending))
            pending = None

    if pending is not None:
        entries.append(KostennachrichtVbEntry(**pending))

    return KostennachrichtVbParsed(entries=entries)
