"""KEZI 29 EZKOAB — Antrag Kosteneinzug nach Widerspruch / Abgabeantrag encoder.

``AA`` + one ``I01`` Kennsatz + ``BB``. Byte layout per the vendored
``EDA-SB_KEZI_29_4000_EZKOAB.pdf`` (Format 4 V 4.0.00): I01 Kennsatz —
SA(2)=``29``, KENNZ(5)=``KS``, FN(2)=``00``, TKEZI(8N), GNR(11N), ASGZ(35X),
EAM(1X)=``X`` (zwingend), FILLER(64). The SEPA fields (8-12) were retired in
2014.

NOTE: pending live Mahngericht Testdurchgang pinning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pyeda_mahn.contracts import KostenAbgabeAntragInput
from pyeda_mahn.format.aa_satz import AAVorsatz, build_edaid, encode_aa
from pyeda_mahn.format.notice_trailer import encode_notice_bb, gnr_control_sum
from pyeda_mahn.format.record import (
    EDARecord,
    encode_blank,
    encode_n,
    encode_x,
    encode_x_gross,
)


@dataclass(frozen=True)
class EzkoabKennsatzRecord(EDARecord):
    """I01 Kosteneinzug/Abgabe Kennsatz."""

    antrag: KostenAbgabeAntragInput

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        a = self.antrag
        parts: list[bytes] = [
            encode_x_gross("29", max_length=2, field_name="EZ.SA"),
            encode_x_gross("KS", max_length=5, field_name="EZ.KENNZ"),
            encode_x("00", max_length=2, field_name="EZ.FN"),
            encode_n(a.tkezi, max_length=8, field_name="EZ.TKEZI"),
            encode_n(a.gnr, max_length=11, field_name="EZ.GNR"),
            encode_x(a.tgz, max_length=35, field_name="EZ.ASGZ"),
            encode_x_gross("X", max_length=1, field_name="EZ.EAM"),  # zwingend "X"
        ]
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


def encode_kosten_abgabe_antrag(
    antrag: KostenAbgabeAntragInput,
    *,
    file_when: datetime | None = None,
    edaid: str | None = None,
) -> bytes:
    """Encode a KEZI 29 EZKOAB to its ``.eda`` byte stream."""
    when = file_when or datetime.now(UTC)
    aa = AAVorsatz(
        tkezi=antrag.tkezi,
        file_date=when.date(),
        belart="29",
        edaid=edaid or build_edaid(when=when, seq=1),
    )
    kennsatz = EzkoabKennsatzRecord(antrag=antrag).to_bytes()
    bb = encode_notice_bb(
        tkezi=antrag.tkezi,
        antrag_count=1,
        satz_count=1,
        sum_gnr=gnr_control_sum([antrag.gnr]),
    )
    return encode_aa(aa) + kennsatz + bb
