"""Data coordinator for ETA Touch."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from etatouch_restful import (
    EtaError,
    EtaMenuNode,
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
    SENSOR_TRANSLATION_KEYS,
)
from .helpers import (
    EtaConfiguredVariable,
    format_discovered_variable_name,
    infer_function_block,
    parse_variable_lines,
)

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


@dataclass(frozen=True, slots=True)
class EtaDiscoveryVariableDefinition:
    """A curated ETA variable to discover by menu path."""

    full_name: str | None
    name: str
    function_block: str
    is_diagnostic: bool = False
    uri: str | None = None


@dataclass(frozen=True, slots=True)
class EtaMenuVariable:
    """An ETA menu node that can itself hold a readable value."""

    uri: str
    path: tuple[str, ...]


CURATED_DISCOVERY_VARIABLES = (
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Kessel",
        "Kessel",
        "Kessel",
        uri="40/10021/0/0/12161",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Kesseldruck",
        "Kesseldruck",
        "Kessel",
        uri="40/10021/0/0/12180",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Abgas",
        "Abgas",
        "Kessel",
        uri="40/10021/0/0/12162",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Restsauerstoff",
        "Restsauerstoff",
        "Kessel",
        uri="40/10021/0/0/12164",
    ),
    EtaDiscoveryVariableDefinition(
        "EG > Eingänge > Raumfühler > Raum Ist",
        "Raum",
        "EG",
    ),
    EtaDiscoveryVariableDefinition(
        "EG > Eingänge > Raumfühler > Raum Soll",
        "Raum Soll",
        "EG",
    ),
    EtaDiscoveryVariableDefinition(
        "EG > Sonstiges > Betrieb",
        "Betrieb",
        "EG",
    ),
    EtaDiscoveryVariableDefinition(
        "OG > Eingänge > Raumfühler > Raum Ist",
        "Raum",
        "OG",
    ),
    EtaDiscoveryVariableDefinition(
        "OG > Eingänge > Raumfühler > Raum Soll",
        "Raum Soll",
        "OG",
    ),
    EtaDiscoveryVariableDefinition(
        "OG > Sonstiges > Betrieb",
        "Betrieb",
        "OG",
    ),
    EtaDiscoveryVariableDefinition(
        "Sys > Außentemperatur",
        "Außentemperatur",
        "Sys",
        uri="40/10241/0/0/12197",
    ),
    EtaDiscoveryVariableDefinition(
        "FBH > Sonstiges > Betrieb",
        "Betrieb",
        "FBH",
    ),
    EtaDiscoveryVariableDefinition(
        None,
        "Vorlauf",
        "FBH",
        uri="120/10101/0/0/12241",
    ),
    EtaDiscoveryVariableDefinition(
        "FBH > Heizkreis > Heizkurve",
        "Heizkurve",
        "FBH",
        uri="120/10101/0/0/12111",
    ),
    EtaDiscoveryVariableDefinition(
        "HEIZK. > Heizkreis > Heizkurve",
        "Heizkurve",
        "HEIZK.",
        uri="120/10481/0/0/12111",
    ),
    EtaDiscoveryVariableDefinition(
        None,
        "Vorlauf",
        "HEIZK.",
        uri="120/10481/0/0/12241",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Kessel > Kessel Soll",
        "Kessel Soll",
        "Kessel",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Kessel unten",
        "Kessel unten",
        "Kessel",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Vorlaufregler 1 > Angeforderte Temperatur",
        "Vorlaufregler 1 Angeforderte Temperatur",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Vorlaufregler 1 > Angeforderte Leistung",
        "Vorlaufregler 1 Angeforderte Leistung",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Vorlaufregler 2 > Angeforderte Temperatur",
        "Vorlaufregler 2 Angeforderte Temperatur",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Vorlaufregler 2 > Angeforderte Leistung",
        "Vorlaufregler 2 Angeforderte Leistung",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "WW > Warmwasserspeicher > Warmwasserspeicher",
        "Warmwasserspeicher",
        "WW",
    ),
    EtaDiscoveryVariableDefinition(
        "WW > Warmwasserspeicher > Warmwasserspeicher Soll",
        "Warmwasserspeicher Soll",
        "WW",
    ),
    EtaDiscoveryVariableDefinition(
        "WW > Warmwasserspeicher > Registerleistung",
        "Registerleistung",
        "WW",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "WW > Warmwasserspeicher > Vorlauf > Differenz",
        "Vorlauf Differenz",
        "WW",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Inhalt Pelletsbehälter",
        "Inhalt Pelletsbehälter",
        "Kessel",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Gesamtverbrauch",
        "Gesamtverbrauch",
        "Kessel",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Verbrauch seit Entaschung",
        "Verbrauch seit Entaschung",
        "Kessel",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Verbrauch seit Aschebox leeren",
        "Verbrauch seit Aschebox leeren",
        "Kessel",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Ausgänge > Abgasgebläse > Abgasgebläse > Ist Drehzahl",
        "Abgasgebläse",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Ausgänge > Luftschieber > Ist Stellung",
        "Luftschieber Stellung",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Ausgänge > Vorlaufmischer 1 > Ist Temperatur",
        "Vorlaufmischer 1 Ist Temperatur",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Ausgänge > Vorlaufmischer 1 > Position",
        "Vorlaufmischer 1 Position",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Ausgänge > Vorlaufmischer 2 > Ist Temperatur",
        "Vorlaufmischer 2 Ist Temperatur",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Ausgänge > Vorlaufmischer 2 > Position",
        "Vorlaufmischer 2 Position",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Lager > Vorrat",
        "Vorrat",
        "Lager",
        uri="40/10201/0/0/12015",
    ),
    EtaDiscoveryVariableDefinition(
        "Lager > Austragung > Austragleistung",
        "Austragleistung",
        "Lager",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Lager > Austragung > Laufzeit Austragschnecke",
        "Laufzeit Austragschnecke",
        "Lager",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Volllaststunden",
        "Volllaststunden",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Laufzeit Abgasgebläse",
        "Laufzeit Abgasgebläse",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Zähler Heizbetriebe",
        "Zähler Heizbetriebe",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Zähler Zündungen",
        "Zähler Zündungen",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Laufzeit Stoker",
        "Laufzeit Stoker",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Laufzeit Entaschung",
        "Laufzeit Entaschung",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Laufzeit Saugturbine",
        "Laufzeit Saugturbine",
        "Kessel",
        True,
    ),
)


class EtaTouchDataUpdateCoordinator(DataUpdateCoordinator[EtaTouchData]):
    """Fetch data from ETA Touch."""

    entry: ConfigEntry
    controller_device_id: str

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.variables = parse_variable_lines(entry.data.get("variables", ""))
        self.auto_discovery = entry.data.get(CONF_AUTO_DISCOVERY, DEFAULT_AUTO_DISCOVERY)
        self.max_discovered_variables = entry.data.get(
            CONF_MAX_DISCOVERED_VARIABLES,
            DEFAULT_MAX_DISCOVERED_VARIABLES,
        )
        self._discovery_complete = bool(self.variables) or not self.auto_discovery
        self._unavailable_variables: set[str] = set()
        self.client = EtaTouchClient(
            entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
            session=async_get_clientsession(hass),
        )
        super().__init__(
            hass,
            config_entry=entry,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

    async def _async_update_data(self) -> EtaTouchData:
        try:
            values: dict[str, EtaValue] = {}
            if not self._discovery_complete:
                menu = await self.client.get_menu()
                self.variables, values = await self._async_discover_variables(menu)
            for variable in self.variables:
                if variable.uri not in values:
                    value = await self._async_read_variable(variable.uri)
                    if value is not None:
                        values[variable.uri] = value
            errors = tuple(await self.client.get_errors())
        except (EtaTouchConnectionError, EtaTouchResponseError) as err:
            raise UpdateFailed(f"Could not update ETA Touch data: {err}") from err
        self._discovery_complete = True
        return EtaTouchData(values=values, errors=errors)

    async def _async_read_variable(self, uri: str, *, probe: bool = False) -> EtaValue | None:
        """Isolate a rejected variable, but propagate controller-wide failures."""
        try:
            value = await self.client.get_variable(uri)
        except EtaTouchResponseError as err:
            if err.status in (401, 403, 429) or (err.status is not None and err.status >= 500):
                raise
            if not probe and uri not in self._unavailable_variables:
                _LOGGER.warning("ETA variable %s is unavailable: %s", uri, err)
                self._unavailable_variables.add(uri)
            return None
        if uri in self._unavailable_variables:
            _LOGGER.info("ETA variable %s is available again", uri)
            self._unavailable_variables.remove(uri)
        return value

    async def _async_discover_variables(
        self,
        menu: Sequence[EtaMenuNode],
    ) -> tuple[tuple[EtaConfiguredVariable, ...], dict[str, EtaValue]]:
        """Discover a bounded default set of ETA variables from the menu tree."""

        indexed = _index_menu_variables(menu)
        discovered = list(self._discover_curated_variables(indexed))[
            : self.max_discovered_variables
        ]
        seen_uris = {variable.uri for variable in discovered}
        values: dict[str, EtaValue] = {}

        # Some supported overview values are hidden from the menu. Probe only exact
        # known URIs whose functional-block address is advertised by this controller.
        blocks = {node.uri.strip("/"): node.name for node in menu if node.uri}
        for definition in CURATED_DISCOVERY_VARIABLES:
            if len(discovered) >= self.max_discovered_variables:
                break
            uri = definition.uri
            if uri is None or uri in indexed or uri in seen_uris:
                continue
            block = blocks.get("/".join(uri.split("/")[:2]))
            if block is None:
                continue
            if any(
                item.name == definition.name and item.function_block == block for item in discovered
            ):
                continue
            seen_uris.add(uri)
            value = await self._async_read_variable(uri, probe=True)
            if value is None:
                continue
            discovered.append(
                EtaConfiguredVariable(
                    name=definition.name,
                    uri=uri,
                    function_block=block,
                    path=(block, definition.name),
                    is_diagnostic=definition.is_diagnostic,
                    translation_key=SENSOR_TRANSLATION_KEYS[definition.name],
                )
            )
            values[uri] = value

        if discovered:
            _LOGGER.info("Discovered %s curated ETA Touch variables", len(discovered))
            return tuple(discovered), values

        for variable in flatten_menu(tuple(menu)):
            if variable.uri in seen_uris:
                continue
            if not is_default_discovery_candidate(variable):
                continue
            if any(part in variable.full_name for part in DISCOVERY_EXCLUDED_NAME_PARTS):
                continue
            seen_uris.add(variable.uri)
            value = await self._async_read_variable(variable.uri, probe=True)
            if value is None or value.unit not in DISCOVERY_ALLOWED_UNITS:
                continue
            values[variable.uri] = value
            discovered.append(
                EtaConfiguredVariable(
                    name=format_discovered_variable_name(variable.path),
                    uri=variable.uri,
                    function_block=infer_function_block(variable.path),
                    path=variable.path,
                    is_diagnostic=False,
                )
            )
            if len(discovered) >= self.max_discovered_variables:
                break
        discovered_variables = tuple(discovered)
        _LOGGER.info("Discovered %s ETA Touch variables", len(discovered_variables))
        return discovered_variables, values

    def _discover_curated_variables(
        self,
        indexed: dict[str, EtaMenuVariable],
    ) -> tuple[EtaConfiguredVariable, ...]:
        """Discover ETA variables from curated menu paths."""

        discovered: list[EtaConfiguredVariable] = []
        seen_uris: set[str] = set()
        for definition in CURATED_DISCOVERY_VARIABLES:
            relative_path = (
                tuple(definition.full_name.split(" > ")[1:]) if definition.full_name else None
            )
            for variable in indexed.values():
                if variable.uri in seen_uris or not (
                    (relative_path is not None and variable.path[1:] == relative_path)
                    or variable.uri == definition.uri
                ):
                    continue
                seen_uris.add(variable.uri)
                discovered.append(
                    EtaConfiguredVariable(
                        name=definition.name,
                        uri=variable.uri,
                        function_block=infer_function_block(variable.path),
                        path=variable.path,
                        is_diagnostic=definition.is_diagnostic,
                        translation_key=SENSOR_TRANSLATION_KEYS[definition.name],
                    )
                )
        return tuple(discovered)

    def variable_by_uri(self, uri: str) -> EtaConfiguredVariable:
        """Return the configured variable for an URI."""

        return next(variable for variable in self.variables if variable.uri == uri)


def _index_menu_variables(
    menu: Sequence[EtaMenuNode],
) -> dict[str, EtaMenuVariable]:
    """Index every readable menu node, including nodes with children."""

    variables: dict[str, EtaMenuVariable] = {}

    def visit(node: EtaMenuNode, parent_path: tuple[str, ...]) -> None:
        path = (*parent_path, node.name)
        uri = node.uri.strip("/")
        if len(uri.split("/")) == 5:
            variables.setdefault(uri, EtaMenuVariable(uri, path))
        for child in node.children:
            visit(child, path)

    for node in menu:
        visit(node, ())
    return variables
