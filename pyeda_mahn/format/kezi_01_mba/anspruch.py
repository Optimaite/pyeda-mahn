"""C20-C27 — Anspruch records (ASPK00, ASPS00, ASPZ, Zusätze, ...).

Supports:
  * ASPK00 (Katalog-Anspruch) — refs/02 §C20
  * ASPZM / ASPZV — Miete/WEG (C21) and Vertrag (C22) Zusatzangaben
  * ASPS00 (Sonstiger Anspruch) — refs/02 §C23/C24
  * ASPZ (laufende Zinsen) — refs/02 §C26 — embedded in the Hauptanspruch's
    Zinsstaffel list
  * VKG (Verbraucherkredit, C27)

Records are emitted in the documented order (C20 §c): Miete/WEG → Vertrag →
Zinsen → Verbraucherkredit. Pending live Mahngericht Testdurchgang pinning.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyeda_mahn.contracts import (
    KatalogAnspruch,
    MieteWegZusatz,
    SonstigerAnspruch,
    VerbraucherkreditAngabe,
    VertragZusatz,
    Zinsstaffel,
)
from pyeda_mahn.format.kezi_01_mba._common import record_header
from pyeda_mahn.format.record import (
    EDARecord,
    encode_betrag,
    encode_blank,
    encode_datum6,
    encode_n,
    encode_n_b,
    encode_x,
)


def _pad_payload(parts: list[bytes]) -> bytes:
    used = sum(len(p) for p in parts)
    if used < 125:
        parts.append(encode_blank(max_length=125 - used))
    return b"".join(parts)


@dataclass(frozen=True)
class ASPK00Record(EDARecord):
    """C20 ASPK00 — Anspruch nach Katalog."""

    anspruch: KatalogAnspruch
    fn: int  # 1-based Hauptanspruch position

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        a = self.anspruch
        parts: list[bytes] = []
        parts.append(record_header(kz="HA", fn=self.fn, tn=1))
        parts.append(encode_n(int(a.katalog_nr), max_length=3, field_name="ASPK.KATALOG"))
        parts.append(encode_betrag(a.betrag, max_length=12, field_name="ASPK.BETRAG"))
        parts.append(encode_x(a.bezeichnung or "", max_length=70, field_name="ASPK.BEZ"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class ASPZRecord(EDARecord):
    """C26 ASPZ — laufende Zinsen (one row per Zinsstaffel)."""

    staffel: Zinsstaffel
    parent_fn: int
    tn: int  # 1-based row within Hauptanspruch (max 3)

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        s = self.staffel
        parts: list[bytes] = []
        parts.append(record_header(kz="HZ", fn=self.parent_fn, tn=self.tn))
        parts.append(encode_datum6(s.von, field_name="ASPZ.VON"))
        parts.append(encode_datum6(s.bis, field_name="ASPZ.BIS"))
        # ZinssatzTyp encoded as 1 char: C = consumer, B = business, V = vertraglich
        typ_char = {"statutory_consumer": "C", "statutory_business": "B", "contractual": "V"}.get(
            s.zinssatz_typ, "C"
        )
        parts.append(encode_x(typ_char, max_length=1, field_name="ASPZ.TYP"))
        parts.append(encode_n_b(s.zinssatz_value_bps, max_length=4, field_name="ASPZ.BPS"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class ASPS00Record(EDARecord):
    """C23 ASPS00 Teil-01."""

    anspruch: SonstigerAnspruch
    fn: int

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        a = self.anspruch
        parts: list[bytes] = []
        parts.append(record_header(kz="SO", fn=self.fn, tn=1))
        parts.append(encode_betrag(a.betrag, max_length=12, field_name="ASPS.BETRAG"))
        parts.append(encode_x(a.bezeichnung_teil1, max_length=105, field_name="ASPS.BEZ1"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class ASPS00TeilZweiRecord(EDARecord):
    """C24 ASPS00 Teil-02."""

    anspruch: SonstigerAnspruch
    fn: int

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        a = self.anspruch
        parts: list[bytes] = []
        parts.append(record_header(kz="SO", fn=self.fn, tn=2))
        parts.append(encode_x(a.bezeichnung_teil2 or "", max_length=105, field_name="ASPS.BEZ2"))
        return _pad_payload(parts)


@dataclass(frozen=True)
class MieteWegRecord(EDARecord):
    """C21 ASPZM — Lage der Wohnung (Miet-/WEG-Anspruch)."""

    zusatz: MieteWegZusatz
    fn: int

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        z = self.zusatz
        parts: list[bytes] = [
            record_header(kz="ZM", fn=self.fn, tn=1),
            encode_x(z.plz, max_length=5, field_name="ASPZM.PLZ"),
            encode_x(z.ort, max_length=27, field_name="ASPZM.ORT"),
            encode_x(z.auslandskennzeichen or "", max_length=3, field_name="ASPZM.AL"),
            encode_x(z.strasse_hausnummer or "", max_length=35, field_name="ASPZM.SH"),
        ]
        return _pad_payload(parts)


@dataclass(frozen=True)
class VertragRecord(EDARecord):
    """C22 ASPZV — Vertragsart (Schadenersatz aus Vertrag)."""

    zusatz: VertragZusatz
    fn: int

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        parts: list[bytes] = [
            record_header(kz="ZV", fn=self.fn, tn=1),
            encode_x(self.zusatz.vertragsart, max_length=35, field_name="ASPZV.ART"),
        ]
        return _pad_payload(parts)


@dataclass(frozen=True)
class VerbraucherkreditRecord(EDARecord):
    """C27 VKG — Verbraucherkredit-Angaben (§ 491-504 BGB)."""

    angabe: VerbraucherkreditAngabe
    fn: int

    def payload(self) -> bytes:
        """Encode the fixed-width record payload."""
        a = self.angabe
        # Effektiver Jahreszins: 5 bytes with 3 implicit decimals (e.g. 7.250 → 07250).
        zins_thousandths = int((a.effektiver_jahreszins * 1000).to_integral_value())
        parts: list[bytes] = [
            record_header(kz="VK", fn=self.fn, tn=1),
            encode_datum6(a.vertragsdatum, field_name="VKG.VKGD"),
            encode_n(zins_thousandths, max_length=5, field_name="VKG.ZISA"),
        ]
        return _pad_payload(parts)


def encode_katalog_anspruch(
    *, anspruch: KatalogAnspruch, fn: int
) -> list[EDARecord]:
    """Emit ASPK00 + C21/C22 Zusätze + (≤3) ASPZ Zinsen + C27 records.

    Order per the MBA Satzbeschreibung C20 §c: Miete/WEG → Vertrag → Zinsen →
    Verbraucherkredit (Abtretung is not modelled).
    """
    records: list[EDARecord] = [ASPK00Record(anspruch=anspruch, fn=fn)]
    if anspruch.miete_weg_zusatz is not None:
        records.append(MieteWegRecord(zusatz=anspruch.miete_weg_zusatz, fn=fn))
    if anspruch.vertrag_zusatz is not None:
        records.append(VertragRecord(zusatz=anspruch.vertrag_zusatz, fn=fn))
    for idx, staffel in enumerate(anspruch.zinsstaffeln, start=1):
        records.append(ASPZRecord(staffel=staffel, parent_fn=fn, tn=idx))
    if anspruch.verbraucherkredit_angabe is not None:
        records.append(VerbraucherkreditRecord(angabe=anspruch.verbraucherkredit_angabe, fn=fn))
    return records


def encode_sonstiger_anspruch(
    *, anspruch: SonstigerAnspruch, fn: int
) -> list[EDARecord]:
    """Emit ASPS00 (+ Teil-02) + (≤3) ASPZ Zinsen for one Sonstiger Anspruch."""
    records: list[EDARecord] = [ASPS00Record(anspruch=anspruch, fn=fn)]
    if anspruch.bezeichnung_teil2:
        records.append(ASPS00TeilZweiRecord(anspruch=anspruch, fn=fn))
    # Sonstige can also carry Zinsstaffeln — emit as ASPZ rows referencing fn.
    for idx, staffel in enumerate(anspruch.zinsstaffeln, start=1):
        records.append(ASPZRecord(staffel=staffel, parent_fn=fn, tn=idx))
    return records
