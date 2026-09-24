# ETA Touch for Home Assistant

HACS-compatible, read-only Home Assistant integration for ETA Touch heating systems.

Requires Home Assistant 2026.8.0 or newer.

## Installation

1. Add `https://github.com/Lechtob/ha-eta-touch` as a HACS custom repository of type
   `Integration`.
2. Install the integration through HACS.
3. Restart Home Assistant.
4. Go to `Settings > Devices & services > Add integration > ETA Touch`.

## Configuration

The config flow asks for:

- ETA Touch host/IP.
- Port, usually `8080`.
- Polling interval in seconds.
- Automatic sensor discovery.
- Optional manual sensor variables, one variable per line.

Sensor lines can look like this:

```text
Kesseltemperatur=112/10021/0/0/12150
112/10021/0/0/12112
```

If the manual sensor list is empty, the integration creates a curated overview inspired by
meinETA. It uses the functional-block names from your controller, such as Kessel, WW,
FBH, EG or your own room names. Technical values and counters remain diagnostic entities.

Discovery runs once when the integration is loaded. Known measurements are matched by
their menu path within a functional block, independently of the block name and address.
Internal menu labels currently follow the German ETA menu. Known additional overview
URIs are probed only when their block address exists and are added only if readable.
Reload the integration after changing the controller's menu or adding functional blocks.

An unavailable variable affects only its own sensor and is retried on the next update.
Connection failures and controller-wide HTTP failures still mark the integration unavailable.
Manually configured variables do not require a menu request.

The default overview includes, where supported by the connected ETA configuration:

- Boiler temperature, target, lower temperature, pressure, flue gas and pellet values.
- Hot-water temperature and target.
- Heating-circuit operating mode and calculated heating-curve temperature.
- EG and OG current and target room temperatures.
- Pellet storage and outside temperature.
- Mixer, fan, air-slider, extraction and runtime diagnostics.

Room and hot-water targets are intentionally read-only in this release. ETA write behavior
depends on operating mode and firmware, so unverified controls are not exposed as entities or
services. URIs can still be inspected manually with `/user/varinfo/<uri>`.

## Status

Implemented:

- Config flow setup.
- Sensors for configured ETA variables.
- Automatic sensor discovery from the ETA menu tree.
- Binary sensor for active ETA errors.
- Read-only room and hot-water targets.
- Diagnostic entities for technical values and counters.

Writable controls will return only after their effective read-back behavior has been verified
across ETA operating modes.

## Local Smoke Test

The Python dependency is published as `py-etatouch-restful==0.2.0`. A quick read-only
check against a local boiler:

```python
import asyncio

from etatouch_restful import EtaTouchClient


async def main() -> None:
    async with EtaTouchClient("192.168.0.159") as client:
        print(await client.get_api_version())
        print(len(await client.get_errors()))


asyncio.run(main())
```

For normal development use Home Assistant's config flow.

## Repository Setup

Empfohlene GitHub-Repo-Einstellungen:

- Repository-Name: `ha-eta-touch`
- Default Branch: `main`
- Develop Branch: `develop`
- HACS Kategorie: `Integration`
- Home-Assistant-Domain: `eta_touch`

Initial push to an empty repository:

```powershell
git init
git add .
git commit -m "Initial ETA Touch Home Assistant integration"
git branch -M main
git remote add origin https://github.com/<user>/ha-eta-touch.git
git push -u origin main
git switch -c develop
git push -u origin develop
```

## Dependency

`custom_components/eta_touch/manifest.json` requires `py-etatouch-restful==0.2.0`.
Publish that package version before releasing this integration version through HACS.
