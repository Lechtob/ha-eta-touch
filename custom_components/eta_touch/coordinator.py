"""Data coordinator for ETA Touch."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from etatouch_restful import (
    EtaError,
    EtaTouchClient,
    EtaTouchConnectionError,
    EtaTouchResponseError,
    EtaValue,
    flatten_menu,
    is_default_discovery_candidate,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_AUTO_DISCOVERY,
    CONF_MAX_DISCOVERED_VARIABLES,
    DEFAULT_AUTO_DISCOVERY,
    DEFAULT_MAX_DISCOVERED_VARIABLES,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .helpers import EtaConfiguredVariable, format_discovered_variable_name, parse_variable_lines

DISCOVERY_ALLOWED_UNITS = frozenset(
    {
        "°C",
        "%",
        "bar",
        "mbar",
        "Pa",
        "W",
        "kW",
        "V",
        "A",
        "mA",
        "kg",
        "kg/h",
        "U/min",
        "rpm",
    }
)
DISCOVERY_EXCLUDED_NAME_PARTS = frozenset(
    {
        "Anforderung",
        "Drehzahlsteuerung",
        "Eingang",
        "Freigabe",
        "Lag ",
        "Luftfeuchteanzeige",
        "Meldungen",
        "Warnung",
        "Ventilzustand",
        "Zustand",
        "max.",
    }
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EtaTouchData:
    """Latest ETA Touch data snapshot."""

    values: dict[str, EtaValue]
    errors: tuple[EtaError, ...]


class EtaTouchDataUpdateCoordinator(DataUpdateCoordinator[EtaTouchData]):
    """Fetch data from ETA Touch."""

    entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.variables = parse_variable_lines(entry.data.get("variables", ""))
        self.auto_discovery = entry.data.get(CONF_AUTO_DISCOVERY, DEFAULT_AUTO_DISCOVERY)
        self.max_discovered_variables = entry.data.get(
            CONF_MAX_DISCOVERED_VARIABLES,
            DEFAULT_MAX_DISCOVERED_VARIABLES,
        )
        self.client = EtaTouchClient(
            entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
            session=async_get_clientsession(hass),
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

    async def _async_update_data(self) -> EtaTouchData:
        try:
            if not self.variables and self.auto_discovery:
                self.variables = await self._async_discover_variables()
            values: dict[str, EtaValue] = {}
            for variable in self.variables:
                values[variable.uri] = await self.client.get_variable(variable.uri)
            errors = tuple(await self.client.get_errors())
        except (EtaTouchConnectionError, EtaTouchResponseError) as err:
            raise UpdateFailed(f"Could not update ETA Touch data: {err}") from err
        return EtaTouchData(values=values, errors=errors)

    async def _async_discover_variables(self) -> tuple[EtaConfiguredVariable, ...]:
        """Discover a bounded default set of ETA variables from the menu tree."""

        discovered: list[EtaConfiguredVariable] = []
        seen_uris: set[str] = set()
        for variable in flatten_menu(await self.client.get_menu()):
            if variable.uri in seen_uris:
                continue
            if not is_default_discovery_candidate(variable):
                continue
            if any(part in variable.full_name for part in DISCOVERY_EXCLUDED_NAME_PARTS):
                continue
            value = await self.client.get_variable(variable.uri)
            if value.unit not in DISCOVERY_ALLOWED_UNITS:
                continue
            seen_uris.add(variable.uri)
            discovered.append(
                EtaConfiguredVariable(
                    name=format_discovered_variable_name(variable.path),
                    uri=variable.uri,
                )
            )
            if len(discovered) >= self.max_discovered_variables:
                break
        discovered_variables = tuple(discovered)
        _LOGGER.info("Discovered %s ETA Touch variables", len(discovered_variables))
        return discovered_variables

    def variable_by_uri(self, uri: str) -> EtaConfiguredVariable:
        """Return the configured variable for an URI."""

        return next(variable for variable in self.variables if variable.uri == uri)
