"""Anspruchskatalog — `KatalognummerEnum` derived from refs/04.

Source of truth: ``refs/04_Anspruchskatalog_Katalognummern.md``. Codes 47-60,
62-69, 71-74, 81-89, 91-94 are reserved (not in the public catalog as of
2026-05-26). Duplicates are intentional — see refs/04 § "Encoder
implications" note 2.
"""

from __future__ import annotations

from enum import IntEnum


class KatalognummerEnum(IntEnum):
    """All 55 published Hauptforderungs-Katalog-Nummern.

    Some codes carry duplicate human labels; their downstream routing at the
    Mahngericht differs (Verbraucher vs Unternehmer context), so we keep
    them as separate enum members.
    """

    ANZEIGEN_IN_ZEITUNGEN_U_A = 1
    AERZTLICHE_LEISTUNG = 2
    BUERGSCHAFT = 3
    DARLEHENSRUECKZAHLUNG = 4
    DIENSTLEISTUNGSVERTRAG = 5
    FRACHTKOSTEN = 6
    GESCHAEFTSBESORGUNG = 7
    HANDWERKERLEISTUNG = 8
    HEIMUNTERBRINGUNG = 9
    HOTELKOSTEN = 10
    KAUFVERTRAG = 11
    KINDERTAGESSTAETTENBEITRAG = 12
    KONTOKORRENTABRECHNUNG = 13
    KRANKENHAUSKOSTEN = 14
    KRANKENTRANSPORTKOSTEN = 15
    LAGERKOSTEN = 16
    LEASING_MIETKAUF = 17
    LEHRGANGSKOSTEN = 18
    MIETE_GESCHAEFTSRAUM = 19
    MIETE_KFZ = 20
    MIETE_WOHNRAUM = 21
    MIETNEBENKOSTEN = 22
    MIETE_SONSTIGE = 23
    MITGLIEDSBEITRAG = 24
    PACHT = 25
    RECHTSANWALTSHONORAR = 26
    REISEVERTRAG = 27
    REPARATURLEISTUNG = 28
    RUECKGRIFF_BUERGSCHAFT = 29
    RUECKGRIFF_VERSICHERUNG = 30
    SCHECK_WECHSEL = 31
    SCHECK_PROVISION = 32
    SCHECK_UNKOSTEN = 33
    SCHULDANERKENNTNIS = 34
    SPEDITIONSKOSTEN = 35
    TELEKOMMUNIKATIONSLEISTUNGEN = 36
    TIERAERZTLICHE_LEISTUNG = 37
    TILGUNGS_ZINSRATEN = 38
    UEBERZIEHUNG_BANKKONTO = 39
    UNGERECHTFERTIGTE_BEREICHERUNG = 40
    UNTERHALTSRUECKSTAENDE = 41
    VERGLEICH_AUSSERGERICHTLICH = 42
    VERMITTLUNG_MAKLERPROVISION = 43
    VERPFLEGUNGSKOSTEN = 44
    VERSICHERUNGSPRAEMIE = 45
    VERSORGUNGSLEISTUNG = 46
    WAHLLEISTUNGEN_STAT_BEHANDLUNG = 61
    KINDERTAGESSTAETTENBEITRAG_70 = 70
    REISEVERTRAG_75 = 75
    TIERAERZTLICHE_LEISTUNG_76 = 76
    LAGERKOSTEN_77 = 77
    TILGUNGS_ZINSRATEN_78 = 78
    VERPFLEGUNGSKOSTEN_79 = 79
    RUECKGRIFF_VERSICHERUNG_80 = 80
    WOHNGELD_HAUSGELD = 90
    PFLEGEVERSICHERUNG_BEITRAEGE = 95


VALID_KATALOG_VALUES: frozenset[int] = frozenset(int(m) for m in KatalognummerEnum)


# Codes requiring the C21 Miete/WEG Zusatzangabe block per refs/04 § note 5.
MIETE_WEG_KATALOG_CODES: frozenset[int] = frozenset(
    {
        KatalognummerEnum.MIETE_GESCHAEFTSRAUM,
        KatalognummerEnum.MIETE_KFZ,
        KatalognummerEnum.MIETE_WOHNRAUM,
        KatalognummerEnum.MIETNEBENKOSTEN,
        KatalognummerEnum.MIETE_SONSTIGE,
        KatalognummerEnum.WOHNGELD_HAUSGELD,
    }
)


def is_valid_katalog_nr(value: int) -> bool:
    return value in VALID_KATALOG_VALUES
