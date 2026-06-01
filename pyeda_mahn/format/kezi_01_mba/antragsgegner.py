"""C13-C18 — Antragsgegner (AG) and gesetzliche Vertreter (AGGV) records."""

from __future__ import annotations

from dataclasses import dataclass

from pyeda_mahn.contracts import Antragsgegner, GesetzlicherVertreter, PartyAddress
from pyeda_mahn.format.kezi_01_mba._common import record_header
from pyeda_mahn.format.record import (
    EDARecord,
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
class AG01Record(EDARecord):
    """C13 AG_01."""

    ag: Antragsgegner
    fn: int

    def payload(self) -> bytes:
        a = self.ag
        parts: list[bytes] = []
        parts.append(record_header(kz="AG", fn=self.fn, tn=1))
        parts.append(encode_x_gross(a.anrede, max_length=1, field_name="AG.ANR"))
        parts.append(encode_x(a.rechtsform or "", max_length=35, field_name="AG.RF"))
        parts.append(encode_x(a.name1, max_length=35, field_name="AG.N1"))
        parts.append(encode_x(a.name2 or "", max_length=35, field_name="AG.N2"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class AG02Record(EDARecord):
    ag: Antragsgegner
    fn: int

    def payload(self) -> bytes:
        a = self.ag
        parts: list[bytes] = []
        parts.append(record_header(kz="AG", fn=self.fn, tn=2))
        parts.append(encode_x(a.name3 or "", max_length=35, field_name="AG.N3"))
        parts.append(encode_x(a.name4 or "", max_length=35, field_name="AG.N4"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class AG03Record(EDARecord):
    ag: Antragsgegner
    fn: int

    def payload(self) -> bytes:
        a = self.ag
        ad = a.address
        parts: list[bytes] = []
        parts.append(record_header(kz="AG", fn=self.fn, tn=3))
        parts.append(encode_x(ad.strasse_hausnummer, max_length=35, field_name="AG.SH"))
        parts.append(encode_x(ad.plz, max_length=5, field_name="AG.PLZ"))
        parts.append(encode_x(ad.ort, max_length=27, field_name="AG.O"))
        parts.append(encode_x(ad.auslandskennzeichen or "", max_length=3, field_name="AG.AL"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class AG04Record(EDARecord):
    """C16 — Geburtsdatum + Erläuterungen (only natural persons)."""

    ag: Antragsgegner
    fn: int

    def payload(self) -> bytes:
        a = self.ag
        parts: list[bytes] = []
        parts.append(record_header(kz="AG", fn=self.fn, tn=4))
        parts.append(encode_datum6(a.geburtsdatum, field_name="AG.GEB"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class AG05Record(EDARecord):
    """C16A — Beruf/Funktion."""

    ag: Antragsgegner
    fn: int

    def payload(self) -> bytes:
        a = self.ag
        parts: list[bytes] = []
        parts.append(record_header(kz="AG", fn=self.fn, tn=5))
        parts.append(encode_x(a.beruf or "", max_length=35, field_name="AG.BERUF"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class AG06Record(EDARecord):
    """C16B — NATO-Truppenstatut Hinweis."""

    ag: Antragsgegner
    fn: int

    def payload(self) -> bytes:
        parts: list[bytes] = []
        parts.append(record_header(kz="AG", fn=self.fn, tn=6))
        parts.append(encode_x_gross("X" if self.ag.nato_truppenstatut else "", max_length=1, field_name="AG.NATO"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class AGGV01Record(EDARecord):
    vertreter: GesetzlicherVertreter
    ag_fn: int
    gv_fn: int

    def payload(self) -> bytes:
        v = self.vertreter
        parts: list[bytes] = []
        parts.append(record_header(kz="GG", fn=self.ag_fn, tn=self.gv_fn * 10 + 1))
        parts.append(encode_x(v.stellung, max_length=35, field_name="AGGV.FU"))
        parts.append(encode_x(v.name, max_length=35, field_name="AGGV.N"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class AGGV02Record(EDARecord):
    vertreter: GesetzlicherVertreter
    ag_fn: int
    gv_fn: int

    def payload(self) -> bytes:
        v = self.vertreter
        ad = v.address or PartyAddress(strasse_hausnummer="", plz="00000", ort="")
        parts: list[bytes] = []
        parts.append(record_header(kz="GG", fn=self.ag_fn, tn=self.gv_fn * 10 + 2))
        parts.append(encode_x(ad.strasse_hausnummer, max_length=35, field_name="AGGV.SH"))
        parts.append(encode_x(ad.plz, max_length=5, field_name="AGGV.PLZ"))
        parts.append(encode_x(ad.ort, max_length=27, field_name="AGGV.O"))
        return _pad_payload(parts)


def encode_antragsgegner_block(
    *, antragsgegner: Antragsgegner, fn: int
) -> list[EDARecord]:
    """Emit the AG_01..AG_06 + AGGV chain for one Antragsgegner."""
    records: list[EDARecord] = []
    records.append(AG01Record(ag=antragsgegner, fn=fn))
    if antragsgegner.name3 or antragsgegner.name4 or antragsgegner.rechtsform:
        records.append(AG02Record(ag=antragsgegner, fn=fn))
    records.append(AG03Record(ag=antragsgegner, fn=fn))
    if antragsgegner.geburtsdatum is not None:
        records.append(AG04Record(ag=antragsgegner, fn=fn))
    if antragsgegner.beruf:
        records.append(AG05Record(ag=antragsgegner, fn=fn))
    if antragsgegner.nato_truppenstatut:
        records.append(AG06Record(ag=antragsgegner, fn=fn))
    for gv_idx, v in enumerate(antragsgegner.vertreter, start=1):
        records.append(AGGV01Record(vertreter=v, ag_fn=fn, gv_fn=gv_idx))
        if v.address is not None:
            records.append(AGGV02Record(vertreter=v, ag_fn=fn, gv_fn=gv_idx))
    return records
