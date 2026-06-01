"""KEZI 07 NEMB / KEZI 10 NEVB — Neuzustellungsantrag encoder (shared).

``AA`` + ``D01`` Kennsatz + optional ``D02``/``D04`` Antragsgegner re-service
block + ``BB``. The MB (KEZI 07) and VB (KEZI 10) variants share the record
layout and differ only in the AA BELART; ``belart="07"`` → NEMB, ``"10"`` →
NEVB. FORMAT is ``4100`` for both.

Byte layout per the vendored ``EDA-SB_KEZI_07_4100_NEMB.pdf`` /
``EDA-SB_KEZI_10_4100_NEVB.pdf`` (Format 4.1 V 4.0.00):
- D01 Kennsatz: SA(2), KENNZ(5)=``KS``, FN(2)=``00``, TKEZI(8N/B), GNR(11N),
  ASGZ(35X), PTBET(8N(2)/B), NMSKOBET(8N(2)/B), NMSKOBG(35X), NMAUSK(8N(2)/B),
  FILLER(6).
- D02 Antragsgegner name: SA(2), KENNZ(5)=``AG``, FN(2)=``01``, AGN1/2/3(35X), FILLER(14).
- D04 Antragsgegner address: SA(2), KENNZ(5)=``AG``, FN(2)=``03``, AGRF(35X),
  AGSH(35X), AGPLZ(5X), AGO(27X), AGAL(3X), FILLER(14).

NOTE: pending live Mahngericht Testdurchgang pinning. The gesetzlicher-Vertreter
re-service path (D08/D09) and the Prozessgericht record (D05) are not emitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from pyeda_mahn.contracts import NeuzustellungAntragsgegner, NeuzustellungInput
from pyeda_mahn.format.aa_satz import AAVorsatz, build_edaid, encode_aa
from pyeda_mahn.format.notice_trailer import encode_notice_bb, gnr_control_sum
from pyeda_mahn.format.record import (
    EDARecord,
    encode_betrag,
    encode_blank,
    encode_n,
    encode_n_b,
    encode_x,
    encode_x_gross,
)


def _betrag_or_blank(value: Decimal | None, *, field_name: str) -> bytes:
    """N(2)/B — Betrag in 8 bytes, or all-BLANK when not applicable."""
    if value is None:
        return encode_blank(max_length=8)
    return encode_betrag(value, max_length=8, field_name=field_name)


@dataclass(frozen=True)
class NeuzustellungKennsatzRecord(EDARecord):
    """D01 Neuzustellungsantrag Kennsatz."""

    nz: NeuzustellungInput
    belart: str

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        nz = self.nz
        parts: list[bytes] = [
            encode_x_gross(self.belart, max_length=2, field_name="NZ.SA"),
            encode_x_gross("KS", max_length=5, field_name="NZ.KENNZ"),
            encode_x("00", max_length=2, field_name="NZ.FN"),
            encode_n_b(nz.tkezi, max_length=8, field_name="NZ.TKEZI"),
            encode_n(nz.gnr, max_length=11, field_name="NZ.GNR"),
            encode_x(nz.tgz, max_length=35, field_name="NZ.ASGZ"),
            _betrag_or_blank(nz.porto_telefon, field_name="NZ.PTBET"),
            _betrag_or_blank(nz.sonstige_kosten, field_name="NZ.NMSKOBET"),
            encode_x(nz.sonstige_kosten_begruendung or "", max_length=35, field_name="NZ.NMSKOBG"),
            _betrag_or_blank(nz.auskunftskosten, field_name="NZ.NMAUSK"),
        ]
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


@dataclass(frozen=True)
class NeuzustellungAgNameRecord(EDARecord):
    """D02 Antragsgegner-Name."""

    ag: NeuzustellungAntragsgegner
    belart: str

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        ag = self.ag
        parts: list[bytes] = [
            encode_x_gross(self.belart, max_length=2, field_name="NZ.SA"),
            encode_x_gross("AG", max_length=5, field_name="NZ.KENNZ"),
            encode_x("01", max_length=2, field_name="NZ.FN"),
            encode_x(ag.name1, max_length=35, field_name="NZ.AGN1"),
            encode_x(ag.name2 or "", max_length=35, field_name="NZ.AGN2"),
            encode_x(ag.name3 or "", max_length=35, field_name="NZ.AGN3"),
        ]
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


@dataclass(frozen=True)
class NeuzustellungAgAddressRecord(EDARecord):
    """D04 Antragsgegner-Anschrift."""

    ag: NeuzustellungAntragsgegner
    belart: str

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        ag = self.ag
        parts: list[bytes] = [
            encode_x_gross(self.belart, max_length=2, field_name="NZ.SA"),
            encode_x_gross("AG", max_length=5, field_name="NZ.KENNZ"),
            encode_x("03", max_length=2, field_name="NZ.FN"),
            encode_x(ag.rechtsform or "", max_length=35, field_name="NZ.AGRF"),
            encode_x(ag.strasse_hausnummer, max_length=35, field_name="NZ.AGSH"),
            encode_x(ag.plz, max_length=5, field_name="NZ.AGPLZ"),
            encode_x(ag.ort, max_length=27, field_name="NZ.AGO"),
            encode_x(ag.auslandskennzeichen or "", max_length=3, field_name="NZ.AGAL"),
        ]
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


def encode_neuzustellung(
    nz: NeuzustellungInput,
    *,
    belart: str,
    file_when: datetime | None = None,
    edaid: str | None = None,
) -> bytes:
    """Encode a Neuzustellungsantrag (``belart`` ``07`` = MB, ``10`` = VB)."""
    when = file_when or datetime.now(UTC)
    aa = AAVorsatz(
        tkezi=nz.tkezi,
        file_date=when.date(),
        belart=belart,
        format_code="4100",
        edaid=edaid or build_edaid(when=when, seq=1),
    )
    body = NeuzustellungKennsatzRecord(nz=nz, belart=belart).to_bytes()
    satz_count = 1
    if nz.antragsgegner is not None:
        body += NeuzustellungAgNameRecord(ag=nz.antragsgegner, belart=belart).to_bytes()
        body += NeuzustellungAgAddressRecord(ag=nz.antragsgegner, belart=belart).to_bytes()
        satz_count += 2
    bb = encode_notice_bb(
        tkezi=nz.tkezi,
        antrag_count=1,
        satz_count=satz_count,
        sum_gnr=gnr_control_sum([nz.gnr]),
    )
    return encode_aa(aa) + body + bb
