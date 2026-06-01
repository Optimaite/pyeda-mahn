"""BB Dateinachsatz (file trailer record) + per-Antragsart Kontrollsummen.

Per EDA-Konditionen §5.2 the BB-Satz carries control totals the Mahngericht
validates against the body of the file:

  * SA              = ``BB`` (2 X/groß)
  * Anzahl Datensätze (excl. AA + BB) (6 N)
  * Anzahl Anträge / Kennsätze (6 N)
  * MBA Kontrollsummen:
      - Σ Katalog-Nummern         (10 N)
      - Σ Anspruchsbeträge (Cent) (15 N)
      - Σ Anzahl Hauptansprüche   (6 N)
  * Filler

The Kontrollsummen calculator takes the typed Kennsatz + ASPK00 lists and
returns the totals — kept pure so it is testable in isolation.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from pyeda_mahn.format.record import (
    EDARecord,
    encode_blank,
    encode_n,
    encode_x_gross,
)


@dataclass(frozen=True)
class MBAControlTotals:
    """Per-Antragsart Kontrollsummen for the MBA case."""

    record_count: int
    antrag_count: int
    sum_katalog_nrn: int
    sum_anspruchsbetraege_cents: int
    sum_hauptansprueche_count: int


def compute_mba_control_totals(
    *,
    record_count: int,
    antrag_count: int,
    katalog_nrn: Iterable[int],
    anspruchsbetraege: Iterable[Decimal | int],
    hauptansprueche_per_antrag: Iterable[int],
) -> MBAControlTotals:
    """Compute the four MBA Kontrollsummen.

    ``record_count`` excludes the AA + BB sätze; the caller supplies it from
    the assembled body.
    ``anspruchsbetraege`` are summed in Cent (with the standard half-up
    rounding implicit in :class:`Decimal`).
    """
    sum_kat = sum(int(k) for k in katalog_nrn)
    cents = 0
    for amt in anspruchsbetraege:
        if isinstance(amt, Decimal):
            cents += int((amt * Decimal(100)).to_integral_value())
        else:
            cents += int(amt) * 100
    sum_hauptansprueche = sum(int(c) for c in hauptansprueche_per_antrag)
    return MBAControlTotals(
        record_count=record_count,
        antrag_count=antrag_count,
        sum_katalog_nrn=sum_kat,
        sum_anspruchsbetraege_cents=cents,
        sum_hauptansprueche_count=sum_hauptansprueche,
    )


class BBNachsatz(BaseModel):
    """Pydantic input for the BB Dateinachsatz record."""

    model_config = ConfigDict(frozen=True)

    record_count: int = Field(..., ge=0)
    antrag_count: int = Field(..., ge=0)
    sum_katalog_nrn: int = Field(..., ge=0)
    sum_anspruchsbetraege_cents: int = Field(..., ge=0)
    sum_hauptansprueche_count: int = Field(..., ge=0)


@dataclass(frozen=True)
class BBRecord(EDARecord):
    nachsatz: BBNachsatz

    def payload(self) -> bytes:
        n = self.nachsatz
        parts: list[bytes] = []
        parts.append(encode_x_gross("BB", max_length=2, field_name="BB.SA"))
        parts.append(encode_n(n.record_count, max_length=6, field_name="BB.AZ_DS"))
        parts.append(encode_n(n.antrag_count, max_length=6, field_name="BB.AZ_KS"))
        parts.append(
            encode_n(n.sum_katalog_nrn, max_length=10, field_name="BB.SUM_KATALOG")
        )
        parts.append(
            encode_n(
                n.sum_anspruchsbetraege_cents,
                max_length=15,
                field_name="BB.SUM_BETRAEGE_CENT",
            )
        )
        parts.append(
            encode_n(
                n.sum_hauptansprueche_count,
                max_length=6,
                field_name="BB.SUM_HAUPT",
            )
        )
        # FILLER to fill payload.
        remaining = 125 - sum(len(p) for p in parts)
        parts.append(encode_blank(max_length=remaining))
        return b"".join(parts)


def encode_bb(nachsatz: BBNachsatz) -> bytes:
    return BBRecord(nachsatz=nachsatz).to_bytes()
