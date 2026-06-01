"""KEZI 01 — Mahnbescheidsantrag (MBA) Satzfolge encoders.

The submodules implement the per-record encoders. The top-level
:func:`encode_mahnbescheidsantrag` driver in :mod:`.encoder` assembles them
in the mandatory order described in
``refs/02_KEZI_01_MBA_Satzfolge.md`` § "Record-type chain".
"""

from __future__ import annotations

from pyeda_mahn.format.kezi_01_mba.encoder import (
    encode_mahnbescheidsantrag,
)

__all__ = ["encode_mahnbescheidsantrag"]
