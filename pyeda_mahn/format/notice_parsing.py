"""Shared fixed-width decode helpers for inbound EDA notice parsers.

The court-side notices (KEZI 03/05/16/18/20/22/90) are 128-byte fixed-width
records using the same field codecs as the outbound encoder. These helpers
decode the typed fields (X text, Datum6 JJMMTT, N(2) Betrag) the parsers read.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pyeda_mahn.format.record import EDA_TEXT_CODEC


def decode_field(record: bytes, start: int, length: int) -> str:
    """Decode a fixed-width text field, right-stripped of padding."""
    return record[start : start + length].decode(EDA_TEXT_CODEC, errors="replace").rstrip()


def parse_datum6(raw: str) -> date | None:
    """Parse a ``JJMMTT`` Datum6 field. Empty / invalid → ``None``.

    Two-digit year window: 00-79 → 20xx, 80-99 → 19xx (mirrors the QU parser).
    """
    raw = raw.strip()
    if len(raw) < 6 or not raw[:6].isdigit():
        return None
    yy, mm, dd = int(raw[0:2]), int(raw[2:4]), int(raw[4:6])
    yyyy = 2000 + yy if yy < 80 else 1900 + yy
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def parse_betrag(raw: str, *, scale: int = 2) -> Decimal | None:
    """Parse an ``N(scale)`` Betrag (zero-padded, implicit decimal). Empty → ``None``."""
    raw = raw.strip()
    if not raw or not raw.isdigit():
        return None
    return (Decimal(int(raw)) / Decimal(10**scale)).quantize(Decimal("0.01"))
