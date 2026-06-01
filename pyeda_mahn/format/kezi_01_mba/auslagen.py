"""C28-C34 — Auslagen records (MK, AUSK, BKR, IK, RVG, NK).

Phase A encodes each Auslage as one record per kind via a shared layout —
all six kinds share the same on-wire shape (Bezeichnung 70 X + Betrag 12
N(2) + optional Zinsstaffel-Belege via parent_fn).
"""

from __future__ import annotations

from dataclasses import dataclass

from pyeda_mahn.contracts import Auslage, AuslagenKind
from pyeda_mahn.format.kezi_01_mba._common import record_header
from pyeda_mahn.format.record import (
    EDARecord,
    encode_betrag,
    encode_blank,
    encode_x,
)

KIND_TO_KZ: dict[AuslagenKind, str] = {
    "mahnkosten": "MK",
    "auskunftskosten": "AK",
    "bankruecklast": "BR",
    "inkassokosten": "IK",
    "vorgerichtliche_rvg_2300": "RV",
    "andere_nebenforderung": "NK",
}


def _pad_payload(parts: list[bytes]) -> bytes:
    used = sum(len(p) for p in parts)
    if used < 125:
        parts.append(encode_blank(max_length=125 - used))
    return b"".join(parts)


@dataclass(frozen=True)
class AuslageRecord(EDARecord):
    auslage: Auslage
    fn: int

    def payload(self) -> bytes:
        a = self.auslage
        kz = KIND_TO_KZ[a.kind]
        parts: list[bytes] = []
        parts.append(record_header(kz=kz, fn=self.fn, tn=1))
        parts.append(encode_betrag(a.betrag, max_length=12, field_name=f"AUS.{kz}.BETRAG"))
        parts.append(encode_x(a.bezeichnung, max_length=70, field_name=f"AUS.{kz}.BEZ"))
        return _pad_payload(parts)


def encode_auslagen_block(auslagen: list[Auslage]) -> list[EDARecord]:
    out: list[EDARecord] = []
    for idx, a in enumerate(auslagen, start=1):
        out.append(AuslageRecord(auslage=a, fn=idx))
    return out
