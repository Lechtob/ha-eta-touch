"""Sensors for ETA Touch."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import EtaTouchDataUpdateCoordinator
from .entity import EtaTouchEntity, eta_touch_function_block_device_info
from .helpers import EtaConfiguredVariable, is_diagnostic_variable


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

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: EtaTouchDataUpdateCoordinator,
        variable: EtaConfiguredVariable,
    ) -> None:
        super().__init__(coordinator)
        self.variable = variable
        self._attr_name = variable.name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{variable.uri.replace('/', '_')}"
        if is_diagnostic_variable(variable.path, variable.name):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

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
        return value.native_value if value is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the ETA unit of measurement."""

        value = self.coordinator.data.values.get(self.variable.uri)
        if value is None or not value.unit:
            return None
        return value.unit

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
