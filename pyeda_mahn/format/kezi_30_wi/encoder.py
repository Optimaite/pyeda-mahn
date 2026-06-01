"""KEZI 30 WI — Widerspruch encoder.

``AA`` (BELART ``30``, FORMAT ``4100``) + one ``J01`` Kennsatz + ``BB``. Byte
layout per the vendored ``EDA-SB_KEZI_30_4100_WI.pdf`` (Format 4.1 V 4.0.00):
J01 Kennsatz — SA(2)=``30``, KENNZ(5)=``KS``, FN(2)=``00``, KEZI(8N=AGPV),
GNR(11N), AGGZ(35X), WIM(1X: 1=Gesamt / 2=Teil), then (only when WIM=2)
WIHFBET(10N(2)/B), WIZIM(1X), WIZARTM(2X), WIZISA(5N(3)/B), WIVKOM(1X),
WINEBBET(10N(2)/B), FILLER(35).

NOTE: pending live Mahngericht Testdurchgang pinning. The J02-J04 other-address
/ gesetzlicher-Vertreter records are not emitted (Gesamtwiderspruch happy path).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from pyeda_mahn.contracts import WiderspruchInput
from pyeda_mahn.format.aa_satz import AAVorsatz, build_edaid, encode_aa
from pyeda_mahn.format.notice_trailer import encode_notice_bb, gnr_control_sum
from pyeda_mahn.format.record import (
    EDARecord,
    encode_betrag,
    encode_blank,
    encode_n,
    encode_x,
    encode_x_gross,
)


def _betrag10_or_blank(value: Decimal | None, *, field_name: str) -> bytes:
    if value is None:
        return encode_blank(max_length=10)
    return encode_betrag(value, max_length=10, field_name=field_name)


@dataclass(frozen=True)
class WiKennsatzRecord(EDARecord):
    """J01 Widerspruch Kennsatz."""

    wi: WiderspruchInput

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        wi = self.wi
        teil = wi.umfang == "teil"
        parts: list[bytes] = [
            encode_x_gross("30", max_length=2, field_name="WI.SA"),
            encode_x_gross("KS", max_length=5, field_name="WI.KENNZ"),
            encode_x("00", max_length=2, field_name="WI.FN"),
            encode_n(wi.agpv_kezi, max_length=8, field_name="WI.KEZI"),
            encode_n(wi.gnr, max_length=11, field_name="WI.GNR"),
            encode_x(wi.tgz, max_length=35, field_name="WI.AGGZ"),
            encode_x_gross("2" if teil else "1", max_length=1, field_name="WI.WIM"),
            # Fields 8-13 only when Teilwiderspruch; otherwise BLANK.
            _betrag10_or_blank(wi.widersprochener_hauptbetrag if teil else None, field_name="WI.WIHFBET"),
            encode_x_gross("X" if teil and wi.widerspruch_zinsen else "", max_length=1, field_name="WI.WIZIM"),
            encode_x("", max_length=2, field_name="WI.WIZARTM"),
            encode_blank(max_length=5),  # WIZISA — Zinssatz, blank
            encode_x_gross(
                "X" if teil and wi.widerspruch_verfahrenskosten else "",
                max_length=1,
                field_name="WI.WIVKOM",
            ),
            _betrag10_or_blank(wi.widersprochene_nebenforderung if teil else None, field_name="WI.WINEBBET"),
        ]
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


def encode_widerspruch(
    wi: WiderspruchInput,
    *,
    file_when: datetime | None = None,
    edaid: str | None = None,
) -> bytes:
    """Encode a KEZI 30 Widerspruch to its ``.eda`` byte stream."""
    when = file_when or datetime.now(UTC)
    aa = AAVorsatz(
        tkezi=wi.agpv_kezi,
        file_date=when.date(),
        belart="30",
        format_code="4100",
        edaid=edaid or build_edaid(when=when, seq=1),
    )
    kennsatz = WiKennsatzRecord(wi=wi).to_bytes()
    bb = encode_notice_bb(
        tkezi=wi.agpv_kezi,
        antrag_count=1,
        satz_count=1,
        sum_gnr=gnr_control_sum([wi.gnr]),
    )
    return encode_aa(aa) + kennsatz + bb
