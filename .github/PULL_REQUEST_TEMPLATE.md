## Summary

<!-- Describe what changed and why. -->

## Validation

<!-- List the checks and any read-only hardware validation performed. -->

## Checklist

- [ ] The change is focused and targets `develop` unless it is a release or hotfix.
- [ ] Tests cover new behavior or the reason for missing tests is documented.
- [ ] `ruff check .`, `pytest`, and compile checks pass locally.
- [ ] User-facing behavior and `CHANGELOG.md` are updated when needed.
- [ ] ETA protocol logic is kept in `py-etatouch-restful`.
- [ ] No write operation was tested on real hardware without an explicit test and restore plan.
- [ ] Logs, screenshots, and fixtures contain no private information.

