"""Smoke test — pyeda-mahn encodes/parses without the host application."""

from __future__ import annotations

from decimal import Decimal

from pyeda_mahn.contracts import (
    Antragsgegner,
    Antragsteller,
    KatalogAnspruch,
    KennsatzInput,
    MahnbescheidAntragInput,
    Mahngericht,
    PartyAddress,
)
from pyeda_mahn.format.kezi_01_mba import encode_mahnbescheidsantrag
from pyeda_mahn.format.record import RECORD_LENGTH
from pyeda_mahn.kennziffer import validate_pvkezi


def _addr() -> PartyAddress:
    return PartyAddress(strasse_hausnummer="Hauptstr. 1", plz="70173", ort="Stuttgart")


def test_encode_mahnbescheid_produces_fixed_width_records() -> None:
    mba = MahnbescheidAntragInput(
        kennsatz=KennsatzInput(tgz="AZ-1", pvkezi="07500012", mahngericht=Mahngericht(plz="70190", ort="Stuttgart")),
        antragsteller=[Antragsteller(anrede="1", name1="Hans", name2="Schäfer", address=_addr())],
        antragsgegner=[Antragsgegner(anrede="1", name1="Klaus", name2="Meier", address=_addr())],
        katalog_ansprueche=[KatalogAnspruch(katalog_nr=11, betrag=Decimal("999.00"))],
    )
    out = encode_mahnbescheidsantrag(mba)
    assert len(out) % RECORD_LENGTH == 0
    assert out[:2] == b"AA"
    # Umlaut preserved, not transliterated.
    assert "Schäfer".encode("cp858") in out


def test_validate_pvkezi_returns_bool_and_rejects_malformed() -> None:
    assert validate_pvkezi("not-a-kennziffer") is False
    assert isinstance(validate_pvkezi("07500012"), bool)
