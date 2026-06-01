"""C01 KS — Kennsatz record."""

from __future__ import annotations

from dataclasses import dataclass

from pyeda_mahn.contracts import KennsatzInput
from pyeda_mahn.format.kezi_01_mba._common import record_header
from pyeda_mahn.format.record import (
    EDARecord,
    encode_blank,
    encode_n_b,
    encode_x,
)


@dataclass(frozen=True)
class KennsatzRecord(EDARecord):
    kennsatz: KennsatzInput

    def payload(self) -> bytes:
        k = self.kennsatz
        parts: list[bytes] = []
        parts.append(record_header(kz="KS", fn=1, tn=1))
        # TGZ - Teilnehmer-Geschäftszeichen 35 X
        parts.append(encode_x(k.tgz, max_length=35, field_name="KS.TGZ"))
        # ASKEZI 8 N/B
        parts.append(encode_n_b(k.askezi, max_length=8, field_name="KS.ASKEZI"))
        # PVKEZI 8 N/B
        parts.append(encode_n_b(k.pvkezi, max_length=8, field_name="KS.PVKEZI"))
        # MGPLZ 5 X
        parts.append(encode_x(k.mahngericht.plz, max_length=5, field_name="KS.MGPLZ"))
        # MGO 30 X
        parts.append(encode_x(k.mahngericht.ort, max_length=30, field_name="KS.MGO"))
        # MGGNR 11 X/B
        parts.append(encode_x(k.mggnr or "", max_length=11, field_name="KS.MGGNR"))
        # Flag set: ASKSTAT, PKH, SWUM, AGGMM, VGLM1, VGLM2, ALRFMAS, ALRFMAG, ASTRVM
        # — encoded as ASCII X/" " bytes per refs/02 §C01.
        for name, flag in [
            ("ASKSTAT", k.askstat_kostenbefreit),
            ("PKHM", k.pkh_flag),
            ("SWUM", k.streitwert_meldung),
            ("AGGMM", k.aggmm),
            ("VGLM1", k.vgl_m1),
            ("VGLM2", k.vgl_m2),
            ("ALRFMAS", k.alrfmas),
            ("ALRFMAG", k.alrfmag),
            ("ASTRVM", k.astrvm),
        ]:
            parts.append(encode_x("X" if flag else "", max_length=1, field_name=f"KS.{name}"))
        # Filler to fill payload (125 bytes).
        used = sum(len(p) for p in parts)
        if used < 125:
            parts.append(encode_blank(max_length=125 - used))
        return b"".join(parts)
