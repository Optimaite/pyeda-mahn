"""KEZI 16 ABN — Abgabenachricht inbound parser.

The Mahngericht emits an Abgabenachricht when the Verfahren leaves the
automated Mahnverfahren and is handed to the Prozessgericht for the streitige
Verfahren (after a Widerspruch/Einspruch, on the Antragsteller's request). It
names the Prozessgericht and the date of Abgabe so the case can transition.

Byte-precise field layout per the vendored ``EDA-SB_KEZI_16_4000_ABN.pdf``
(Format 4 V 4.0.00) — N01 Kennsatz (``SA=16``, ``KENNZ=KS``). The follow-on
party/PV records (N02-N06) are accepted-but-ignored; the Kennsatz carries the
durable transition fields.

Spec 367 Phase C.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from pyeda_mahn.errors import EDAInvariantError
from pyeda_mahn.format.notice_parsing import decode_field, parse_datum6
from pyeda_mahn.format.record import RECORD_LENGTH

# Prozessgerichtsart codes (Feld PGM) per the Satzbeschreibung.
_PGM_LABELS: dict[str, str] = {
    "1": "Amtsgericht (Zivilabteilung)",
    "2": "Landgericht - Zivilkammer",
    "3": "Landgericht - Kammer für Handelssachen",
    "6": "Amtsgericht - Familiengericht",
    "8": "Sozialgericht",
}


class AbgabenachrichtEntry(BaseModel):
    """One parsed ABN notice.

    Attributes:
        gnr: 11-digit court Geschäftsnummer of the originating Mahnverfahren.
        tgz: Teilnehmergeschäftszeichen (the inbound-join key to our filing).
        abgabe_datum: date the case was handed off (``ABD``).
        prozessgericht_art: human label for the Prozessgerichtsart (``PGM``).
        prozessgericht_plz: PLZ of the Prozessgericht (``PGPLZ``).
        prozessgericht_ort: seat of the Prozessgericht (``PGO``).
    """

    model_config = ConfigDict(frozen=True)

    gnr: str
    tgz: str | None = None
    abgabe_datum: date | None = None
    prozessgericht_art: str | None = None
    prozessgericht_plz: str | None = None
    prozessgericht_ort: str | None = None


class AbgabenachrichtParsed(BaseModel):
    """All ABN notices parsed from one inbound EDA file."""

    model_config = ConfigDict(frozen=True)

    entries: list[AbgabenachrichtEntry] = Field(default_factory=list)


def parse_abgabenachricht(payload: bytes) -> AbgabenachrichtParsed:
    """Parse a KEZI 16 ABN EDA file payload.

    N01 Kennsatz (``SA=16``, ``KENNZ=KS``): GNR 11N @17, AS/AGGZ 35X @28,
    ABD 6X @63, PGM 1X @78, PGPLZ 5X @79, PGO 30X @84. AA/BB and the N02-N06
    follow-on party records are skipped.
    """
    if len(payload) % RECORD_LENGTH != 0:
        raise EDAInvariantError(
            invariant_name="abn_payload_length",
            detail=f"ABN payload length {len(payload)} is not a multiple of {RECORD_LENGTH}",
        )

    entries: list[AbgabenachrichtEntry] = []
    for offset in range(0, len(payload), RECORD_LENGTH):
        record = payload[offset : offset + RECORD_LENGTH]
        sa = decode_field(record, 0, 2)
        if sa in ("AA", "BB"):
            continue
        if sa != "16" or decode_field(record, 2, 5) != "KS":
            continue
        gnr = decode_field(record, 17, 11)
        if not gnr:
            continue
        pgm = decode_field(record, 78, 1)
        entries.append(
            AbgabenachrichtEntry(
                gnr=gnr,
                tgz=decode_field(record, 28, 35) or None,
                abgabe_datum=parse_datum6(decode_field(record, 63, 6)),
                prozessgericht_art=_PGM_LABELS.get(pgm),
                prozessgericht_plz=decode_field(record, 79, 5) or None,
                prozessgericht_ort=decode_field(record, 84, 30) or None,
            )
        )

    return AbgabenachrichtParsed(entries=entries)
