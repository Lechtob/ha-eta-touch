# ETA Touch for Home Assistant

HACS-compatible Home Assistant integration for ETA Touch heating systems.

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
- Sensor variables, one variable per line.

Sensor lines can look like this:

```text
Kesseltemperatur=112/10021/0/0/12150
112/10021/0/0/12112
```

URIs can be discovered from `/user/menu` and inspected with `/user/varinfo/<uri>`.

## Status

Implemented:

- Config flow setup.
- Sensors for configured ETA variables.
- Binary sensor for active ETA errors.
- Service `eta_touch.set_variable` for writable ETA variables.

Next features should use `/user/varinfo` to classify entities automatically as sensors,
binary sensors, selects or switches.

## Local Smoke Test

The Python dependency is published as `py-etatouch-restful==0.1.0`. A quick read-only
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

For normal development use Home Assistant's config flow rather than calling write
services manually.

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

`custom_components/eta_touch/manifest.json` requires `py-etatouch-restful==0.1.0`,
which is available on PyPI.
