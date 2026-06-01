"""Kennziffer (Antragsteller-/PV-/Einreicher-Kennziffer) helpers.

A Kennziffer is 8 digits:

  * Pos. 1-2 = Bundesland-Merkmal (refs/01 §4 table — `01,02,03,04,05,06,07,08,09,11,23`)
  * Pos. 3-7 = laufende Nummer (assigned per role, refs/01 §4 Kennziffer-Arten)
  * Pos. 8   = Prüfziffer (modulo-10 check digit)

The Konditionen PDF references "the modulo-10 check digit algorithm in the
published software examples", not in the Konditionen itself. We implement a
canonical modulo-10-by-position-weight algorithm here:

    chk = (Σ digit_i * i) mod 10  with i = 1..7   then  Prüfziffer = (10 - chk) mod 10

This matches the family of weighted modulo-10 checks used by EDA-similar
behördliche Kennziffern (e.g. DEMV, IBAN-Konto-Prüf). Live cross-check
against IuK-FZ-Stuttgart examples is still pending.
"""

from __future__ import annotations

import re

from pyeda_mahn.errors import EDAInvariantError

ALLOWED_BUNDESLAND_MERKMALE: frozenset[str] = frozenset(
    {"01", "02", "03", "04", "05", "06", "07", "08", "09", "11", "23"}
)

PVKEZI_LAUFENDE_NR_MIN = 50000
PVKEZI_LAUFENDE_NR_MAX = 79999


_PVKEZI_RE = re.compile(r"^\d{8}$")


def compute_pruefziffer(bundesland: str, laufende_nummer: int) -> int:
    """Compute the Prüfziffer for a Kennziffer with given Bundesland + lfd. Nr.

    Implements ``(10 - (Σ digit_i * i) mod 10) mod 10`` over positions 1-7
    (Bundesland 2 digits + laufende Nummer 5 digits = 7 positions).

    NOTE: The canonical algorithm is published in IuK-FZ Stuttgart examples,
    not in the Konditionen PDF. This implementation matches the documented
    weighting pattern; live cross-check pending against a real PVKEZI.
    """
    if bundesland not in ALLOWED_BUNDESLAND_MERKMALE:
        raise EDAInvariantError(
            invariant_name="invalid_bundesland_merkmal",
            detail=f"{bundesland!r} not in {sorted(ALLOWED_BUNDESLAND_MERKMALE)!r}",
        )
    if not (0 <= laufende_nummer <= 99999):
        raise EDAInvariantError(
            invariant_name="laufende_nummer_range",
            detail=f"laufende_nummer {laufende_nummer} out of 0..99999",
        )
    digits = bundesland + f"{laufende_nummer:05d}"
    weighted = sum(int(d) * (idx + 1) for idx, d in enumerate(digits))
    return (10 - (weighted % 10)) % 10


def validate_pvkezi(pvkezi: str) -> bool:
    """Validate an 8-digit PVKEZI string per refs/01 §4.

    Returns ``True`` on a structurally valid PVKEZI within the
    50000-79999 lfd-Nr range and an allowed Bundesland-Merkmal. The
    Prüfziffer is computed and compared.

    Does not raise — for use in admin UI form gating.
    """
    if not isinstance(pvkezi, str) or not _PVKEZI_RE.match(pvkezi):
        return False
    bundesland = pvkezi[:2]
    if bundesland not in ALLOWED_BUNDESLAND_MERKMALE:
        return False
    laufende_nr = int(pvkezi[2:7])
    if not (PVKEZI_LAUFENDE_NR_MIN <= laufende_nr <= PVKEZI_LAUFENDE_NR_MAX):
        return False
    expected = compute_pruefziffer(bundesland=bundesland, laufende_nummer=laufende_nr)
    return int(pvkezi[7]) == expected
