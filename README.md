# ETA Touch for Home Assistant

HACS-compatible, read-only Home Assistant integration for ETA Touch heating systems.

Requires Home Assistant 2026.8.0 or newer.

## Installation

### Prerequisites

The ETA controller must expose its local ETAtouch REST interface and be reachable
from the Home Assistant host. Enable that interface according to your controller's
manual; the menu location and availability depend on the controller firmware.
Use its local hostname or IP address, not a meinETA account or cloud URL.
The integration uses HTTP, normally on port `8080`, without login credentials.
Keep this interface on a trusted local network and do not expose it to the internet.

### HACS setup

1. Add `https://github.com/Lechtob/ha-eta-touch` as a HACS custom repository of type
   `Integration`.
2. Install the integration through HACS.
3. Restart Home Assistant.
4. Go to `Settings > Devices & services > Add integration > ETA Touch`.

## Configuration

| Field | Default | Purpose and accepted values |
| --- | --- | --- |
| Name | `ETA Touch` | Display name for the integration entry. |
| Host | Required | Local hostname or IP address, without a URL scheme or path. |
| Port | `8080` | REST port, from `1` to `65535`. |
| Polling interval | `30` | Seconds between updates, from `10` to `3600`. Shorter intervals increase controller traffic. |
| Automatic discovery | Enabled | Discover measurements from the controller menu when no manual variables are supplied. |
| Maximum discovered variables | `48` | Discovery limit, from `1` to `200`; does not limit an explicit manual list. |
| Variables | Empty | Optional URI or `Name=URI`, one per line. A non-empty list replaces automatic discovery. |

These fields are selected during initial setup. Change polling and sensor selection
afterward using **Configure** on the ETA Touch integration entry. Change host and
port through **Reconfigure**. Do not edit Home Assistant's storage files.
Disabling discovery with an empty manual list leaves only the active-error sensor.

Sensor lines can look like this:

```text
Kesseltemperatur=112/10021/0/0/12150
112/10021/0/0/12112
```

If the manual sensor list is empty, the integration creates a curated overview inspired by
meinETA. It uses the functional-block names from your controller, such as Kessel, WW,
FBH, EG or your own room names. Technical values and counters remain diagnostic entities.

Known sensor names and the active-error sensor use Home Assistant translations
(English and German). Default names follow the Home Assistant backend language,
not each user's frontend language. Functional-block names from the controller,
generic discovered names and manually configured sensor names are not translated.
Existing entity IDs and user-assigned names are retained.

Discovery runs once when the integration is loaded. Known measurements are matched by
their menu path within a functional block, independently of the block name and address.
Internal menu labels currently follow the German ETA menu. Known additional overview
URIs are probed only when their block address exists and are added only if readable.
Reload the integration after changing the controller's menu or adding functional blocks.

An unavailable variable affects only its own sensor and is retried on the next update.
Connection failures and controller-wide HTTP failures still mark the integration unavailable.
Manually configured variables do not require a menu request.

### Changing the controller address

Open the existing ETA Touch entry menu under **Settings > Devices & services** and
select **Reconfigure** to change its host or port. Use the new address of the same
controller: the ETA REST API does not currently provide a verified stable device
identity, so the integration cannot detect an accidental change to another boiler.

The connection is checked before saving. An unreachable controller, invalid response
or endpoint already used by another ETA entry leaves the existing configuration intact.
After successful validation, Home Assistant reloads the existing entry. Its entry ID,
entity IDs, custom names, sensor selection and polling settings are preserved. Newly
discovered URIs may still add entities as on any reload. Reconfigure also works when
the previous address is offline. No write commands are sent to the boiler.

### Changing polling and sensor selection

Open **Settings > Devices & services > ETA Touch** and select **Configure** on
the relevant entry. You can change the polling interval, automatic discovery,
discovery limit and manual variable list. The multiline list accepts the same
`Name=URI` or plain URI format as initial setup. A non-empty list replaces discovery,
even if automatic discovery is enabled. To return to automatic selection, clear
the list and enable discovery. To hide individual discovered sensors without
maintaining a manual list, disable those entities using Home Assistant's entity settings.

Saving changed options reloads the integration and runs discovery again when enabled.
Invalid variable syntax keeps the form open without saving or reloading. Settings
can be saved while the controller is offline; setup retries when it becomes reachable.
This configures Home Assistant only and does not change any settings on the boiler.

Existing installations migrate automatically to configuration version 3: polling
and sensor preferences move into options with their saved values intact. Existing
options take precedence if both locations already contain a value. Entry IDs,
entity IDs and user-assigned names are retained. There is no need to remove and
re-add the integration. Older integration versions cannot load version-3 entries;
make a Home Assistant backup before updating if you need a rollback path.

Sensors removed from the selection stop being queried but remain in the entity
registry as unavailable. Re-selecting the same URI reuses its entity ID and custom
name. Their history is not deliberately purged. Devices are not automatically
deleted when their last sensor is deselected. Switching between manual and automatic
selection can change a sensor's function-block association.

### Diagnostics download

On the integration page, open the ETA Touch entry menu and select **Download
diagnostics**. Attach that JSON file when reporting a discovery or value-parsing
issue. Review the file before sharing it.

The ETA section includes safe configuration settings, update status, variable URIs,
anonymous block aliases, units, numeric raw values and scaling metadata. Failed
updates explicitly mark the cached snapshot as stale. Missing variables remain
listed without a value. Only the number of active errors is included.

Hostnames, IP addresses, entry/device/room names, credentials, arbitrary options,
menu paths, formatted display text and error descriptions are excluded. Numeric
measurements and variable addresses are retained for troubleshooting. Home Assistant
adds its own standard system and integration version information to the download.
The export reads cached data only: it never contacts or writes to the boiler.
An entry that has not completed setup can still return basic configuration diagnostics.

### Sensor statistics

Temperature, pressure, power, voltage, current, mass and duration values use Home
Assistant device classes where the ETA unit identifies them. The known warm-water
supply difference uses the temperature-delta class, not absolute temperature.
Percentages are not assumed to be humidity or battery levels; rotation speeds
keep their original ETA units without being classified as linear speed.

Discovered lifetime consumption, runtime and operation counters use `total`.
Consumption since ash removal or emptying the ash box uses `total_increasing`
so a reset starts a new counting cycle. Pellet stock and container contents remain
`measurement`, not consumption totals. Counter classification requires a known
relative menu path and its expected unit; a manual sensor name alone never enables it.
Unitless textual status values have no numeric device or state class.

Entity IDs and native units are unchanged. Home Assistant may convert displayed
values according to user preferences. Existing historical measurements are not
rewritten into consumption totals; the corrected classes apply to future statistics.

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

## Supported devices and limitations

The integration has been tested with an ETA PU15 and its ETAtouch REST interface.
Other ETA models and firmware versions have not been verified. Sensor availability
depends on the installed functional blocks and readable variables, not just the
boiler model. Systems without the local REST interface are unsupported.

The integration communicates directly over local HTTP/XML using the open-source
[py-etatouch-restful library](https://github.com/Lechtob/py-etatouch-restful).
It does not use meinETA, cloud credentials, or a browser session. The overview is
inspired by meinETA, but does not promise identical data on every controller.

Automatic discovery currently recognizes German internal menu paths. Renaming a
functional block may change its device grouping, so review device/area assignments
after such a change. Different hostnames pointing to the same controller cannot
be reliably identified as duplicates; configure each controller only once.

There are no ETA-specific actions, triggers, or conditions in this read-only release.
You can use the sensor states with Home Assistant's standard automation triggers
and conditions, for example to notify you about low pellet stock or an active fault.
Connection loss makes entities unavailable; it does not mean that the boiler itself
has reported a fault. An unavailable error sensor must not be interpreted as all-clear.

## Troubleshooting

- **Cannot connect:** Check the controller address, port, REST setting, and network
  access from Home Assistant. A browser on another network is not a sufficient test.
  After an address change, use **Reconfigure** on the existing integration entry.
- **All entities unavailable:** Check connectivity and the integration's log entry.
  Polling retries automatically; entities recover after a successful update.
- **Only one sensor unavailable:** The variable may no longer be readable on this
  firmware or in this configuration. Other readable variables continue updating.
- **Missing sensors:** Check the manual list, discovery setting and discovery limit.
  Reload after controller menu changes. A manual list replaces the discovered list.
  Not every ETA parameter belongs to the curated overview.
- **Unknown numeric value:** The controller returned a value that cannot safely be
  interpreted as a number. Download diagnostics rather than substituting zero.

For a bug report, include the Home Assistant and integration versions, boiler model,
firmware version if known, affected URI, and a reviewed diagnostics download.
Do not publish credentials, private network details or unreviewed controller dumps.

## Removal

1. Open **Settings > Devices & services > ETA Touch**.
2. Delete the relevant integration entry from its menu. This stops polling and
   removes the entry's devices and entities; it does not alter boiler settings.
3. Remove or update dashboards and automations that referenced those entities.
4. To uninstall the custom integration completely, remove it in HACS after deleting
   all ETA Touch entries, then restart Home Assistant.

Deleting an integration is not a request to purge recorded history or backups.

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
    async with EtaTouchClient("eta.local") as client:
        print(await client.get_api_version())
        print(len(await client.get_errors()))


asyncio.run(main())
```

For normal development use Home Assistant's config flow.

## Core readiness

This is still a HACS custom integration, not an accepted Home Assistant Core
integration or an awarded quality-scale tier. See [the Core readiness checklist](docs/CORE_READINESS.md)
for verified evidence, remaining work, and the intended upstream submission scope.

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
