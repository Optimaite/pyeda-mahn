"""KEZI 25 RN — Rücknahme / Erledigterklärung encoder.

Builds ``AA`` + one ``H01`` Kennsatz + ``BB`` from a :class:`RuecknahmeInput`.
With a Gerichtsnummer present (``GNRM='J'``) the Parteikurzdaten (H02) record
is not required, so a Rücknahme is a single body record.

Byte layout per the vendored ``EDA-SB_KEZI_25_4000_RN.pdf`` (Format 4 V 4.0.00):
H01 Kennsatz — SA(2)=``25``, KENNZ(5)=``KS``, FN(2)=``00``, TKEZI(8N),
TGZ(35X), REM(1X: R/E), GNRM(1X: J), GNR(11N), MBEGM(1X: B/E), FILLER(62).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pyeda_mahn.contracts import RuecknahmeInput
from pyeda_mahn.format.aa_satz import AAVorsatz, build_edaid, encode_aa
from pyeda_mahn.format.notice_trailer import encode_notice_bb, gnr_control_sum
from pyeda_mahn.format.record import (
    EDARecord,
    encode_blank,
    encode_n,
    encode_x,
    encode_x_gross,
)

_REM = {"ruecknahme": "R", "erledigterklaerung": "E"}
_MBEGM = {"gruener_vordruck": "B", "maschinell": "E"}


@dataclass(frozen=True)
class RnKennsatzRecord(EDARecord):
    """H01 Rücknahme / Erledigterklärung Kennsatz."""

    rn: RuecknahmeInput

    def payload(self) -> bytes:
        """Encode the H01 Rücknahme Kennsatz payload."""
        rn = self.rn
        parts: list[bytes] = [
            encode_x_gross("25", max_length=2, field_name="RN.SA"),
            encode_x_gross("KS", max_length=5, field_name="RN.KENNZ"),
            encode_x("00", max_length=2, field_name="RN.FN"),
            encode_n(rn.tkezi, max_length=8, field_name="RN.TKEZI"),
            encode_x(rn.tgz, max_length=35, field_name="RN.TGZ"),
            encode_x_gross(_REM[rn.art], max_length=1, field_name="RN.REM"),
            encode_x_gross("J", max_length=1, field_name="RN.GNRM"),  # GNR present
            encode_n(rn.gnr, max_length=11, field_name="RN.GNR"),
            encode_x_gross(_MBEGM[rn.mb_eingangsmerkmal], max_length=1, field_name="RN.MBEGM"),
        ]
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


def encode_ruecknahme(
    rn: RuecknahmeInput,
    *,
    file_when: datetime | None = None,
    edaid: str | None = None,
) -> bytes:
    """Encode a KEZI 25 Rücknahme / Erledigterklärung to its ``.eda`` byte stream."""
    when = file_when or datetime.now(UTC)
    aa = AAVorsatz(
        tkezi=rn.tkezi,
        file_date=when.date(),
        belart="25",
        edaid=edaid or build_edaid(when=when, seq=1),
    )
    kennsatz = RnKennsatzRecord(rn=rn).to_bytes()
    bb = encode_notice_bb(
        tkezi=rn.tkezi,
        antrag_count=1,
        satz_count=1,
        sum_gnr=gnr_control_sum([rn.gnr]),
    )
    return encode_aa(aa) + kennsatz + bb
