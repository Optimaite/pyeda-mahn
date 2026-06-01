"""AA Dateivorsatz (file header record).

Per ``refs/02_KEZI_01_MBA_Satzfolge.md`` § "A — Dateivorsatz" — every
logical EDA file starts with one ``AA`` record carrying:

  * SA          = ``AA``        (2 X/groß)
  * TKEZI       = Teilnehmer-Kennziffer (8 N)
  * DATUM       = file creation in JJMMTT  (6 N)
  * BELART      = Belegart, ``01`` for MBA batches (2 X/groß)
  * EKEZI       = Einreicher-Kennziffer (8 N/B; only EKEZI-Verfahren)
  * FORMAT      = ``4000``        (4 X/groß)
  * EDAID       = file bezeichnung in Großbuchstaben (12 X/groß)
  * FILLER (BLANK to padding)
  * SWN         = Software-Name   (35 X)
  * SWV         = Software-Version (10 X)

Layout chosen to mirror the published worked examples — EDAID generated per
file as ``OPT{YYYYMMDD}{HHMMSS}{seq3}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from pyeda_mahn.format.record import (
    EDARecord,
    encode_blank,
    encode_datum6,
    encode_n,
    encode_n_b,
    encode_x,
    encode_x_gross,
)

DEFAULT_FORMAT = "4000"
DEFAULT_SOFTWARE_NAME = "Optimaite Law"
DEFAULT_SOFTWARE_VERSION = "1.0.0"


def build_edaid(*, when: datetime, seq: int) -> str:
    """Generate a deterministic EDAID for a single AA-Satz.

    ``OPT{YYYYMMDD}{HHMMSS}`` truncated to 12 bytes — keeps it
    uppercase-alphanumeric and unique per minute. ``seq`` is reserved for
    multi-logical-file physical files.
    """
    stamp = f"{when:%y%m%d%H%M%S}"  # 12 bytes
    return f"OPT{stamp[:9]}"[:12].upper()


class AAVorsatz(BaseModel):
    """Pydantic input for the AA Dateivorsatz record."""

    model_config = ConfigDict(frozen=True)

    tkezi: str = Field(..., min_length=8, max_length=8, description="8-digit Teilnehmer-Kennziffer")
    file_date: date = Field(..., description="File creation date (JJMMTT)")
    belart: str = Field(default="01", min_length=2, max_length=2)
    ekezi: str | None = Field(default=None, description="Einreicher-Kennziffer (only EKEZI-Verfahren)")
    format_code: str = Field(default=DEFAULT_FORMAT, min_length=4, max_length=4)
    edaid: str = Field(..., min_length=1, max_length=12)
    software_name: str = Field(default=DEFAULT_SOFTWARE_NAME)
    software_version: str = Field(default=DEFAULT_SOFTWARE_VERSION)


@dataclass(frozen=True)
class AARecord(EDARecord):
    """Concrete AA Dateivorsatz."""

    vorsatz: AAVorsatz

    def payload(self) -> bytes:
        v = self.vorsatz
        parts: list[bytes] = []
        parts.append(encode_x_gross("AA", max_length=2, field_name="AA.SA"))
        parts.append(encode_n(v.tkezi, max_length=8, field_name="AA.TKEZI"))
        parts.append(encode_datum6(v.file_date, field_name="AA.DATUM"))
        parts.append(encode_x_gross(v.belart, max_length=2, field_name="AA.BELART"))
        parts.append(encode_n_b(v.ekezi, max_length=8, field_name="AA.EKEZI"))
        parts.append(encode_x_gross(v.format_code, max_length=4, field_name="AA.FORMAT"))
        parts.append(encode_x_gross(v.edaid, max_length=12, field_name="AA.EDAID"))
        parts.append(encode_blank(max_length=14))  # FILLER
        parts.append(encode_x(v.software_name, max_length=35, field_name="AA.SWN"))
        parts.append(encode_x(v.software_version, max_length=10, field_name="AA.SWV"))
        return b"".join(parts)


def encode_aa(vorsatz: AAVorsatz) -> bytes:
    """Encode the AA Dateivorsatz to its 128-byte record."""
    return AARecord(vorsatz=vorsatz).to_bytes()
