# Contributing

## Branching

This project follows GitFlow:

- `main`: stable HACS releases only.
- `develop`: integration branch for upcoming work.
- `feature/<name>`: focused feature branches.
- `release/<version>`: release preparation.
- `hotfix/<version>`: urgent fixes from `main`.

Open normal pull requests against `develop`. Only release and hotfix pull requests target
`main`. Keep pull requests focused; protocol and XML parsing changes belong in the
`py-etatouch-restful` repository.

## Reporting issues

Use the structured GitHub issue forms and include the integration version, Home Assistant
version, ETA model, firmware version, and affected entities. Redact public URLs, serial
numbers, and other private information from logs and screenshots.

Security vulnerabilities must be reported privately as described in `SECURITY.md`.

## Local Checks

Use Python 3.14 on Linux (or WSL) for the complete Home Assistant test suite:

```shell
python -m pip install -r requirements_test.txt
ruff check .
python -m compileall custom_components tests
pytest --cov=custom_components.eta_touch --cov-branch --cov-report=term-missing
```

`tests/ha` runs the real Home Assistant flow manager, registry and entity setup using
`pytest-homeassistant-custom-component`. Only the ETA client is mocked. CI requires
100% line and branch coverage of `config_flow.py`. The pinned test framework currently
tests Home Assistant 2026.9.3.

On Windows, the framework-independent helper tests can still be run with
`pytest tests/test_helpers.py`; the complete suite runs in GitHub Actions on Linux.

Hardware checks must be read-only by default. Any write test needs an explicit test value,
expected read-back behavior, and a restore plan before it is run.

## Pull requests

- Update tests for behavior changes.
- Update `CHANGELOG.md` for user-facing changes.
- Keep entity names concise because entities are already grouped by ETA functional block.
- Mark technical values with the Home Assistant diagnostic entity category.
- Wait for CI, HACS, and Hassfest to pass before merging.
- Prefer squash merging feature and maintenance pull requests.

## Scope

Keep Home Assistant specific code in this repository. ETA Touch HTTP/XML protocol logic
belongs in `py-etatouch-restful`.
