"""128-byte fixed-width EDA record discipline.

Per EDA-Konditionen §4 every record is exactly 128 bytes: positions 1-125
carry the typed payload, positions 126-128 are the line terminator
``CR LF + filler`` — we emit ``\\r\\n`` followed by one trailing space so the
total length is always 128.

All encoders below produce **bytes**, not str — the wire format is CP-858
for the published CP-850-compatible EDA character set plus the Euro sign.
The EDA-Konditionen §4.3.2 allowed-character set is intentionally narrow; we
encode through CP-858 explicitly and refuse any
character outside the published allowed set.

Field-format encoders mirror the table in
``refs/02_KEZI_01_MBA_Satzfolge.md`` § "Field format conventions":

| Code      | Helper                |
|-----------|-----------------------|
| ``X``     | :func:`encode_x`      |
| ``X/groß``| :func:`encode_x_gross`|
| ``N``     | :func:`encode_n`      |
| ``N/B``   | :func:`encode_n_b`    |
| ``B``     | :func:`encode_blank`  |
| ``Datum`` | :func:`encode_datum6` |
| ``Datum8``| :func:`encode_datum8` |
| ``Betrag``| :func:`encode_betrag` |
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from pyeda_mahn.errors import (
    EDACharsetError,
    EDAFieldLengthError,
)

# ---------------------------------------------------------------------------
# Allowed character set (EDA-Konditionen §4.3.2)
# ---------------------------------------------------------------------------
#
# Allowed: ASCII printable 0x20-0x7E plus the German set
# ``ü ä Ä ö Ö Ü ß §`` plus ``@ €``. Tab, CR, LF, NUL, and any other control
# character is rejected at field-encoding time.
EDA_TEXT_CODEC = "cp858"
_ALLOWED_GERMAN = "üäÄöÖÜß§€"
_ALLOWED_ASCII = set(chr(c) for c in range(0x20, 0x7F))
ALLOWED_CHARS: frozenset[str] = frozenset(_ALLOWED_ASCII | set(_ALLOWED_GERMAN))


# Record line terminator: positions 126-128 inclusive.
# §4.3 of the Konditionen specifies "CR oder CR/LF". We emit CR LF + one
# trailing space so the total record length is exactly 128 bytes regardless
# of EDA codec byte expansion in the typed payload.
_LINE_TERMINATOR = b"\r\n "
RECORD_LENGTH = 128
PAYLOAD_LENGTH = RECORD_LENGTH - len(_LINE_TERMINATOR)  # 125


def _assert_charset(value: str, *, field_name: str) -> None:
    """Raise :class:`EDACharsetError` on the first disallowed character."""
    for idx, ch in enumerate(value):
        if ch not in ALLOWED_CHARS:
            raise EDACharsetError(field=field_name, char=ch, position=idx + 1)


def _to_eda_bytes(value: str, *, field_name: str) -> bytes:
    """Encode an already-charset-validated string to EDA wire bytes."""
    try:
        return value.encode(EDA_TEXT_CODEC)
    except UnicodeEncodeError as exc:  # pragma: no cover — guarded by charset check
        raise EDACharsetError(
            field=field_name, char=str(exc.reason), position=exc.start
        ) from None


def encode_x(value: str, *, max_length: int, field_name: str) -> bytes:
    """Format ``X`` — alphanumeric, mixed case, BLANK-padded right.

    Returns exactly ``max_length`` EDA wire bytes after charset validation.
    Umlauts are preserved exactly (no transliteration — Konditionen §4.3.2).
    """
    if value is None:
        value = ""
    _assert_charset(value, field_name=field_name)
    encoded = _to_eda_bytes(value, field_name=field_name)
    if len(encoded) > max_length:
        raise EDAFieldLengthError(
            field=field_name, length=len(encoded), max_length=max_length
        )
    return encoded.ljust(max_length, b" ")


def encode_x_gross(value: str, *, max_length: int, field_name: str) -> bytes:
    """Format ``X/groß`` — like X but auto-uppercased."""
    return encode_x(value.upper() if value else "", max_length=max_length, field_name=field_name)


def encode_n(value: int | str | None, *, max_length: int, field_name: str) -> bytes:
    """Format ``N`` — numeric, zero-padded left, exact width.

    Negative numbers fail closed.
    """
    if value is None:
        digits = ""
    elif isinstance(value, int):
        if value < 0:
            raise EDAFieldLengthError(
                field=field_name, length=-1, max_length=max_length
            )
        digits = str(value)
    else:
        digits = str(value).strip()
        if not digits.isdigit():
            raise EDACharsetError(field=field_name, char="(non-digit)", position=1)
    if len(digits) > max_length:
        raise EDAFieldLengthError(
            field=field_name, length=len(digits), max_length=max_length
        )
    return digits.rjust(max_length, "0").encode("ascii")


def encode_n_b(value: int | str | None, *, max_length: int, field_name: str) -> bytes:
    """Format ``N/B`` — numeric OR entire field BLANK if value is empty."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return b" " * max_length
    return encode_n(value, max_length=max_length, field_name=field_name)


def encode_blank(*, max_length: int) -> bytes:
    """Format ``B`` — explicit BLANK filler."""
    return b" " * max_length


def encode_datum6(value: date | None, *, field_name: str) -> bytes:
    """Format ``Datum`` — JJMMTT (6 bytes). BLANK if None."""
    if value is None:
        return b" " * 6
    # JJ = two-digit year (per the published Satzbeschreibung) — note that
    # the Konditionen explicitly use 2-digit years here while ``Datum8`` uses
    # the 4-digit form. Production-Mahngerichte have a documented Y2K
    # window: 00-79 → 21xx, 80-99 → 19xx; encoding-side we just emit YY.
    yy = value.year % 100
    mm = value.month
    dd = value.day
    return f"{yy:02d}{mm:02d}{dd:02d}".encode("ascii")


def encode_datum8(value: date | None, *, field_name: str) -> bytes:
    """Format ``Datum8`` — JJJJMMTT (8 bytes). BLANK if None."""
    if value is None:
        return b" " * 8
    return f"{value.year:04d}{value.month:02d}{value.day:02d}".encode("ascii")


def encode_betrag(value: Decimal | int | None, *, max_length: int, field_name: str) -> bytes:
    """Format ``N(2)`` Betrag — total ``max_length`` bytes with 2 implied decimals.

    Value is the EUR amount as ``Decimal`` (or int = whole Euros). We multiply
    by 100 and zero-pad. ``0`` encodes as ``00…00``. BLANK is encoded as
    all-zeros only when the caller explicitly passes ``None`` AND the field
    is documented as ``N(2)`` rather than ``N/B(2)`` — for ``N(2)`` BLANK is
    a Mahngericht reject. We emit zeros for None to keep the contract narrow
    here; per-record callers pass the right value.
    """
    if value is None:
        cents = 0
    elif isinstance(value, Decimal):
        cents = int((value * Decimal(100)).to_integral_value())
    else:
        cents = int(value) * 100
    if cents < 0:
        raise EDAFieldLengthError(
            field=field_name, length=-1, max_length=max_length
        )
    if len(str(cents)) > max_length:
        raise EDAFieldLengthError(
            field=field_name, length=len(str(cents)), max_length=max_length
        )
    return str(cents).rjust(max_length, "0").encode("ascii")


# ---------------------------------------------------------------------------
# Record base
# ---------------------------------------------------------------------------


class EDARecord:
    """Base class for a 128-byte EDA fixed-width record.

    Subclasses implement :meth:`payload` returning the typed payload as
    bytes; :meth:`to_bytes` enforces the 128-byte invariant and appends the
    line terminator.

    The payload must be at most 125 bytes; shorter payloads are
    BLANK-padded right to fill positions up to position 125.
    """

    def payload(self) -> bytes:
        raise NotImplementedError

    def to_bytes(self) -> bytes:
        body = self.payload()
        if len(body) > PAYLOAD_LENGTH:
            raise EDAFieldLengthError(
                field=self.__class__.__name__,
                length=len(body),
                max_length=PAYLOAD_LENGTH,
            )
        body = body.ljust(PAYLOAD_LENGTH, b" ")
        record = body + _LINE_TERMINATOR
        assert len(record) == RECORD_LENGTH, (
            f"EDA record length invariant violated: "
            f"got {len(record)}, expected {RECORD_LENGTH}"
        )
        return record


def concat_records(records: Iterable[EDARecord]) -> bytes:
    """Concatenate a sequence of records into the EDA byte stream."""
    return b"".join(rec.to_bytes() for rec in records)
