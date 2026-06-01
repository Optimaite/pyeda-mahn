"""KEZI 10 — Neuzustellungsantrag Vollstreckungsbescheid encoder.

Shares the record layout with KEZI 07 NEMB; only the AA BELART differs (``10``).
"""

from __future__ import annotations

from datetime import datetime

from pyeda_mahn.contracts import NeuzustellungInput
from pyeda_mahn.format.kezi_07_nemb.encoder import encode_neuzustellung


def encode_neuzustellung_vb(
    nz: NeuzustellungInput,
    *,
    file_when: datetime | None = None,
    edaid: str | None = None,
) -> bytes:
    """Encode a KEZI 10 Neuzustellungsantrag zum Vollstreckungsbescheid."""
    return encode_neuzustellung(nz, belart="10", file_when=file_when, edaid=edaid)


__all__ = ["encode_neuzustellung_vb"]
