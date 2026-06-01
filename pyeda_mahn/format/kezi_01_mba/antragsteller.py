"""C02-C06 — Antragsteller (AS) and gesetzliche Vertreter (ASGV) records."""

from __future__ import annotations

from dataclasses import dataclass

from pyeda_mahn.contracts import (
    Antragsteller,
    GesetzlicherVertreter,
    PartyAddress,
)
from pyeda_mahn.format.kezi_01_mba._common import record_header
from pyeda_mahn.format.record import (
    EDARecord,
    encode_blank,
    encode_x,
    encode_x_gross,
)


def _pad_payload(parts: list[bytes]) -> bytes:
    used = sum(len(p) for p in parts)
    if used < 125:
        parts.append(encode_blank(max_length=125 - used))
    return b"".join(parts)


@dataclass(frozen=True)
class AS01Record(EDARecord):
    """C02 AS_01 — Antragsteller_Teil-01."""

    antragsteller: Antragsteller
    fn: int  # 1-based Folgenummer within block

    def payload(self) -> bytes:
        a = self.antragsteller
        parts: list[bytes] = []
        parts.append(record_header(kz="AS", fn=self.fn, tn=1))
        parts.append(encode_x_gross(a.anrede, max_length=1, field_name="AS.ASANR"))
        parts.append(encode_x(a.rechtsform or "", max_length=35, field_name="AS.ASRF"))
        parts.append(encode_x(a.name1, max_length=35, field_name="AS.ASN1"))
        parts.append(encode_x(a.name2 or "", max_length=35, field_name="AS.ASN2"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class AS02Record(EDARecord):
    """C03 AS_02 — Antragsteller_Teil-02 (juristische Person Fortsetzung)."""

    antragsteller: Antragsteller
    fn: int

    def payload(self) -> bytes:
        a = self.antragsteller
        parts: list[bytes] = []
        parts.append(record_header(kz="AS", fn=self.fn, tn=2))
        parts.append(encode_x(a.name3 or "", max_length=35, field_name="AS.ASN3"))
        parts.append(encode_x(a.name4 or "", max_length=35, field_name="AS.ASN4"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class AS03Record(EDARecord):
    """C04 AS_03 — Antragsteller_Teil-03 (Anschrift)."""

    antragsteller: Antragsteller
    fn: int

    def payload(self) -> bytes:
        a = self.antragsteller
        ad = a.address
        parts: list[bytes] = []
        parts.append(record_header(kz="AS", fn=self.fn, tn=3))
        parts.append(encode_x(ad.strasse_hausnummer, max_length=35, field_name="AS.ASSH"))
        parts.append(encode_x(ad.plz, max_length=5, field_name="AS.ASPLZ"))
        parts.append(encode_x(ad.ort, max_length=27, field_name="AS.ASO"))
        parts.append(encode_x(ad.auslandskennzeichen or "", max_length=3, field_name="AS.ASAL"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class ASGV01Record(EDARecord):
    """C05 ASGV_01 — gesetzlicher Vertreter Teil-01."""

    vertreter: GesetzlicherVertreter
    as_fn: int
    gv_fn: int

    def payload(self) -> bytes:
        v = self.vertreter
        parts: list[bytes] = []
        parts.append(record_header(kz="GS", fn=self.as_fn, tn=self.gv_fn * 10 + 1))
        # Note: refs/02 lays out ASGV as kz="GS" or "GV" with FN combining AS
        # and GV indices; we keep gv_fn high-byte for clarity.
        parts.append(encode_x(v.stellung, max_length=35, field_name="ASGV.ASGVFU"))
        parts.append(encode_x(v.name, max_length=35, field_name="ASGV.ASGVN"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class ASGV02Record(EDARecord):
    """C06 ASGV_02 — Anschrift des gesetzlichen Vertreters."""

    vertreter: GesetzlicherVertreter
    as_fn: int
    gv_fn: int

    def payload(self) -> bytes:
        v = self.vertreter
        ad = v.address or PartyAddress(strasse_hausnummer="", plz="00000", ort="")
        parts: list[bytes] = []
        parts.append(record_header(kz="GS", fn=self.as_fn, tn=self.gv_fn * 10 + 2))
        parts.append(encode_x(ad.strasse_hausnummer, max_length=35, field_name="ASGV.ASGVSH"))
        parts.append(encode_x(ad.plz, max_length=5, field_name="ASGV.ASGVPLZ"))
        parts.append(encode_x(ad.ort, max_length=27, field_name="ASGV.ASGVO"))
        parts.append(encode_x(ad.auslandskennzeichen or "", max_length=3, field_name="ASGV.ASGVAL"))
        return _pad_payload(parts)


def encode_antragsteller_block(
    *, antragsteller: Antragsteller, fn: int
) -> list[EDARecord]:
    """Emit the AS_01..AS_03 + ASGV_* chain for one Antragsteller.

    The Folgenummer (FN) is the AS index within the Antrag (1-based).
    Eheleute shorthand: if ``is_eheleute=True`` and ``spouse_name1`` is
    given, append a second AS_01 Folgesatz referencing the spouse by name
    only (refs/02 §"natural-person Sonderfall Eheleute").
    """
    records: list[EDARecord] = []
    records.append(AS01Record(antragsteller=antragsteller, fn=fn))
    if antragsteller.name3 or antragsteller.name4 or antragsteller.rechtsform:
        records.append(AS02Record(antragsteller=antragsteller, fn=fn))
    records.append(AS03Record(antragsteller=antragsteller, fn=fn))

    # Eheleute shorthand — second AS_01 only, no second AS_03 (same address).
    if antragsteller.is_eheleute and antragsteller.spouse_name1:
        spouse_ast = antragsteller.model_copy(
            update={
                "name1": antragsteller.spouse_name1,
                "name2": antragsteller.name2,
                "is_eheleute": False,
                "spouse_name1": None,
            }
        )
        records.append(AS01Record(antragsteller=spouse_ast, fn=fn))

    # Gesetzlicher Vertreter chain
    for gv_idx, v in enumerate(antragsteller.vertreter, start=1):
        records.append(ASGV01Record(vertreter=v, as_fn=fn, gv_fn=gv_idx))
        if v.address is not None:
            records.append(ASGV02Record(vertreter=v, as_fn=fn, gv_fn=gv_idx))
    return records
