# Changelog

All notable changes to the ETA Touch Home Assistant integration will be documented here.

## Unreleased

## 1.0.0-rc.1 - 2026-09-24

This is a pre-release for read-only monitoring, not the final 1.0.0 release.
Requires Home Assistant 2026.8.0 or newer. Back up Home Assistant before upgrading:
configuration entries migrate to version 3, which older integration versions cannot load.

- Add an options dialog for polling interval, automatic discovery, discovery limit
  and manual variables. Reload automatically after changed settings are saved.
- Migrate saved polling/discovery settings to options without changing entry IDs,
  entity IDs or user-defined names. Retain deselected entities for later reuse.
- Update py-etatouch-restful to 0.2.1 for scientific/decimal numeric values and
  request timeouts when using Home Assistant's shared HTTP session.
- Test the full integration against HA 2026.8.0 and 2026.9.3.
- Document the read-only 1.0 scope, known limitations and outstanding hardware
  acceptance checks. No climate entities or boiler write controls are included.
- Verify repeated unload/reload polling cleanup and active-error sensor recovery.
- Mark diagnostics without a measurement snapshot as stale rather than current.

- Translate curated sensor names and the active-error sensor in English and German
  through HA translation keys, preserving entity IDs and user-defined names.
- Add a reconfigure flow for host and port, validating the connection and preventing
  duplicate endpoints before updating and reloading the existing entry.
- Add a cached diagnostics download with variable addresses, numeric encoding,
  availability and coordinator health, excluding endpoints and user-defined text.
- Assign sensor device classes and distinguish measurements, lifetime totals and
  resettable maintenance counters. Keep numeric metadata during invalid readings.
- Classify the warm-water supply difference as a temperature delta for correct
  unit conversion; leave generic percentages, rotation speeds and status codes unclassified.
- Discover known measurements under custom functional-block names and addresses;
  probe hidden overview URIs only for existing blocks and require a successful read.
- Cache discovery per load and skip menu requests for manually configured variables.
- Isolate rejected variables, preserve their measurement units while unavailable,
  recover automatically and log only availability transitions.
- Add real Home Assistant config-flow, setup, registry migration and unload tests.
- Stop using host/port as a stable config-entry ID; prevent duplicate endpoints and
  migrate existing entries without replacing their entry or entity IDs.
- Validate port and polling interval inputs and distinguish malformed API data from
  invalid manual variable configuration.
- Migrate functional-block identifiers to valid two-part identifiers without
  replacing their device registry IDs.
- Replace deprecated `via_device` references with `via_device_id`, preparing for
  Home Assistant 2027.8. Register the controller before setting up its functional blocks.
- Require Home Assistant 2026.8.0 or newer for the updated device registry API.

## 0.4.1 - 2026-09-24

- Convert ETA runtime text such as `18727h 42m` to numeric seconds, fixing unavailable
  full-load, flue-gas fan, stoker and ash-removal runtime sensors and recurring log errors.
- Preserve numeric runtime precision and report unparseable measurements as unknown.
- Use the normalized sensor value when determining the measurement state class.

## 0.4.0 - 2026-06-19

- Align automatic discovery with the compact meinETA overview.
- Add boiler temperature, pressure, flue gas, storage and heating-curve values.
- Keep technical measurements and counters as diagnostic entities.
- Expose room and hot-water targets as read-only sensors.
- Remove experimental write controls and the raw write service from the release surface.
- Add Hassfest validation for HACS default repository readiness.

## 0.3.1 - 2026-06-19

- Read room setpoints from ETA display variables while writing to ETA setter variables.

## 0.3.0 - 2026-06-19

- Add Phase 3 controls for room and hot water setpoints.
- Add a switch for hot water immediate loading.

## 0.2.4 - 2026-06-19

- Use a curated default discovery list for MVP and diagnostic ETA variables.

## 0.2.3 - 2026-06-19

- Remove functional block prefixes from discovered sensor names.

## 0.2.2 - 2026-06-19

- Group discovered sensors by ETA functional block devices.
- Mark technical discovered sensors as diagnostic entities.

## 0.2.1 - 2026-06-18

- Improve automatic discovery names and filter out more technical values.
- Replace brand icon with a PNG extracted from the official ETA logo SVG.

## 0.2.0 - 2026-06-18

- Add automatic sensor discovery from the ETA menu tree.
- Bump `py-etatouch-restful` requirement to `0.2.0`.

## 0.1.0 - 2026-06-18

- Initial HACS-compatible custom integration scaffold.
- Config flow for host, port, scan interval and configured ETA variables.
- Sensor entities for configured ETA variables.
- Binary sensor for active ETA errors.
- `eta_touch.set_variable` service for writable ETA variables.
- Manifest metadata aligned with the published `py-etatouch-restful==0.1.0` package.
- Local HACS brand icon added.
