"""Sensors for ETA Touch."""

from __future__ import annotations

from math import isfinite

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import EtaTouchDataUpdateCoordinator
from .entity import EtaTouchEntity, eta_touch_function_block_device_info
from .helpers import EtaConfiguredVariable, format_sensor_value, is_diagnostic_variable

_DEVICE_CLASSES = {
    UnitOfTemperature.CELSIUS: SensorDeviceClass.TEMPERATURE,
    UnitOfTemperature.FAHRENHEIT: SensorDeviceClass.TEMPERATURE,
    UnitOfTemperature.KELVIN: SensorDeviceClass.TEMPERATURE,
    UnitOfPressure.BAR: SensorDeviceClass.PRESSURE,
    UnitOfPressure.MBAR: SensorDeviceClass.PRESSURE,
    UnitOfPressure.PA: SensorDeviceClass.PRESSURE,
    UnitOfPower.WATT: SensorDeviceClass.POWER,
    UnitOfPower.KILO_WATT: SensorDeviceClass.POWER,
    UnitOfElectricPotential.VOLT: SensorDeviceClass.VOLTAGE,
    UnitOfElectricCurrent.AMPERE: SensorDeviceClass.CURRENT,
    UnitOfElectricCurrent.MILLIAMPERE: SensorDeviceClass.CURRENT,
    UnitOfMass.KILOGRAMS: SensorDeviceClass.WEIGHT,
    UnitOfTime.SECONDS: SensorDeviceClass.DURATION,
}

# Exact relative menu paths avoid treating a renamed sensor or a time setting as
# a counter. The expected unit must also match before enabling sum statistics.
_COUNTERS = {
    ("Zählerstände", "Gesamtverbrauch"): ("kg", SensorStateClass.TOTAL),
    ("Zählerstände", "Verbrauch seit Entaschung"): ("kg", SensorStateClass.TOTAL_INCREASING),
    ("Zählerstände", "Verbrauch seit Aschebox leeren"): ("kg", SensorStateClass.TOTAL_INCREASING),
    ("Zählerstände", "Volllaststunden"): ("s", SensorStateClass.TOTAL),
    ("Zählerstände", "Laufzeit Abgasgebläse"): ("s", SensorStateClass.TOTAL),
    ("Zählerstände", "Laufzeit Stoker"): ("s", SensorStateClass.TOTAL),
    ("Zählerstände", "Laufzeit Entaschung"): ("s", SensorStateClass.TOTAL),
    ("Zählerstände", "Laufzeit Saugturbine"): ("s", SensorStateClass.TOTAL),
    ("Zählerstände", "Zähler Heizbetriebe"): ("", SensorStateClass.TOTAL),
    ("Zählerstände", "Zähler Zündungen"): ("", SensorStateClass.TOTAL),
    ("Austragung", "Laufzeit Austragschnecke"): ("s", SensorStateClass.TOTAL),
}
_TEMPERATURE_DELTA_PATH = ("Warmwasserspeicher", "Vorlauf", "Differenz")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ETA Touch sensors."""

    coordinator: EtaTouchDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        EtaTouchVariableSensor(coordinator, variable) for variable in coordinator.variables
    )


class EtaTouchVariableSensor(
    EtaTouchEntity, CoordinatorEntity[EtaTouchDataUpdateCoordinator], SensorEntity
):
    """Sensor for a configured ETA variable."""

    def __init__(
        self,
        coordinator: EtaTouchDataUpdateCoordinator,
        variable: EtaConfiguredVariable,
    ) -> None:
        super().__init__(coordinator)
        self.variable = variable
        self._attr_name = variable.name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{variable.uri.replace('/', '_')}"
        self._update_value_metadata()
        if variable.is_diagnostic or is_diagnostic_variable(variable.path, variable.name):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _update_value_metadata(self) -> None:
        """Keep measurement metadata across temporary per-variable failures."""
        value = self.coordinator.data.values.get(self.variable.uri)
        if value is not None:
            self._attr_native_unit_of_measurement = value.unit or None
            self._attr_device_class = _DEVICE_CLASSES.get(value.unit)
            if (
                self._attr_device_class is SensorDeviceClass.TEMPERATURE
                and self.variable.path[1:] == _TEMPERATURE_DELTA_PATH
            ):
                self._attr_device_class = SensorDeviceClass.TEMPERATURE_DELTA
            self._attr_state_class = self._counter_state_class(value.unit)
            if self._attr_state_class is None and value.unit:
                self._attr_state_class = SensorStateClass.MEASUREMENT

    def _counter_state_class(self, unit: str) -> SensorStateClass | None:
        """Return statistics semantics only for a known path and matching unit."""
        definition = _COUNTERS.get(self.variable.path[1:])
        return definition[1] if definition is not None and definition[0] == unit else None

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_value_metadata()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        return super().available and self.variable.uri in self.coordinator.data.values

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the ETA functional block."""

        return eta_touch_function_block_device_info(
            self.coordinator,
            self.variable.function_block,
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the latest native value."""

        value = self.coordinator.data.values.get(self.variable.uri)
        if value is None:
            return None
        native_value = format_sensor_value(value.native_value, value.str_value, value.unit)
        if self._counter_state_class(value.unit) is not None and (
            not isinstance(native_value, int | float) or not isfinite(native_value)
        ):
            return None
        return native_value

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return raw ETA metadata."""

        value = self.coordinator.data.values.get(self.variable.uri)
        if value is None:
            return {"eta_uri": self.variable.uri}
        return {
            "eta_uri": self.variable.uri,
            "raw_value": value.raw,
            "str_value": value.str_value,
            "decimal_places": value.decimal_places,
            "scale_factor": value.scale_factor,
            "advanced_text_offset": value.advanced_text_offset,
        }
