"""KEZI 07 — Neuzustellungsantrag Mahnbescheid encoder."""

from __future__ import annotations

from datetime import datetime

from pyeda_mahn.contracts import NeuzustellungInput
from pyeda_mahn.format.kezi_07_nemb.encoder import encode_neuzustellung


def encode_neuzustellung_mb(
    nz: NeuzustellungInput,
    *,
    file_when: datetime | None = None,
    edaid: str | None = None,
) -> bytes:
    """Encode a KEZI 07 Neuzustellungsantrag zum Mahnbescheid."""
    return encode_neuzustellung(nz, belart="07", file_when=file_when, edaid=edaid)


__all__ = ["encode_neuzustellung", "encode_neuzustellung_mb"]
