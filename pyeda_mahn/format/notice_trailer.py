"""BB Dateinachsatz for notice-style Antragsarten (RN / VBA / NEMB / …).

The MBA BB (``bb_satz.BBNachsatz``) sums Katalog-Nummern + Anspruchsbeträge.
The notice-style Antragsarten (KEZI 25 RN, 08 VBA, 07 NEMB, 10 NEVB, 29
EZKOAB, 30 WI) instead carry, per their Satzbeschreibungen:

    SA(2) TKEZI(8N) ANTANZ(7N) SANZ(7N) SKATNR(7N=NULL) SUASP(14N=NULL)
    SUGNR(15N) ASPANZ(7N=NULL) FILLER(61X)

``SUGNR`` is the sum of positions 3-9 of every 11-digit Gerichtsnummer in the
file (Konditionen §5.2). ``ANTANZ`` counts the Nachrichten, ``SANZ`` the body
Einzeldatensätze (excludes AA + BB).
"""

from __future__ import annotations

from dataclasses import dataclass

from pyeda_mahn.format.record import EDARecord, encode_blank, encode_n, encode_x_gross


def gnr_control_sum(gnrs: list[str]) -> int:
    """Sum positions 3-9 (the 7-digit laufende Nummer) of each 11-digit GNR."""
    total = 0
    for gnr in gnrs:
        digits = gnr.strip()
        if len(digits) >= 9 and digits[2:9].isdigit():
            total += int(digits[2:9])
    return total


@dataclass(frozen=True)
class NoticeBBRecord(EDARecord):
    """BB trailer for notice-style Antragsarten."""

    tkezi: str
    antrag_count: int
    satz_count: int
    sum_gnr: int

    def payload(self) -> bytes:
        """Encode the notice-style BB trailer payload."""
        parts: list[bytes] = [
            encode_x_gross("BB", max_length=2, field_name="BB.SA"),
            encode_n(self.tkezi, max_length=8, field_name="BB.TKEZI"),
            encode_n(self.antrag_count, max_length=7, field_name="BB.ANTANZ"),
            encode_n(self.satz_count, max_length=7, field_name="BB.SANZ"),
            encode_n(0, max_length=7, field_name="BB.SKATNR"),  # NULL
            encode_n(0, max_length=14, field_name="BB.SUASP"),  # NULL
            encode_n(self.sum_gnr, max_length=15, field_name="BB.SUGNR"),
            encode_n(0, max_length=7, field_name="BB.ASPANZ"),  # NULL
        ]
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


def encode_notice_bb(*, tkezi: str, antrag_count: int, satz_count: int, sum_gnr: int) -> bytes:
    """Encode the notice-style BB Dateinachsatz to its 128-byte record."""
    return NoticeBBRecord(
        tkezi=tkezi,
        antrag_count=antrag_count,
        satz_count=satz_count,
        sum_gnr=sum_gnr,
    ).to_bytes()
