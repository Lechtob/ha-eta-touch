"""Data coordinator for ETA Touch."""

from __future__ import annotations

import logging
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
            menu = await self.client.get_menu()
            flattened_menu = flatten_menu(menu)
            if not self.variables and self.auto_discovery:
                self.variables = await self._async_discover_variables(menu, flattened_menu)
            values: dict[str, EtaValue] = {}
            for variable in self.variables:
                values[variable.uri] = await self.client.get_variable(variable.uri)
            errors = tuple(await self.client.get_errors())
        except (EtaTouchConnectionError, EtaTouchResponseError) as err:
            raise UpdateFailed(f"Could not update ETA Touch data: {err}") from err
        return EtaTouchData(values=values, errors=errors)

    async def _async_discover_variables(
        self,
        menu: tuple[EtaMenuNode, ...],
        flattened_menu,
    ) -> tuple[EtaConfiguredVariable, ...]:
        """Discover a bounded default set of ETA variables from the menu tree."""

        curated_variables = self._discover_curated_variables(menu)
        if curated_variables:
            discovered_variables = curated_variables[: self.max_discovered_variables]
            _LOGGER.info("Discovered %s curated ETA Touch variables", len(discovered_variables))
            return discovered_variables

        discovered: list[EtaConfiguredVariable] = []
        seen_uris: set[str] = set()
        for variable in flattened_menu:
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
                    function_block=infer_function_block(variable.path),
                    path=variable.path,
                    is_diagnostic=False,
                )
            )
            if len(discovered) >= self.max_discovered_variables:
                break
        discovered_variables = tuple(discovered)
        _LOGGER.info("Discovered %s ETA Touch variables", len(discovered_variables))
        return discovered_variables

    def _discover_curated_variables(
        self,
        menu: tuple[EtaMenuNode, ...],
    ) -> tuple[EtaConfiguredVariable, ...]:
        """Discover ETA variables from curated menu paths."""

        variables_by_full_name = _index_menu_variables(menu)
        discovered: list[EtaConfiguredVariable] = []
        seen_uris: set[str] = set()
        for definition in CURATED_DISCOVERY_VARIABLES:
            variable = (
                variables_by_full_name.get(definition.full_name)
                if definition.full_name is not None
                else None
            )
            uri = variable.uri if variable is not None else definition.uri
            if uri is None or uri in seen_uris:
                continue
            seen_uris.add(uri)
            discovered.append(
                EtaConfiguredVariable(
                    name=definition.name,
                    uri=uri,
                    function_block=definition.function_block,
                    path=(
                        variable.path
                        if variable is not None
                        else (definition.function_block, definition.name)
                    ),
                    is_diagnostic=definition.is_diagnostic,
                )
            )
        return tuple(discovered)

    def variable_by_uri(self, uri: str) -> EtaConfiguredVariable:
        """Return the configured variable for an URI."""

        return next(variable for variable in self.variables if variable.uri == uri)


def _index_menu_variables(
    menu: tuple[EtaMenuNode, ...],
) -> dict[str, EtaMenuVariable]:
    """Index every readable menu node, including nodes with children."""

    variables: dict[str, EtaMenuVariable] = {}

    def visit(node: EtaMenuNode, parent_path: tuple[str, ...]) -> None:
        path = (*parent_path, node.name)
        if node.uri:
            variables[" > ".join(path)] = EtaMenuVariable(node.uri.strip("/"), path)
        for child in node.children:
            visit(child, path)

    for node in menu:
        visit(node, ())
    return variables
