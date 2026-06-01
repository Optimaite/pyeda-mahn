"""Common record-prefix helpers for the MBA Satzfolge.

Per refs/02 every MBA record carries:
  * Pos. 1-2  = SA  = "01"
  * Pos. 3-4  = KZ  = Kennzeichen of the Teilsatz (e.g. AS, AG, KS, ...)
  * Pos. 5-6  = FN  = Folgenummer within block (e.g. "01" for first AS,
                 "02" for second AS)
  * Pos. 7-9  = TN  = Teilsatznummer within the FN block (e.g. "01" for
                 AS_01, "02" for AS_02, "03" for AS_03)
"""

from __future__ import annotations

from pyeda_mahn.format.record import encode_n, encode_x_gross


def record_header(*, kz: str, fn: int, tn: int) -> bytes:
    """Build the first 9 bytes of any MBA record."""
    parts = [
        encode_x_gross("01", max_length=2, field_name="MBA.SA"),
        encode_x_gross(kz, max_length=2, field_name="MBA.KZ"),
        encode_n(fn, max_length=2, field_name="MBA.FN"),
        encode_n(tn, max_length=3, field_name="MBA.TN"),
    ]
    return b"".join(parts)
