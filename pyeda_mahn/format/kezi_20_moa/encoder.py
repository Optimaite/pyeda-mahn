"""KEZI 20 MOA — Monierungsantwort encoder.

Responds to a court Monierung (KEZI 20 MO): ``AA`` + one ``G01`` Kennsatz +
N ``G02`` Monierungsdaten records (one per corrected field, echoed back in the
court's order) + ``BB``.

Byte layout per the vendored ``EDA-SB_KEZI_20_4000_MOA.pdf`` (Format 4 V 4.0.00):
- G01 Kennsatz: SA(2)=``20``, KENNZ(5)=``KS``, FN(2)=``00``, TKEZI(8N),
  ASGZ(35X), GNR1..GNR5(11N each), MOD(6X JJMMTT), AND(6X JJMMTT),
  MOBELART(2X), FILLER(7).
- G02 Daten: SA(2)=``20``, KENNZ(5)=``MO``, FN(2)=``00``, FSCHL(3N),
  FELDN(20X), INDEX1(2N), INDEX2(2N), MAS(1N), MAZ(1N), MAZPOS(1N), FORM(1X),
  INHALT(35X), FILLER(53).

NOTE: court byte-verification requires a live Mahngericht Testdurchgang — the
field map follows the published Satzbeschreibung but is not yet pinned to a
real-court fixture.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pyeda_mahn.contracts import MonierungsantwortInput, MonierungsdatenAntwort
from pyeda_mahn.format.aa_satz import AAVorsatz, build_edaid, encode_aa
from pyeda_mahn.format.notice_trailer import encode_notice_bb, gnr_control_sum
from pyeda_mahn.format.record import (
    EDARecord,
    encode_blank,
    encode_datum6,
    encode_n,
    encode_x,
    encode_x_gross,
)

_MOBELART = {
    "mba": "01",
    "vba": "02",
    "vba_erneut": "03",
    "nemb": "07",
    "nemb_erneut": "08",
    "nevb": "10",
    "nevb_erneut": "11",
}


@dataclass(frozen=True)
class MoaKennsatzRecord(EDARecord):
    """G01 Monierungsantwort Kennsatz."""

    moa: MonierungsantwortInput

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        moa = self.moa
        gnrs = list(moa.gnrs) + [""] * (5 - len(moa.gnrs))
        parts: list[bytes] = [
            encode_x_gross("20", max_length=2, field_name="MOA.SA"),
            encode_x_gross("KS", max_length=5, field_name="MOA.KENNZ"),
            encode_x("00", max_length=2, field_name="MOA.FN"),
            encode_n(moa.tkezi, max_length=8, field_name="MOA.TKEZI"),
            encode_x(moa.tgz, max_length=35, field_name="MOA.ASGZ"),
        ]
        for idx, gnr in enumerate(gnrs, start=1):
            parts.append(encode_n(gnr or 0, max_length=11, field_name=f"MOA.GNR{idx}"))
        parts.append(encode_datum6(moa.antwort_datum, field_name="MOA.MOD"))
        parts.append(encode_datum6(moa.monierter_antrag_datum, field_name="MOA.AND"))
        parts.append(encode_x_gross(_MOBELART[moa.monierte_antragsart], max_length=2, field_name="MOA.MOBELART"))
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


@dataclass(frozen=True)
class MoaDatenRecord(EDARecord):
    """G02 Monierungsantwort Daten (one corrected field)."""

    daten: MonierungsdatenAntwort

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        d = self.daten
        parts: list[bytes] = [
            encode_x_gross("20", max_length=2, field_name="MOA.SA"),
            encode_x_gross("MO", max_length=5, field_name="MOA.KENNZ"),
            encode_x("00", max_length=2, field_name="MOA.FN"),
            encode_n(d.fschl, max_length=3, field_name="MOA.FSCHL"),
            encode_x(d.feldn, max_length=20, field_name="MOA.FELDN"),
            encode_n(d.index1, max_length=2, field_name="MOA.INDEX1"),
            encode_n(d.index2, max_length=2, field_name="MOA.INDEX2"),
            encode_n(d.mas, max_length=1, field_name="MOA.MAS"),
            encode_n(d.maz, max_length=1, field_name="MOA.MAZ"),
            encode_n(d.mazpos, max_length=1, field_name="MOA.MAZPOS"),
            encode_x(d.form, max_length=1, field_name="MOA.FORM"),
            encode_x(d.inhalt, max_length=35, field_name="MOA.INHALT"),
        ]
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


def encode_monierungsantwort(
    moa: MonierungsantwortInput,
    *,
    file_when: datetime | None = None,
    edaid: str | None = None,
) -> bytes:
    """Encode a KEZI 20 Monierungsantwort to its ``.eda`` byte stream."""
    when = file_when or datetime.now(UTC)
    aa = AAVorsatz(
        tkezi=moa.tkezi,
        file_date=when.date(),
        belart="20",
        edaid=edaid or build_edaid(when=when, seq=1),
    )
    body = MoaKennsatzRecord(moa=moa).to_bytes()
    body += b"".join(MoaDatenRecord(daten=d).to_bytes() for d in moa.daten)
    bb = encode_notice_bb(
        tkezi=moa.tkezi,
        antrag_count=1,
        satz_count=1 + len(moa.daten),
        sum_gnr=gnr_control_sum(moa.gnrs),
    )
    return encode_aa(aa) + body + bb
