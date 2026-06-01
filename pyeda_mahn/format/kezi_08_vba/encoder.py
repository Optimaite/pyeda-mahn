"""KEZI 08 VBA — Vollstreckungsbescheidsantrag encoder.

``AA`` (BELART ``08``, FORMAT ``4100``) + ``E01`` Kennsatz + optional ``E02``
Zahlungsangaben + optional ``E03``/``E05`` Antragsgegner block + ``BB``.

Byte layout per the vendored ``EDA-SB_KEZI_08_4100_VBA.pdf`` (Format 4.1 V 4.0.00):
- E01 Kennsatz: SA(2)=``08``, KENNZ(5)=``KS``, FN(2)=``00``, TKEZI(8N/B),
  GNR(11N), ASGZ(30X), VBAND(6X JJMMTT), VBZAM(1X: 1/2), VBZUM(1X: 1/2),
  VBPTBET(8N(2)/B), VBSKOBET(8N(2)/B), VBSKOBG(35X), KOZIM(1X), ASPVAUSL(7N(2)/0).
  (sums to exactly 125 payload bytes.)
- E02 Zahlungen (only when VBZAM=2): SA, KENNZ(5)=``ZAHL``, FN=``00``, then
  6x [ZAD(6X JJMMTT) + ZABET(10N(2)/B)], FILLER(23).
- E03/E05 Antragsgegner: identical to the KEZI 07 NEMB D02/D04 records.

NOTE: pending live Mahngericht Testdurchgang pinning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from pyeda_mahn.contracts import VollstreckungsbescheidInput
from pyeda_mahn.format.aa_satz import AAVorsatz, build_edaid, encode_aa
from pyeda_mahn.format.kezi_07_nemb.encoder import (
    NeuzustellungAgAddressRecord,
    NeuzustellungAgNameRecord,
)
from pyeda_mahn.format.notice_trailer import encode_notice_bb, gnr_control_sum
from pyeda_mahn.format.record import (
    EDARecord,
    encode_betrag,
    encode_blank,
    encode_datum6,
    encode_n,
    encode_n_b,
    encode_x,
    encode_x_gross,
)

_VBZUM = {"durch_gericht": "1", "parteibetrieb": "2"}


def _betrag_or_blank(value: Decimal | None, *, max_length: int, field_name: str) -> bytes:
    if value is None:
        return encode_blank(max_length=max_length)
    return encode_betrag(value, max_length=max_length, field_name=field_name)


@dataclass(frozen=True)
class VbaKennsatzRecord(EDARecord):
    """E01 Vollstreckungsbescheidsantrag Kennsatz."""

    vba: VollstreckungsbescheidInput

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        vba = self.vba
        parts: list[bytes] = [
            encode_x_gross("08", max_length=2, field_name="VBA.SA"),
            encode_x_gross("KS", max_length=5, field_name="VBA.KENNZ"),
            encode_x("00", max_length=2, field_name="VBA.FN"),
            encode_n_b(vba.tkezi, max_length=8, field_name="VBA.TKEZI"),
            encode_n(vba.gnr, max_length=11, field_name="VBA.GNR"),
            encode_x(vba.tgz, max_length=30, field_name="VBA.ASGZ"),
            encode_datum6(vba.antragstellung_datum, field_name="VBA.VBAND"),
            encode_x_gross("2" if vba.zahlungen else "1", max_length=1, field_name="VBA.VBZAM"),
            encode_x_gross(_VBZUM[vba.zustellung], max_length=1, field_name="VBA.VBZUM"),
            _betrag_or_blank(vba.porto_telefon, max_length=8, field_name="VBA.VBPTBET"),
            _betrag_or_blank(vba.sonstige_kosten, max_length=8, field_name="VBA.VBSKOBET"),
            encode_x(vba.sonstige_kosten_begruendung or "", max_length=35, field_name="VBA.VBSKOBG"),
            encode_x_gross("X" if vba.zinsen_auf_kosten else "", max_length=1, field_name="VBA.KOZIM"),
            _betrag_or_blank(vba.aspv_auslagen, max_length=7, field_name="VBA.ASPVAUSL"),
        ]
        # The E01 fields sum to exactly 125 payload bytes (no extra FILLER).
        return b"".join(parts)


@dataclass(frozen=True)
class VbaZahlungenRecord(EDARecord):
    """E02 Angaben zu Zahlungen (up to 6 payments)."""

    vba: VollstreckungsbescheidInput

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        parts: list[bytes] = [
            encode_x_gross("08", max_length=2, field_name="VBA.SA"),
            encode_x_gross("ZAHL", max_length=5, field_name="VBA.KENNZ"),
            encode_x("00", max_length=2, field_name="VBA.FN"),
        ]
        zahlungen = list(self.vba.zahlungen)
        for idx in range(6):
            if idx < len(zahlungen):
                z = zahlungen[idx]
                parts.append(encode_datum6(z.datum, field_name=f"VBA.ZAD{idx + 1}"))
                parts.append(encode_betrag(z.betrag, max_length=10, field_name=f"VBA.ZABET{idx + 1}"))
            else:
                parts.append(encode_blank(max_length=6))
                parts.append(encode_blank(max_length=10))
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


def encode_vollstreckungsbescheidsantrag(
    vba: VollstreckungsbescheidInput,
    *,
    file_when: datetime | None = None,
    edaid: str | None = None,
) -> bytes:
    """Encode a KEZI 08 Vollstreckungsbescheidsantrag to its ``.eda`` byte stream."""
    when = file_when or datetime.now(UTC)
    aa = AAVorsatz(
        tkezi=vba.tkezi,
        file_date=when.date(),
        belart="08",
        format_code="4100",
        edaid=edaid or build_edaid(when=when, seq=1),
    )
    body = VbaKennsatzRecord(vba=vba).to_bytes()
    satz_count = 1
    if vba.zahlungen:
        body += VbaZahlungenRecord(vba=vba).to_bytes()
        satz_count += 1
    if vba.antragsgegner is not None:
        body += NeuzustellungAgNameRecord(ag=vba.antragsgegner, belart="08").to_bytes()
        body += NeuzustellungAgAddressRecord(ag=vba.antragsgegner, belart="08").to_bytes()
        satz_count += 2
    bb = encode_notice_bb(
        tkezi=vba.tkezi,
        antrag_count=1,
        satz_count=satz_count,
        sum_gnr=gnr_control_sum([vba.gnr]),
    )
    return encode_aa(aa) + body + bb
