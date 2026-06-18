# Contributing

## Branching

This project follows GitFlow:

- `main`: stable HACS releases only.
- `develop`: integration branch for upcoming work.
- `feature/<name>`: focused feature branches.
- `release/<version>`: release preparation.
- `hotfix/<version>`: urgent fixes from `main`.

## Local Checks

```powershell
python -m pip install ruff pytest
ruff check .
python -m compileall custom_components tests
pytest
```

For full Home Assistant integration tests, add `pytest-homeassistant-custom-component`
and mock the `py-etatouch-restful` client.

## Scope

Keep Home Assistant specific code in this repository. ETA Touch HTTP/XML protocol logic
belongs in `py-etatouch-restful`.

