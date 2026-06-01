"""C11 ASPVAB01 — Bankverbindung Antragsteller / PV."""

from __future__ import annotations

from dataclasses import dataclass

from pyeda_mahn.contracts import Bankverbindung
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
class ASPVAB01Record(EDARecord):
    bank: Bankverbindung

    def payload(self) -> bytes:
        b = self.bank
        parts: list[bytes] = []
        parts.append(record_header(kz="BV", fn=1, tn=1))
        parts.append(encode_x_gross(b.iban, max_length=34, field_name="ASPVAB.IBAN"))
        parts.append(encode_x_gross(b.bic or "", max_length=11, field_name="ASPVAB.BIC"))
        parts.append(encode_x(b.kontoinhaber, max_length=35, field_name="ASPVAB.KTO_INH"))
        return _pad_payload(parts)


def encode_bankverbindung(bank: Bankverbindung | None) -> list[EDARecord]:
    if bank is None:
        return []
    return [ASPVAB01Record(bank=bank)]
