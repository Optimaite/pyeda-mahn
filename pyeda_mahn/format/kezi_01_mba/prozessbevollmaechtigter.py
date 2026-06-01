"""C07-C10 — Prozessbevollmächtigter (ASPV) + antragsspezifische Angaben (ASPVA00)."""

from __future__ import annotations

from dataclasses import dataclass

from pyeda_mahn.contracts import (
    ASPVAngaben,
    GesetzlicherVertreter,
    Prozessbevollmaechtigter,
)
from pyeda_mahn.format.kezi_01_mba._common import record_header
from pyeda_mahn.format.record import (
    EDARecord,
    encode_betrag,
    encode_blank,
    encode_datum6,
    encode_x,
    encode_x_gross,
)


def _pad_payload(parts: list[bytes]) -> bytes:
    used = sum(len(p) for p in parts)
    if used < 125:
        parts.append(encode_blank(max_length=125 - used))
    return b"".join(parts)


@dataclass(frozen=True)
class ASPV01Record(EDARecord):
    """C07 ASPV_01 — PV_Teil-01 (Anrede, name)."""

    pv: Prozessbevollmaechtigter

    def payload(self) -> bytes:
        p = self.pv
        parts: list[bytes] = []
        parts.append(record_header(kz="PV", fn=1, tn=1))
        parts.append(encode_x_gross(p.anrede, max_length=1, field_name="ASPV.ASPVANR"))
        parts.append(encode_x(p.name, max_length=105, field_name="ASPV.ASPVN"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class ASPV02Record(EDARecord):
    """C08 ASPV_02 — PV_Teil-02 (Rechtsform + Anschrift)."""

    pv: Prozessbevollmaechtigter

    def payload(self) -> bytes:
        p = self.pv
        ad = p.address
        parts: list[bytes] = []
        parts.append(record_header(kz="PV", fn=1, tn=2))
        parts.append(encode_x(p.rechtsform or "", max_length=35, field_name="ASPV.ASPVRF"))
        parts.append(encode_x(ad.strasse_hausnummer, max_length=35, field_name="ASPV.ASPHSH"))
        parts.append(encode_x(ad.plz, max_length=5, field_name="ASPV.ASPVPLZ"))
        parts.append(encode_x(ad.ort, max_length=27, field_name="ASPV.ASPVO"))
        parts.append(encode_x(ad.auslandskennzeichen or "", max_length=3, field_name="ASPV.ASPVAL"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class ASPV03Record(EDARecord):
    """C09 ASPV_03 — gesetzlicher Vertreter des PV (only Anrede 7-9)."""

    vertreter: GesetzlicherVertreter

    def payload(self) -> bytes:
        v = self.vertreter
        parts: list[bytes] = []
        parts.append(record_header(kz="PV", fn=1, tn=3))
        parts.append(encode_x(v.stellung, max_length=35, field_name="ASPV.ASPVGVFU"))
        parts.append(encode_x(v.name, max_length=35, field_name="ASPV.ASPVGVN"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class ASPVA00Record(EDARecord):
    """C10 ASPVA00 — antragsspezifische Angaben zum PV."""

    angaben: ASPVAngaben

    def payload(self) -> bytes:
        a = self.angaben
        parts: list[bytes] = []
        parts.append(record_header(kz="PA", fn=1, tn=1))
        parts.append(encode_x(a.abweichendes_geschaeftszeichen or "", max_length=35, field_name="ASPVA.ASPVGZ"))
        parts.append(encode_datum6(a.beauftragung_date, field_name="ASPVA.ASPVAUFD"))
        parts.append(encode_betrag(a.auslagen_betrag, max_length=10, field_name="ASPVA.ASPVMBAUSL"))
        parts.append(encode_betrag(a.vv2300_minderungsbetrag, max_length=12, field_name="ASPVA.VV2300MBET"))
        parts.append(
            encode_x_gross("X" if a.vv2300_versicherung_umfang else "", max_length=1, field_name="ASPVA.VV2300M")
        )
        parts.append(encode_betrag(a.inkasso_erstattungsbetrag, max_length=9, field_name="ASPVA.IKUBET"))
        return _pad_payload(parts)


def encode_pv_block(
    *,
    pv: Prozessbevollmaechtigter | None,
    angaben: ASPVAngaben | None,
) -> list[EDARecord]:
    """Emit ASPV_01..ASPV_03 + ASPVA00 records.

    When ``pv.pvkezi`` is set, the ASPV_01..ASPV_03 stammdaten are emitted
    empty (refs/02 hard rule #1) — but ASPVA00 is still required if any
    antragsspezifische Angaben are present (rule #2).
    """
    records: list[EDARecord] = []
    if pv is not None and pv.pvkezi is None:
        records.append(ASPV01Record(pv=pv))
        records.append(ASPV02Record(pv=pv))
        if pv.gesetzlicher_vertreter is not None and pv.anrede in ("7", "8", "9"):
            records.append(ASPV03Record(vertreter=pv.gesetzlicher_vertreter))
    if angaben is not None:
        records.append(ASPVA00Record(angaben=angaben))
    return records
