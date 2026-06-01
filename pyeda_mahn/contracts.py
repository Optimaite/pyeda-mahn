"""Pydantic v2 input contracts for the EDA-Mahn encoder.

The contracts deliberately do not mirror the SQLAlchemy domain shapes —
they're the encoder's typed input boundary. The driver (a future
``mahnbescheid_builder`` not in Phase A scope) maps ``Case`` + ``Party`` +
``ClaimsAccount`` rows into these models.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pyeda_mahn.errors import EDAInvariantError
from pyeda_mahn.katalog import (
    MIETE_WEG_KATALOG_CODES,
    KatalognummerEnum,
    is_valid_katalog_nr,
)

# ---------------------------------------------------------------------------
# Parties
# ---------------------------------------------------------------------------


# Anrede-Schlüssel for Antragsteller / Antragsgegner per refs/02 §"C02"
PartyAnrede = Literal[
    "0",  # Herr/Frau (divers)
    "1",  # Herr
    "2",  # Frau
    "3",  # Einzelfirma
    "4",  # GmbH & Co. KG / UG & Co. KG (Komplementär required)
    "5",  # Juristische Person sonstige (GmbH, AG, e.V., ...)
    "6",  # OHG, KG, GbR ...
    "7",  # Behörde / Anstalt
    "8",  # Inkasso-/Kreditdienstleister
    "9",  # Verbraucherzentrale
    "B",  # Wohnungseigentümergemeinschaft
]


PV_ANREDE = Literal[
    "1",  # Rechtsanwalt
    "2",  # Rechtsanwälte (mehrere namentlich)
    "3",  # Rechtsbeistand
    "4",  # Herr/Frau (eingeschränkt)
    "5",  # Rechtsanwältin
    "6",  # Rechtsanwältinnen
    "7",  # Rechtsanwaltsgemeinschaft (Vergütung nach RVG)
    "8",  # Inkasso-/Kreditdienstleister
    "9",  # Verbraucherzentrale / Verbraucherverband
]


class PartyAddress(BaseModel):
    """Anschrift block — common shape for AS, AG and PV addresses."""

    model_config = ConfigDict(frozen=True)

    strasse_hausnummer: str = Field(..., max_length=35)
    plz: str = Field(..., min_length=4, max_length=5)
    ort: str = Field(..., max_length=27)
    auslandskennzeichen: str | None = Field(default=None, max_length=3)


class GesetzlicherVertreter(BaseModel):
    """Inner gesetzlicher Vertreter (ASGV / AGGV / ASPVGV)."""

    model_config = ConfigDict(frozen=True)

    stellung: str = Field(..., max_length=35, description="e.g. 'Geschäftsführer'")
    name: str = Field(..., max_length=35, description="Vorname Nachname")
    address: PartyAddress | None = None  # Required for natural-person GV (Insolvenz-/WEG-Verwalter)


class Antragsteller(BaseModel):
    """AS-Block input (max 6 per Antrag)."""

    model_config = ConfigDict(frozen=True)

    anrede: PartyAnrede
    rechtsform: str | None = Field(default=None, max_length=35)
    name1: str = Field(..., max_length=35, description="Vorname / Antragstellerbezeichnung")
    name2: str | None = Field(default=None, max_length=35, description="Nachname / Fortsetzung")
    name3: str | None = Field(default=None, max_length=35)
    name4: str | None = Field(default=None, max_length=35)
    address: PartyAddress
    askezi: str | None = Field(
        default=None,
        min_length=8,
        max_length=8,
        description="Antragsteller-Kennziffer. When set, all AS-Stammdaten must be empty.",
    )
    vertreter: list[GesetzlicherVertreter] = Field(default_factory=list)
    # Special-case Eheleute: a single AS-block can carry a second spouse via a
    # second AS_01 Folgesatz when both share the same Nachname and the same
    # Anschrift. The bool below marks the AS block as ``Eheleute``; the
    # second spouse is provided as ``spouse_name1``.
    is_eheleute: bool = False
    spouse_name1: str | None = Field(default=None, max_length=35)


class Antragsgegner(BaseModel):
    """AG-Block input (max 5 per Antrag)."""

    model_config = ConfigDict(frozen=True)

    anrede: PartyAnrede
    rechtsform: str | None = Field(default=None, max_length=35)
    name1: str = Field(..., max_length=35)
    name2: str | None = Field(default=None, max_length=35)
    name3: str | None = Field(default=None, max_length=35)
    name4: str | None = Field(default=None, max_length=35)
    address: PartyAddress
    geburtsdatum: date | None = None
    beruf: str | None = Field(default=None, max_length=35)
    nato_truppenstatut: bool = False
    vertreter: list[GesetzlicherVertreter] = Field(default_factory=list)


class Prozessbevollmaechtigter(BaseModel):
    """ASPV-Block (Anwalt) input. Mandatory ASPVA00 in :class:`ASPVAngaben`."""

    model_config = ConfigDict(frozen=True)

    anrede: PV_ANREDE
    name: str = Field(..., max_length=105)
    rechtsform: str | None = Field(default=None, max_length=35)
    address: PartyAddress
    pvkezi: str | None = Field(default=None, min_length=8, max_length=8)
    gesetzlicher_vertreter: GesetzlicherVertreter | None = None


class Bankverbindung(BaseModel):
    """ASPVAB01 Bankverbindung."""

    model_config = ConfigDict(frozen=True)

    iban: str = Field(..., max_length=34)
    bic: str | None = Field(default=None, max_length=11)
    kontoinhaber: str = Field(..., max_length=35)


class ASPVAngaben(BaseModel):
    """ASPVA00 antragsspezifische Angaben zum PV."""

    model_config = ConfigDict(frozen=True)

    abweichendes_geschaeftszeichen: str | None = Field(default=None, max_length=35)
    beauftragung_date: date | None = None
    auslagen_betrag: Decimal | None = None
    vv2300_minderungsbetrag: Decimal | None = None
    vv2300_versicherung_umfang: bool = False
    inkasso_erstattungsbetrag: Decimal | None = None


# ---------------------------------------------------------------------------
# Ansprüche
# ---------------------------------------------------------------------------


class Zinsstaffel(BaseModel):
    """One Zinsstaffel-Zeile (max 3 pro Hauptanspruch — refs/02 hard rules)."""

    model_config = ConfigDict(frozen=True)

    von: date
    bis: date | None = None
    zinssatz_typ: Literal["statutory_consumer", "statutory_business", "contractual"] = "statutory_consumer"
    zinssatz_value_bps: int | None = None


class MieteWegZusatz(BaseModel):
    """C21 ASPZM — Lage der Wohnung for a Miet-/WEG-Anspruch (Kat. 17/19/20/90)."""

    model_config = ConfigDict(frozen=True)

    plz: str = Field(..., max_length=5)
    ort: str = Field(..., max_length=27)
    strasse_hausnummer: str | None = Field(default=None, max_length=35)
    auslandskennzeichen: str | None = Field(default=None, max_length=3)


class VertragZusatz(BaseModel):
    """C22 ASPZV — Vertragsart for a Schadenersatz-aus-Vertrag-Anspruch (Kat. 28)."""

    model_config = ConfigDict(frozen=True)

    vertragsart: str = Field(..., max_length=35, description="ohne '-vertrag', z. B. 'Kauf', 'Werk'")


class VerbraucherkreditAngabe(BaseModel):
    """C27 VKG — Verbraucherkredit § 491-504 BGB (Kat. 15/36/46)."""

    model_config = ConfigDict(frozen=True)

    vertragsdatum: date
    effektiver_jahreszins: Decimal = Field(..., description="anfänglicher effektiver Jahreszins in %, 3 Dezimalstellen")


class KatalogAnspruch(BaseModel):
    """ASPK00 record — one Hauptforderung per Katalog-Nummer."""

    model_config = ConfigDict(frozen=True)

    katalog_nr: int = Field(...)
    betrag: Decimal
    zinsstaffeln: list[Zinsstaffel] = Field(default_factory=list)
    bezeichnung: str | None = Field(default=None, max_length=70)
    miete_weg_zusatz: MieteWegZusatz | None = None  # C21
    vertrag_zusatz: VertragZusatz | None = None  # C22
    verbraucherkredit_angabe: VerbraucherkreditAngabe | None = None  # C27

    @model_validator(mode="after")
    def _validate_katalog_nr(self) -> KatalogAnspruch:
        if not is_valid_katalog_nr(self.katalog_nr):
            raise EDAInvariantError(
                invariant_name="invalid_katalog_nr",
                detail=f"Katalog-Nummer {self.katalog_nr} is not in the public catalog",
            )
        if len(self.zinsstaffeln) > 3:
            raise EDAInvariantError(
                invariant_name="zinsstaffel_3max",
                detail=f"Hauptanspruch carries {len(self.zinsstaffeln)} Zinsstaffeln; max 3",
            )
        # Miete-WEG dependency
        if self.katalog_nr in MIETE_WEG_KATALOG_CODES and self.miete_weg_zusatz is None:
            # The Mahngericht actually requires the C21 block for these
            # codes; we accept the input here but flag at the encoder level.
            pass
        return self


class SonstigerAnspruch(BaseModel):
    """ASPS00 — Sonstiger Anspruch (Freitext, max 9 pro Antrag)."""

    model_config = ConfigDict(frozen=True)

    bezeichnung_teil1: str = Field(..., max_length=105)
    bezeichnung_teil2: str | None = Field(default=None, max_length=105)
    betrag: Decimal
    zinsstaffeln: list[Zinsstaffel] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Auslagen
# ---------------------------------------------------------------------------


AuslagenKind = Literal[
    "mahnkosten",
    "auskunftskosten",
    "bankruecklast",
    "inkassokosten",
    "vorgerichtliche_rvg_2300",
    "andere_nebenforderung",
]


class Auslage(BaseModel):
    """One C28-C34 Auslagen-Block entry."""

    model_config = ConfigDict(frozen=True)

    kind: AuslagenKind
    bezeichnung: str = Field(..., max_length=70)
    betrag: Decimal
    zinsstaffeln: list[Zinsstaffel] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Kennsatz (C01)
# ---------------------------------------------------------------------------


class Mahngericht(BaseModel):
    """Mahngericht reference."""

    model_config = ConfigDict(frozen=True)

    plz: str = Field(..., min_length=4, max_length=5)
    ort: str = Field(..., max_length=30)
    safe_id: str | None = None  # only used by the send service, not the encoder


class KennsatzInput(BaseModel):
    """Top-level Kennsatz parameters (one per MBA)."""

    model_config = ConfigDict(frozen=True)

    tgz: str = Field(..., max_length=35, description="Teilnehmer-Geschäftszeichen")
    mahngericht: Mahngericht
    askezi: str | None = Field(default=None, min_length=8, max_length=8)
    pvkezi: str | None = Field(default=None, min_length=8, max_length=8)
    mggnr: str | None = Field(default=None, max_length=11)
    askstat_kostenbefreit: bool = False
    pkh_flag: bool = False  # PKH + EDA forbidden — encoder raises invariant error
    streitwert_meldung: bool = False
    aggmm: bool = False  # Anspruch-gemeinschaft Merkmal
    vgl_m1: bool = False
    vgl_m2: bool = False
    alrfmas: bool = False  # Ausländische Rechtsform Antragsteller
    alrfmag: bool = False  # Ausländische Rechtsform Antragsgegner
    astrvm: bool = False  # Antragsteller-trennung Verfahren Merkmal


# ---------------------------------------------------------------------------
# Top-level MBA input
# ---------------------------------------------------------------------------


class MahnbescheidAntragInput(BaseModel):
    """Top-level input contract for one Mahnbescheidsantrag."""

    model_config = ConfigDict(frozen=True)

    kennsatz: KennsatzInput
    antragsteller: list[Antragsteller] = Field(default_factory=list)
    prozessbevollmaechtigter: Prozessbevollmaechtigter | None = None
    aspv_angaben: ASPVAngaben | None = None
    bankverbindung: Bankverbindung | None = None
    antragsgegner: list[Antragsgegner] = Field(default_factory=list)
    katalog_ansprueche: list[KatalogAnspruch] = Field(default_factory=list)
    sonstige_ansprueche: list[SonstigerAnspruch] = Field(default_factory=list)
    auslagen: list[Auslage] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_cross_field(self) -> MahnbescheidAntragInput:
        # Hard rule 1: Kennziffer ⊕ Stammdaten exclusion (refs/02 §"Hard rules" #1)
        if self.kennsatz.askezi:
            for idx, ast in enumerate(self.antragsteller):
                if ast.askezi is not None and ast.askezi != self.kennsatz.askezi:
                    raise EDAInvariantError(
                        invariant_name="askezi_conflict",
                        detail=(
                            f"Antragsteller[{idx}].askezi={ast.askezi} conflicts "
                            f"with Kennsatz.askezi={self.kennsatz.askezi}"
                        ),
                    )

        if (
            self.kennsatz.pvkezi
            and self.prozessbevollmaechtigter is not None
            and self.prozessbevollmaechtigter.pvkezi
            and self.prozessbevollmaechtigter.pvkezi != self.kennsatz.pvkezi
        ):
            raise EDAInvariantError(
                invariant_name="pvkezi_conflict",
                detail=(
                    f"Prozessbevollmaechtigter.pvkezi conflicts with "
                    f"Kennsatz.pvkezi={self.kennsatz.pvkezi}"
                ),
            )

        # Hard rule 10: PKH + EDA verboten
        if self.kennsatz.pkh_flag:
            raise EDAInvariantError(
                invariant_name="pkh_forbidden",
                detail="Mahnbescheidsantrag mit PKH-Flag darf nicht per EDA übermittelt werden (Konditionen §2.7).",
            )

        # At least one Antragsteller (or askezi-only) and at least one Antragsgegner
        if not self.antragsteller and not self.kennsatz.askezi:
            raise EDAInvariantError(
                invariant_name="no_antragsteller",
                detail="At least one Antragsteller (or ASKEZI) required",
            )
        if not self.antragsgegner:
            raise EDAInvariantError(
                invariant_name="no_antragsgegner",
                detail="At least one Antragsgegner required",
            )
        if not self.katalog_ansprueche and not self.sonstige_ansprueche:
            raise EDAInvariantError(
                invariant_name="no_anspruch",
                detail="At least one Anspruch (Katalog or Sonstiger) required",
            )
        return self


# ---------------------------------------------------------------------------
# KEZI 25 RN — Rücknahme / Erledigterklärung
# ---------------------------------------------------------------------------


class RuecknahmeInput(BaseModel):
    """Input for a KEZI 25 Rücknahme / Erledigterklärung of a Mahnbescheid.

    The common case carries the Gerichtsnummer (``gnr``) so the court can
    match the Antrag — no Parteikurzdaten (H02) record is then required
    (``GNRM='J'``). ``tgz`` must equal the original MB-Antrag's TGZ.
    """

    model_config = ConfigDict(frozen=True)

    tkezi: str = Field(..., min_length=8, max_length=8, description="Teilnehmer-Kennziffer (PVKEZI/ASKEZI)")
    tgz: str = Field(..., max_length=35, description="Geschäftszeichen Teilnehmer (= MB-Antrag TGZ)")
    gnr: str = Field(..., min_length=1, max_length=11, description="11-digit Gerichtsnummer")
    art: Literal["ruecknahme", "erledigterklaerung"]
    mb_eingangsmerkmal: Literal["gruener_vordruck", "maschinell"] = "maschinell"


# ---------------------------------------------------------------------------
# KEZI 20 MOA — Monierungsantwort
# ---------------------------------------------------------------------------

MonierteAntragsart = Literal["mba", "vba", "vba_erneut", "nemb", "nemb_erneut", "nevb", "nevb_erneut"]


class MonierungsdatenAntwort(BaseModel):
    """One corrected data field echoed back to the court (G02 record).

    The court's Monierung lists each defective field; the answer returns the
    same field rows verbatim with only ``inhalt`` (the corrected value)
    changed. ``feldn`` + the indices + ``form`` mirror the court's record.
    """

    model_config = ConfigDict(frozen=True)

    fschl: int = Field(..., ge=0, description="Fehlerschlüssel (court code)")
    feldn: str = Field(..., max_length=20, description="gerichtsinterne Feld-Referenz")
    index1: int = Field(default=0, ge=0)
    index2: int = Field(default=0, ge=0)
    mas: int = Field(default=1, ge=1, le=4, description="Seite der Papier-Monierungsantwort")
    maz: int = Field(default=1, ge=1, le=5, description="Zeile")
    mazpos: int = Field(default=1, ge=1, le=2, description="1=linke, 2=rechte Halbzeile")
    form: str = Field(default="1", max_length=1, description="Feldformat code 1-8")
    inhalt: str = Field(..., max_length=35, description="corrected value")


class MonierungsantwortInput(BaseModel):
    """Input for a KEZI 20 Monierungsantwort (response to a court Monierung)."""

    model_config = ConfigDict(frozen=True)

    tkezi: str = Field(..., min_length=8, max_length=8)
    tgz: str = Field(..., max_length=35, description="Geschäftszeichen Teilnehmer")
    gnrs: list[str] = Field(..., min_length=1, max_length=5, description="1-5 Gerichtsnummern (first always set)")
    antwort_datum: date = Field(..., description="MOD — EDA-Teilnehmer Erstellungsdatum")
    monierter_antrag_datum: date = Field(..., description="AND — date of the monierter Antrag")
    monierte_antragsart: MonierteAntragsart
    daten: list[MonierungsdatenAntwort] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# KEZI 07 NEMB / KEZI 10 NEVB — Neuzustellungsantrag (MB / VB)
# ---------------------------------------------------------------------------


class NeuzustellungAntragsgegner(BaseModel):
    """Corrected Antragsgegner for a Neuzustellung (re-service) request."""

    model_config = ConfigDict(frozen=True)

    anrede: PartyAnrede
    name1: str = Field(..., max_length=35)
    name2: str | None = Field(default=None, max_length=35)
    name3: str | None = Field(default=None, max_length=35)
    rechtsform: str | None = Field(default=None, max_length=35)
    strasse_hausnummer: str = Field(..., max_length=35)
    plz: str = Field(..., max_length=5)
    ort: str = Field(..., max_length=27)
    auslandskennzeichen: str | None = Field(default=None, max_length=3)


class NeuzustellungInput(BaseModel):
    """Input for a KEZI 07 NEMB / KEZI 10 NEVB Neuzustellungsantrag.

    Re-service of a Mahnbescheid (NEMB) or Vollstreckungsbescheid (NEVB),
    usually after a failed delivery. When ``antragsgegner`` is given the
    document is re-served to the corrected address; otherwise re-service goes
    to the address already on file at the court.
    """

    model_config = ConfigDict(frozen=True)

    tkezi: str = Field(..., min_length=8, max_length=8)
    gnr: str = Field(..., min_length=1, max_length=11)
    tgz: str = Field(..., max_length=35, description="Geschäftszeichen AS/ASPV")
    antragsgegner: NeuzustellungAntragsgegner | None = None
    porto_telefon: Decimal | None = Field(default=None, description="PTBET — Porto/Telefon")
    sonstige_kosten: Decimal | None = Field(default=None, description="NMSKOBET")
    sonstige_kosten_begruendung: str | None = Field(default=None, max_length=35)
    auskunftskosten: Decimal | None = Field(default=None, description="NMAUSK")


# ---------------------------------------------------------------------------
# KEZI 29 EZKOAB — Antrag Kosteneinzug nach Widerspruch / Abgabeantrag
# ---------------------------------------------------------------------------


class KostenAbgabeAntragInput(BaseModel):
    """Input for a KEZI 29 Antrag auf Kosteneinzug nach Widerspruch / Abgabe.

    After a Widerspruch, requests that the Widerspruchs-Kosten be collected and
    the Verfahren handed to the Prozessgericht for the streitige Verfahren. The
    SEPA fields were retired in 2014 (Lastschriftmandat must be on paper), so
    the record is just GNR + TGZ + the fixed Einzugs-/Abgabe-Merkmal.
    """

    model_config = ConfigDict(frozen=True)

    tkezi: str = Field(..., min_length=8, max_length=8)
    gnr: str = Field(..., min_length=1, max_length=11)
    tgz: str = Field(..., max_length=35, description="Geschäftszeichen Teilnehmer")


# ---------------------------------------------------------------------------
# KEZI 30 WI — Widerspruch
# ---------------------------------------------------------------------------


class WiderspruchInput(BaseModel):
    """Input for a KEZI 30 Widerspruch against a Mahnbescheid.

    In Kennziffer-EDA the Widerspruch is **only for the Antragsgegner's
    Prozessbevollmächtigter** (the firm representing the *debtor*); the
    Kennziffer's 3rd digit must be 5-7 (a PVKEZI). A Gesamtwiderspruch needs
    only ``gnr`` + ``tgz``; a Teilwiderspruch additionally specifies which
    parts are contested.
    """

    model_config = ConfigDict(frozen=True)

    agpv_kezi: str = Field(..., min_length=8, max_length=8, description="AGPV-Kennziffer (debtor's PV)")
    gnr: str = Field(..., min_length=1, max_length=11)
    tgz: str = Field(..., max_length=35, description="Geschäftszeichen des AGPV (AGGZ)")
    umfang: Literal["gesamt", "teil"] = "gesamt"
    # Teilwiderspruch (umfang='teil') only:
    widersprochener_hauptbetrag: Decimal | None = Field(default=None, description="WIHFBET")
    widerspruch_zinsen: bool = Field(default=False, description="WIZIM — gegen Zinsen insgesamt")
    widerspruch_verfahrenskosten: bool = Field(default=False, description="WIVKOM")
    widersprochene_nebenforderung: Decimal | None = Field(default=None, description="WINEBBET")


# ---------------------------------------------------------------------------
# KEZI 08 VBA — Vollstreckungsbescheidsantrag
# ---------------------------------------------------------------------------


class VbZahlung(BaseModel):
    """One payment the Antragsgegner made after the Mahnbescheid (E02)."""

    model_config = ConfigDict(frozen=True)

    datum: date
    betrag: Decimal


class VollstreckungsbescheidInput(BaseModel):
    """Input for a KEZI 08 Vollstreckungsbescheidsantrag.

    Filed after the Mahnbescheid was served and the Widerspruchsfrist lapsed
    without (full) Widerspruch. References the same Gerichtsnummer. When the
    Antragsgegner made partial payments they are listed in ``zahlungen`` and
    the court reduces the title accordingly (VBZAM='2' → E02 Satz).
    """

    model_config = ConfigDict(frozen=True)

    tkezi: str = Field(..., min_length=8, max_length=8)
    gnr: str = Field(..., min_length=1, max_length=11)
    tgz: str = Field(..., max_length=30, description="Geschäftszeichen Teilnehmer (30 bytes)")
    antragstellung_datum: date = Field(..., description="VBAND")
    zustellung: Literal["durch_gericht", "parteibetrieb"] = "durch_gericht"
    zahlungen: list[VbZahlung] = Field(default_factory=list, max_length=6)
    porto_telefon: Decimal | None = Field(default=None, description="VBPTBET")
    sonstige_kosten: Decimal | None = Field(default=None, description="VBSKOBET")
    sonstige_kosten_begruendung: str | None = Field(default=None, max_length=35)
    zinsen_auf_kosten: bool = Field(default=False, description="KOZIM — Zinsen § 104 ZPO auf Kosten")
    aspv_auslagen: Decimal | None = Field(
        default=None,
        description="ASPVAUSL — None=Pauschale 7002 VV; 0=Verzicht; >0=abweichender Betrag",
    )
    antragsgegner: NeuzustellungAntragsgegner | None = None


# Convenience re-exports
__all__ = [
    "PV_ANREDE",
    "ASPVAngaben",
    "Antragsgegner",
    "Antragsteller",
    "Auslage",
    "AuslagenKind",
    "Bankverbindung",
    "GesetzlicherVertreter",
    "KatalogAnspruch",
    "KatalognummerEnum",
    "KennsatzInput",
    "KostenAbgabeAntragInput",
    "MahnbescheidAntragInput",
    "MieteWegZusatz",
    "VerbraucherkreditAngabe",
    "VertragZusatz",
    "Mahngericht",
    "MonierteAntragsart",
    "MonierungsantwortInput",
    "MonierungsdatenAntwort",
    "NeuzustellungAntragsgegner",
    "NeuzustellungInput",
    "PartyAddress",
    "PartyAnrede",
    "Prozessbevollmaechtigter",
    "RuecknahmeInput",
    "SonstigerAnspruch",
    "VbZahlung",
    "VollstreckungsbescheidInput",
    "WiderspruchInput",
    "Zinsstaffel",
]
