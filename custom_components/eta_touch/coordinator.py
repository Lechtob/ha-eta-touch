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
from .helpers import (
    EtaConfiguredVariable,
    EtaControlVariable,
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

    full_name: str
    name: str
    function_block: str
    is_diagnostic: bool = False


CURATED_DISCOVERY_VARIABLES = (
    EtaDiscoveryVariableDefinition(
        "EG > Eingänge > Raumfühler > Raum Ist",
        "Raum Ist",
        "EG",
    ),
    EtaDiscoveryVariableDefinition(
        "OG > Eingänge > Raumfühler > Raum Ist",
        "Raum Ist",
        "OG",
    ),
    EtaDiscoveryVariableDefinition(
        "FBH > Eingänge > Außentemperatur",
        "Außentemperatur",
        "FBH",
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
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Vorlaufregler 1 > Angeforderte Leistung",
        "Vorlaufregler 1 Angeforderte Leistung",
        "Kessel",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Vorlaufregler 2 > Angeforderte Temperatur",
        "Vorlaufregler 2 Angeforderte Temperatur",
        "Kessel",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Kessel > Vorlaufregler 2 > Angeforderte Leistung",
        "Vorlaufregler 2 Angeforderte Leistung",
        "Kessel",
    ),
    EtaDiscoveryVariableDefinition(
        "WW > Warmwasserspeicher > Warmwasserspeicher",
        "Warmwasserspeicher Temperatur",
        "WW",
    ),
    EtaDiscoveryVariableDefinition(
        "WW > Warmwasserspeicher > Registerleistung",
        "Warmwasserspeicher Registerleistung",
        "WW",
    ),
    EtaDiscoveryVariableDefinition(
        "WW > Warmwasserspeicher > Vorlauf > Differenz",
        "Warmwasserspeicher Vorlauf Differenz",
        "WW",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Inhalt Pelletsbehälter",
        "Pelletsbehälter Inhalt",
        "Kessel",
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Zählerstände > Gesamtverbrauch",
        "Pellets Gesamtverbrauch",
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
        "Abgasgebläse Ist Drehzahl",
        "Kessel",
        True,
    ),
    EtaDiscoveryVariableDefinition(
        "Kessel > Ausgänge > Luftschieber > Ist Stellung",
        "Luftschieber Ist Stellung",
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
        "Lager > Austragung > Austragleistung",
        "Austragung Austragleistung",
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


CONTROL_KIND_NUMBER = "number"
CONTROL_KIND_SWITCH = "switch"

PHASE_3_CONTROL_VARIABLES = (
    EtaControlVariable(
        name="Raum Soll",
        function_block="EG",
        value_kind=CONTROL_KIND_NUMBER,
        full_name="EG > Raum > Raum > Raum Soll > Solltemperatur setzen auf",
        unit="°C",
        scale_factor=10.0,
        native_min_value=5.0,
        native_max_value=30.0,
        native_step=0.5,
    ),
    EtaControlVariable(
        name="Raum Soll",
        function_block="OG",
        value_kind=CONTROL_KIND_NUMBER,
        full_name="OG > Raum > Raum > Raum Soll > Solltemperatur setzen auf",
        unit="°C",
        scale_factor=10.0,
        native_min_value=5.0,
        native_max_value=30.0,
        native_step=0.5,
    ),
    EtaControlVariable(
        name="Warmwasserspeicher Soll",
        function_block="WW",
        value_kind=CONTROL_KIND_NUMBER,
        full_name="WW > Warmwasserspeicher > Warmwasserspeicher Soll",
        unit="°C",
        scale_factor=10.0,
        native_min_value=30.0,
        native_max_value=70.0,
        native_step=1.0,
    ),
    EtaControlVariable(
        name="Solltemperatur für Sofortladen",
        function_block="WW",
        value_kind=CONTROL_KIND_NUMBER,
        full_name="WW > Warmwasserspeicher > Solltemperatur für [Sofort laden]",
        unit="°C",
        scale_factor=10.0,
        native_min_value=30.0,
        native_max_value=70.0,
        native_step=1.0,
    ),
    EtaControlVariable(
        name="Warmwasser sofort laden",
        function_block="WW",
        value_kind=CONTROL_KIND_SWITCH,
        full_name="WW > Sonstiges > Warmwasser sofort laden",
        on_value="1803",
        off_value="1802",
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
        self.control_variables: tuple[EtaControlVariable, ...] = ()
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
            flattened_menu = flatten_menu(await self.client.get_menu())
            if not self.control_variables:
                self.control_variables = self._discover_control_variables(flattened_menu)
            if not self.variables and self.auto_discovery:
                self.variables = await self._async_discover_variables(flattened_menu)
            values: dict[str, EtaValue] = {}
            for variable in self.variables:
                values[variable.uri] = await self.client.get_variable(variable.uri)
            for variable in self.control_variables:
                if variable.uri is not None:
                    values[variable.uri] = await self.client.get_variable(variable.uri)
            errors = tuple(await self.client.get_errors())
        except (EtaTouchConnectionError, EtaTouchResponseError) as err:
            raise UpdateFailed(f"Could not update ETA Touch data: {err}") from err
        return EtaTouchData(values=values, errors=errors)

    async def _async_discover_variables(
        self,
        flattened_menu,
    ) -> tuple[EtaConfiguredVariable, ...]:
        """Discover a bounded default set of ETA variables from the menu tree."""

        curated_variables = self._discover_curated_variables(flattened_menu)
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

    def _discover_control_variables(
        self,
        flattened_menu,
    ) -> tuple[EtaControlVariable, ...]:
        """Discover supported writable ETA control variables from the menu tree."""

        variables_by_full_name = {variable.full_name: variable for variable in flattened_menu}
        discovered: list[EtaControlVariable] = []
        for definition in PHASE_3_CONTROL_VARIABLES:
            if definition.full_name is None:
                continue
            variable = variables_by_full_name.get(definition.full_name)
            if variable is None:
                continue
            discovered.append(
                EtaControlVariable(
                    name=definition.name,
                    uri=variable.uri,
                    function_block=definition.function_block,
                    value_kind=definition.value_kind,
                    full_name=definition.full_name,
                    unit=definition.unit,
                    scale_factor=definition.scale_factor,
                    native_min_value=definition.native_min_value,
                    native_max_value=definition.native_max_value,
                    native_step=definition.native_step,
                    on_value=definition.on_value,
                    off_value=definition.off_value,
                )
            )
        _LOGGER.info("Discovered %s ETA Touch control variables", len(discovered))
        return tuple(discovered)

    def _discover_curated_variables(
        self,
        flattened_menu,
    ) -> tuple[EtaConfiguredVariable, ...]:
        """Discover ETA variables from curated menu paths."""

        variables_by_full_name = {variable.full_name: variable for variable in flattened_menu}
        discovered: list[EtaConfiguredVariable] = []
        seen_uris: set[str] = set()
        for definition in CURATED_DISCOVERY_VARIABLES:
            variable = variables_by_full_name.get(definition.full_name)
            if variable is None or variable.uri in seen_uris:
                continue
            seen_uris.add(variable.uri)
            discovered.append(
                EtaConfiguredVariable(
                    name=definition.name,
                    uri=variable.uri,
                    function_block=definition.function_block,
                    path=variable.path,
                    is_diagnostic=definition.is_diagnostic,
                )
            )
        return tuple(discovered)

    def variable_by_uri(self, uri: str) -> EtaConfiguredVariable:
        """Return the configured variable for an URI."""

        return next(variable for variable in self.variables if variable.uri == uri)
