# Home Assistant Core readiness

This is an implementation audit, not a quality-tier award or an upstream submission.
The initial Core scope is read-only sensors and an active-error binary sensor,
with devices grouped by functional block. Keep HACS working while preparing it.

## Evidence available in this repository

| Area | Implementation and verification |
| --- | --- |
| UI setup, endpoint validation, duplicate detection | `config_flow.py`; `tests/ha/test_config_flow.py` and `test_reconfigure.py`; CI enforces complete flow line/branch coverage. |
| Options and migration | `test_options_flow.py`, `test_options_migration.py`; connection data is separate from polling/discovery options, with automatic reload and migration from versions 1 and 2. |
| Stable entry/entity identity through migration and reconfiguration | `__init__.py`, `entity.py`; `test_setup.py` and `test_reconfigure.py`. |
| Centralized polling and lifecycle | `coordinator.py`, both read-only platforms with explicit `PARALLEL_UPDATES`; repeated unload/setup test verifies polling cancellation and registry identity. |
| Discovery and partial failures | `test_discovery.py` covers menu paths, custom block names, rejected variables, transport failures and recovery. |
| Numeric values and statistics | `test_helpers.py`, `test_sensor.py` cover duration conversion, numeric metadata, counters and unavailable values. |
| Active errors | `test_binary_sensor.py` distinguishes active faults, no faults, connection loss and recovery. |
| Private diagnostics | `diagnostics.py`, `test_diagnostics.py` cover real downloads, redaction, stale/missing snapshots and no extra network requests. |
| Entity translations | `strings.json`, English/German translations, `test_entity_translations.py`; custom names remain unchanged. |
| User documentation | README covers local REST prerequisites, every setup field, limitations, troubleshooting and removal. |

`custom_components/eta_touch/quality_scale.yaml` lists every Bronze rule with
evidence or an explicit outstanding task. Documentation rules remain open until
the content exists in the upstream documentation repository. Higher-tier rules
listed there do not imply that the entire tier is complete.

## Next changes, in order

1. **Upstream documentation and brands.** Prepare the integration page for
   `home-assistant/home-assistant.io`, based on the README but using Core setup
   instructions. Verify `eta_touch` assets in `home-assistant/brands` and submit
   missing assets. Local HACS branding is not evidence of upstream acceptance.
2. **Core-native port and validation.** Port to `homeassistant/components/eta_touch`
   and `tests/components/eta_touch`, replace custom-component test fixtures with
   Core fixtures, and adapt the manifest and documentation URL for Core. Run the
   target Core revision's tests, lint, hassfest and typing checks. Re-audit every
   Bronze rule against that revision before opening the upstream integration PR.

The HACS release candidate uses py-etatouch-restful 0.2.1, including numeric parsing
and borrowed-session timeout fixes. It does not claim an awarded quality tier.
Do not remove the HACS manifest version from this repository just because the
eventual Core port has different requirements. HACS release acceptance is tracked
separately in [the release checklist](RELEASE_CHECKLIST.md).

## Remaining limitations, separate from the Bronze baseline

- Only the PU15 installation has been verified; do not advertise all ETA models
  or firmware versions as supported without evidence.
- Discovery relies on known German menu paths and runs at load time, not continuously.
- Function-block device grouping currently uses the block name; renaming a block
  can affect grouping. A stable block-identifier migration needs separate design.
- No verified immutable boiler identifier is available. Host aliases can bypass
  duplicate-endpoint detection, and reconfigure cannot prove it is the same boiler.
- Writable controls remain out of scope until their effective behavior is verified.
- Strict typing and the complete higher-tier checklist remain separate work.
  A high aggregate coverage percentage alone does not prove the per-module Silver rule.

## Verification workflow

Run `ruff check .` and the full pytest suite using `requirements_test.txt` on the
supported Linux/Python environment. CI also runs compilation and checks config-flow
coverage. HACS and hassfest checks must pass before merging. Lightweight local
helper tests do not replace the real Home Assistant tests in CI.

Tests mock the ETA transport only, exercising the real Home Assistant lifecycle.
They must never require a live boiler or send write commands to production equipment.

## Official references

- [Quality-scale checklist](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist/)
- [Config flow and data/options separation](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow/)
- [Coordinator-backed parallel updates](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates/)
- [Brands requirement](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/brands/)
- [Integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)

Recheck the current upstream documentation at submission time; requirements evolve.
