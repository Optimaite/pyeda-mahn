# pyeda-mahn

[![CI](https://github.com/Optimaite/pyeda-mahn/actions/workflows/ci.yml/badge.svg)](https://github.com/Optimaite/pyeda-mahn/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

`pyeda-mahn` is a Python encoder and parser for **EDA-Mahn**, the German fixed-width record format used for electronic data exchange in automated court dunning proceedings (*Elektronischer Datenaustausch im automatisierten gerichtlichen Mahnverfahren*).

The library is intentionally small and pure:

- Pydantic v2 contracts in.
- Deterministic 128-byte `.eda` records out.
- CP-858 text encoding with German umlauts preserved.
- No database, network, beA, EGVP, signing, storage, billing, or Optimaite product coupling.

Optimaite uses this package as the pure format layer inside its legal product. The surrounding filing workflow remains application-specific.

## Status

This is an alpha release. The encoders and parsers follow the public EDA-Mahn Format 4 V 4.0.00 Satzbeschreibungen, but the field maps are **not yet byte-pinned against a live Mahngericht Testdurchgang**. Validate with your own test exchange before using the output for production legal filings.

Issues, sanitized fixtures, and real court-response edge cases are very welcome.

## Installation

```bash
pip install "pyeda-mahn @ git+https://github.com/Optimaite/pyeda-mahn.git"
```

PyPI publishing is prepared through GitHub Actions trusted publishing, but the PyPI project/publisher still has to be activated before `pip install pyeda-mahn` works from the public index.

For local development:

```bash
git clone https://github.com/Optimaite/pyeda-mahn.git
cd pyeda-mahn
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
pytest -q
```

## What It Covers

Outbound encoders, Anwalt to Gericht:

| KEZI | Antragsart |
|---|---|
| 01 | Mahnbescheidsantrag (MBA), including C21 Miete/WEG, C22 Vertrag, C27 Verbraucherkredit |
| 07 | Neuzustellungsantrag Mahnbescheid (NEMB) |
| 08 | Vollstreckungsbescheidsantrag (VBA) |
| 10 | Neuzustellungsantrag Vollstreckungsbescheid (NEVB) |
| 20 | Monierungsantwort (MOA) |
| 25 | Ruecknahme / Erledigterklaerung (RN) |
| 29 | Kosteneinzug / Abgabeantrag (EZKOAB) |
| 30 | Widerspruch (WI) |

Inbound parsers, Gericht to Anwalt:

| KEZI | Nachricht |
|---|---|
| 03 | Kostennachricht Mahnbescheid (KNMB) |
| 05 | Zustellungsnachricht MB/VB (ZNMBVB) |
| 16 | Abgabenachricht (ABN) |
| 18 | Widerspruchsnachricht (WIN) |
| 20 | Monierung (MO) |
| 22 | Kostennachricht Vollstreckungsbescheid (KNVB) |
| 90 | Eingangsquittung (QU) |

## Quick Example

```python
from decimal import Decimal

from pyeda_mahn.contracts import (
    Antragsteller,
    Antragsgegner,
    KatalogAnspruch,
    KennsatzInput,
    MahnbescheidAntragInput,
    Mahngericht,
    PartyAddress,
)
from pyeda_mahn.format.kezi_01_mba import encode_mahnbescheidsantrag

address = PartyAddress(
    strasse_hausnummer="Hauptstr. 1",
    plz="70173",
    ort="Stuttgart",
)

mba = MahnbescheidAntragInput(
    kennsatz=KennsatzInput(
        tgz="AZ-2026-001",
        pvkezi="07500012",
        mahngericht=Mahngericht(plz="70190", ort="Stuttgart"),
    ),
    antragsteller=[
        Antragsteller(
            anrede="1",
            name1="Hans",
            name2="Schaefer",
            address=address,
        )
    ],
    antragsgegner=[
        Antragsgegner(
            anrede="1",
            name1="Klaus",
            name2="Meier",
            address=address,
        )
    ],
    katalog_ansprueche=[
        KatalogAnspruch(katalog_nr=11, betrag=Decimal("999.00")),
    ],
)

eda_bytes = encode_mahnbescheidsantrag(mba)
assert len(eda_bytes) % 128 == 0
```

## Parsing Example

```python
from pyeda_mahn.format.kezi_90_qu_parser import parse_eingangsbestaetigung

notice = parse_eingangsbestaetigung(raw_eda_bytes)
print(notice.gnr)
```

## Character Encoding

EDA-Mahn records are fixed-width and encoded as CP-858. The library preserves German umlauts and fails closed on unsupported characters or field overflows. It does not transliterate `ae`, `oe`, or `ue` automatically because doing so can change legally relevant names.

## What This Library Does Not Do

`pyeda-mahn` does **not**:

- sign `.eda` files,
- create PKCS#7 detached signatures,
- submit messages over beA or EGVP,
- manage PVKEZI registration,
- calculate legal fees or claims,
- persist filings or court messages,
- create legal advice or decide whether a filing is appropriate.

Host applications are responsible for those workflows.

## Reference Material

The public repository does not redistribute official PDF/ZIP specifications. See [docs/reference-sources.md](docs/reference-sources.md) for official source URLs and hashes observed during implementation.

## Safety Notes

Automated Mahnverfahren filings can have legal consequences. Treat this package as format infrastructure, not as legal advice. Before production use:

1. Register and verify the participant Kennziffer/PVKEZI with the relevant Mahngericht.
2. Run a Mahngericht Testdurchgang for the exact filing variants you intend to send.
3. Compare generated records against court-accepted fixtures.
4. Keep transport, signing, audit logging, and deadline management in your host application.

## Development Checks

```bash
pytest -q
ruff check .
python -m build
twine check dist/*
```

## License

Apache-2.0. See [LICENSE](LICENSE).

---

# pyeda-mahn (Deutsch)

`pyeda-mahn` ist eine Python-Bibliothek zum Kodieren und Parsen des deutschen EDA-Mahn-Formats fuer das automatisierte gerichtliche Mahnverfahren. Die Bibliothek ist bewusst auf das reine Dateiformat beschraenkt: typisierte Pydantic-Eingaben, byte-genaue 128-Byte-Festsaetze, keine Signatur, kein Transport, keine Produktlogik.

Status: Alpha. Die Implementierung folgt den oeffentlichen Satzbeschreibungen, ist aber noch nicht gegen einen echten Mahngericht-Testdurchgang byte-genau verifiziert. Bitte vor produktiver Nutzung mit dem zustaendigen Mahngericht testen.
