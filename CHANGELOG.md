# Changelog

All notable changes to the ETA Touch Home Assistant integration will be documented here.

## 0.2.3 - Unreleased

- Remove functional block prefixes from discovered sensor names.

## 0.2.2 - Unreleased

- Group discovered sensors by ETA functional block devices.
- Mark technical discovered sensors as diagnostic entities.

## 0.2.1 - Unreleased

- Improve automatic discovery names and filter out more technical values.
- Replace brand icon with a PNG extracted from the official ETA logo SVG.

## 0.2.0 - Unreleased

- Add automatic sensor discovery from the ETA menu tree.
- Bump `py-etatouch-restful` requirement to `0.2.0`.

## 0.1.0 - Unreleased

- Initial HACS-compatible custom integration scaffold.
- Config flow for host, port, scan interval and configured ETA variables.
- Sensor entities for configured ETA variables.
- Binary sensor for active ETA errors.
- `eta_touch.set_variable` service for writable ETA variables.
- Manifest metadata aligned with the published `py-etatouch-restful==0.1.0` package.
- Local HACS brand icon added.
