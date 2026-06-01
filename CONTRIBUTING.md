# Contributing

Thanks for helping improve `pyeda-mahn`.

## Ground Rules

- Keep the library pure: no Optimaite product imports, no network calls, no database/storage/signing/beA transport logic.
- Keep public contracts explicit and typed. Prefer Pydantic models and narrow enums over unstructured dictionaries.
- Preserve byte-level determinism. Encoders must emit stable 128-byte records, and parser behavior must be covered by tests.
- Do not add official PDF specifications to pull requests unless redistribution rights are clear. Link to public source URLs and include hashes instead.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
pytest -q
ruff check .
python -m build
twine check dist/*
```

## Pull Requests

All changes must go through pull requests. The default branch is protected and direct pushes are blocked.

Before opening a PR:

- add or update tests,
- run the local checks above,
- update `README.md` or docs for public API changes,
- add a changelog note when behavior changes.

By submitting a contribution, you agree that your contribution is licensed under Apache-2.0.
