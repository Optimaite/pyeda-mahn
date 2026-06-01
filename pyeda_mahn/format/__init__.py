"""EDA fixed-width record + AA/BB Satz primitives + KEZI parsers (spec 367).

The 128-byte record discipline lives in :mod:`record`. AA Dateivorsatz and
BB Dateinachsatz live in :mod:`aa_satz` and :mod:`bb_satz` respectively. The
MBA chain lives under :mod:`kezi_01_mba`. Inbound parsers (KEZI 05, 90) sit
next to each other for symmetry.
"""

from __future__ import annotations
