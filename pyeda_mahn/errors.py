"""Typed EDA exceptions.

Every encoder/parser failure rides one of these subclasses so callers can
distinguish charset, length, Aussteuerung, and invariant violations without
string-matching.

See ``refs/01_EDA-Konditionen.md`` § 4.3.2 (charset),
``refs/01_EDA-Konditionen.md`` § 11 (Aussteuerung), and
``refs/02_KEZI_01_MBA_Satzfolge.md`` § "Hard rules" (Kennziffer ⊕ Stammdaten,
PKH-Verbot, etc).
"""

from __future__ import annotations


class EDAError(Exception):
    """Base class for all EDA-Mahn encoder/parser failures."""


class EDACharsetError(EDAError):
    """A field contains a character not in the EDA allowed-charset table.

    The EDA-Konditionen §4.3.2 allowed-charset includes ASCII 7-bit plus the
    German set ``& ' ( ) * + , - . / : ; = @ € ü ä Ä ö Ö Ü ß §`` and a few
    other special characters. Anything else fails closed.
    """

    def __init__(self, *, field: str, char: str, position: int):
        self.field = field
        self.char = char
        self.position = position
        super().__init__(
            f"EDACharsetError: field {field!r} position {position} contains "
            f"disallowed character {char!r}"
        )


class EDAFieldLengthError(EDAError):
    """A field value exceeds the declared maximum byte length."""

    def __init__(self, *, field: str, length: int, max_length: int):
        self.field = field
        self.length = length
        self.max_length = max_length
        super().__init__(
            f"EDAFieldLengthError: field {field!r} length {length} exceeds "
            f"maximum {max_length}"
        )


class EDAAussteuerungError(EDAError):
    """A Mahnbescheidsantrag violates one of the §2.6.1.1 Aussteuerungs-Caps.

    The Mahngericht's automated processing fails the file if any of these
    limits is exceeded; per project policy the encoder fails closed first.
    """

    def __init__(self, *, limit_name: str, value: int, max_value: int):
        self.limit_name = limit_name
        self.value = value
        self.max_value = max_value
        super().__init__(
            f"EDAAussteuerungError: {limit_name} = {value}, max allowed "
            f"= {max_value}"
        )


class EDAInvariantError(EDAError):
    """A structural invariant from the Satzbeschreibung is violated.

    Used for ``Kennziffer ⊕ Stammdaten``, PKH ✗ EDA, missing-required-block,
    Aktenzeichen format, and any other rule that is not a charset or
    Aussteuerung cap.
    """

    def __init__(self, *, invariant_name: str, detail: str):
        self.invariant_name = invariant_name
        self.detail = detail
        super().__init__(
            f"EDAInvariantError: {invariant_name}: {detail}"
        )
