"""Top-level driver — :func:`encode_mahnbescheidsantrag`.

Builds the full ``.eda`` byte stream from a validated
:class:`MahnbescheidAntragInput`. Enforces:

* the 11 §2.6.1.1 Aussteuerungs-Caps (Konditionen)
* refs/02 §"Hard rules" (Kennziffer ⊕ Stammdaten + PKH ✗ EDA + Zinsstaffel
  ≤ 3 + record order)
* charset/length per :mod:`format.record`

The output is a single physical file containing one logical file:
``AA`` … one ``01 Kennsatz`` chain … ``BB``. Multi-Antrag batches share the
same AA/BB envelope; the kontrollsummen accumulate accordingly.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from pyeda_mahn.contracts import (
    MahnbescheidAntragInput,
)
from pyeda_mahn.errors import EDAAussteuerungError, EDAInvariantError
from pyeda_mahn.format.aa_satz import (
    AAVorsatz,
    build_edaid,
    encode_aa,
)
from pyeda_mahn.format.bb_satz import (
    BBNachsatz,
    compute_mba_control_totals,
    encode_bb,
)
from pyeda_mahn.format.kezi_01_mba.anspruch import (
    encode_katalog_anspruch,
    encode_sonstiger_anspruch,
)
from pyeda_mahn.format.kezi_01_mba.antragsgegner import (
    encode_antragsgegner_block,
)
from pyeda_mahn.format.kezi_01_mba.antragsteller import (
    encode_antragsteller_block,
)
from pyeda_mahn.format.kezi_01_mba.auslagen import (
    encode_auslagen_block,
)
from pyeda_mahn.format.kezi_01_mba.bankverbindung import (
    encode_bankverbindung,
)
from pyeda_mahn.format.kezi_01_mba.kennsatz import KennsatzRecord
from pyeda_mahn.format.kezi_01_mba.prozessbevollmaechtigter import (
    encode_pv_block,
)
from pyeda_mahn.format.record import EDARecord, concat_records

# Konditionen §2.6.1.1 Aussteuerungs-Caps (refs/01)
AUSSTEUERUNG_CAPS: dict[str, int] = {
    "max_antragsteller": 6,
    "max_gesetzlicher_vertreter_per_as": 6,
    "max_antragsgegner": 5,
    "max_katalog_ansprueche": 45,
    "max_miete_weg_zusaetze": 4,
    "max_vertrag_zusaetze": 4,
    "max_sonstige_ansprueche": 9,
    "max_abtretungen": 4,
    "max_verbraucherkredit_angaben": 10,
    "max_zinsangaben": 54,
    "max_andere_nebenforderungen": 5,
}


def _check_aussteuerung(mba: MahnbescheidAntragInput) -> None:
    """Enforce the 11 Aussteuerungs-Caps."""
    caps = AUSSTEUERUNG_CAPS

    if len(mba.antragsteller) > caps["max_antragsteller"]:
        raise EDAAussteuerungError(
            limit_name="max_antragsteller",
            value=len(mba.antragsteller),
            max_value=caps["max_antragsteller"],
        )
    for ast in mba.antragsteller:
        if len(ast.vertreter) > caps["max_gesetzlicher_vertreter_per_as"]:
            raise EDAAussteuerungError(
                limit_name="max_gesetzlicher_vertreter_per_as",
                value=len(ast.vertreter),
                max_value=caps["max_gesetzlicher_vertreter_per_as"],
            )
    if len(mba.antragsgegner) > caps["max_antragsgegner"]:
        raise EDAAussteuerungError(
            limit_name="max_antragsgegner",
            value=len(mba.antragsgegner),
            max_value=caps["max_antragsgegner"],
        )
    if len(mba.katalog_ansprueche) > caps["max_katalog_ansprueche"]:
        raise EDAAussteuerungError(
            limit_name="max_katalog_ansprueche",
            value=len(mba.katalog_ansprueche),
            max_value=caps["max_katalog_ansprueche"],
        )
    miete_weg = sum(
        1 for a in mba.katalog_ansprueche if a.miete_weg_zusatz is not None
    )
    if miete_weg > caps["max_miete_weg_zusaetze"]:
        raise EDAAussteuerungError(
            limit_name="max_miete_weg_zusaetze",
            value=miete_weg,
            max_value=caps["max_miete_weg_zusaetze"],
        )
    vertrag_z = sum(
        1 for a in mba.katalog_ansprueche if a.vertrag_zusatz is not None
    )
    if vertrag_z > caps["max_vertrag_zusaetze"]:
        raise EDAAussteuerungError(
            limit_name="max_vertrag_zusaetze",
            value=vertrag_z,
            max_value=caps["max_vertrag_zusaetze"],
        )
    if len(mba.sonstige_ansprueche) > caps["max_sonstige_ansprueche"]:
        raise EDAAussteuerungError(
            limit_name="max_sonstige_ansprueche",
            value=len(mba.sonstige_ansprueche),
            max_value=caps["max_sonstige_ansprueche"],
        )
    vk = sum(
        1 for a in mba.katalog_ansprueche if a.verbraucherkredit_angabe is not None
    )
    if vk > caps["max_verbraucherkredit_angaben"]:
        raise EDAAussteuerungError(
            limit_name="max_verbraucherkredit_angaben",
            value=vk,
            max_value=caps["max_verbraucherkredit_angaben"],
        )
    zinszeilen = sum(len(a.zinsstaffeln) for a in mba.katalog_ansprueche)
    if zinszeilen > caps["max_zinsangaben"]:
        raise EDAAussteuerungError(
            limit_name="max_zinsangaben",
            value=zinszeilen,
            max_value=caps["max_zinsangaben"],
        )
    andere_nf = sum(
        1 for a in mba.auslagen if a.kind == "andere_nebenforderung"
    )
    if andere_nf > caps["max_andere_nebenforderungen"]:
        raise EDAAussteuerungError(
            limit_name="max_andere_nebenforderungen",
            value=andere_nf,
            max_value=caps["max_andere_nebenforderungen"],
        )

    # Zinsstaffel ≤ 3 per Hauptanspruch is already enforced by the contract,
    # but check again here for safety.
    for idx, anspruch in enumerate(mba.katalog_ansprueche):
        if len(anspruch.zinsstaffeln) > 3:
            raise EDAInvariantError(
                invariant_name="zinsstaffel_3max",
                detail=f"Hauptanspruch[{idx}] has {len(anspruch.zinsstaffeln)} Zinsstaffeln; max 3",
            )


def _assemble_body(mba: MahnbescheidAntragInput) -> list[EDARecord]:
    """Build the ordered MBA body record list (no AA/BB)."""

    records: list[EDARecord] = []
    records.append(KennsatzRecord(kennsatz=mba.kennsatz))

    # AS-blocks (skip Stammdaten when ASKEZI is set per refs/02 hard rule #1)
    if not mba.kennsatz.askezi:
        for as_idx, ast in enumerate(mba.antragsteller, start=1):
            records.extend(encode_antragsteller_block(antragsteller=ast, fn=as_idx))

    # PV-block: ASPV01..ASPV03 only when no PVKEZI; ASPVA00 always when given.
    records.extend(
        encode_pv_block(
            pv=mba.prozessbevollmaechtigter,
            angaben=mba.aspv_angaben,
        )
    )

    # Bankverbindung
    records.extend(encode_bankverbindung(mba.bankverbindung))

    # AG blocks
    for ag_idx, ag in enumerate(mba.antragsgegner, start=1):
        records.extend(encode_antragsgegner_block(antragsgegner=ag, fn=ag_idx))

    # Anspruch-blocks
    for ha_idx, ha in enumerate(mba.katalog_ansprueche, start=1):
        records.extend(encode_katalog_anspruch(anspruch=ha, fn=ha_idx))
    for s_idx, so in enumerate(mba.sonstige_ansprueche, start=1):
        # Sonstige fn continues numbering after Katalog
        records.extend(encode_sonstiger_anspruch(anspruch=so, fn=len(mba.katalog_ansprueche) + s_idx))

    # Auslagen
    records.extend(encode_auslagen_block(mba.auslagen))

    return records


def encode_mahnbescheidsantrag(
    mba: MahnbescheidAntragInput,
    *,
    file_when: datetime | None = None,
    edaid: str | None = None,
    ekezi: str | None = None,
) -> bytes:
    """Encode one Mahnbescheidsantrag into the full ``.eda`` byte stream.

    Phase A — single-Antrag per file. ``file_when`` controls AA-Satz DATUM
    and the EDAID derivation; defaults to ``datetime.utcnow()``.
    """
    # 1. Fail-closed validation
    _check_aussteuerung(mba)

    # 2. Resolve TKEZI for the AA-Satz.
    # Hierarchy: PVKEZI (Kennsatz) → ASKEZI (Kennsatz) → fallback "00000000".
    # Konditionen §4.1 — TKEZI is whichever Kennziffer the Teilnehmer uses to
    # authenticate to the Mahngericht.
    tkezi = mba.kennsatz.pvkezi or mba.kennsatz.askezi or "00000000"

    when = file_when or datetime.now(UTC)
    edaid_final = edaid or build_edaid(when=when, seq=1)

    aa = AAVorsatz(
        tkezi=tkezi,
        file_date=when.date(),
        belart="01",
        ekezi=ekezi,
        edaid=edaid_final,
    )
    aa_bytes = encode_aa(aa)

    # 3. Assemble body
    body_records = _assemble_body(mba)
    body_bytes = concat_records(body_records)
    record_count = len(body_records)

    # 4. Compute Kontrollsummen
    totals = compute_mba_control_totals(
        record_count=record_count,
        antrag_count=1,
        katalog_nrn=(int(a.katalog_nr) for a in mba.katalog_ansprueche),
        anspruchsbetraege=(a.betrag for a in mba.katalog_ansprueche),
        hauptansprueche_per_antrag=[len(mba.katalog_ansprueche)],
    )
    bb = BBNachsatz(
        record_count=totals.record_count,
        antrag_count=totals.antrag_count,
        sum_katalog_nrn=totals.sum_katalog_nrn,
        sum_anspruchsbetraege_cents=totals.sum_anspruchsbetraege_cents,
        sum_hauptansprueche_count=totals.sum_hauptansprueche_count,
    )
    bb_bytes = encode_bb(bb)

    return aa_bytes + body_bytes + bb_bytes


def iter_records_for_debug(mba: MahnbescheidAntragInput) -> Iterable[EDARecord]:
    """Helper for tests: yield the MBA body record list (no AA/BB)."""
    yield from _assemble_body(mba)
