"""Numbers for ETA Touch."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CONTROL_KIND_NUMBER, EtaTouchDataUpdateCoordinator
from .entity import EtaTouchEntity, eta_touch_function_block_device_info
from .helpers import EtaControlVariable


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ETA Touch numbers."""

    coordinator: EtaTouchDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        EtaTouchNumber(coordinator, variable)
        for variable in coordinator.control_variables
        if variable.value_kind == CONTROL_KIND_NUMBER
    )


class EtaTouchNumber(
    EtaTouchEntity, CoordinatorEntity[EtaTouchDataUpdateCoordinator], NumberEntity
):
    """Number for a writable ETA variable."""

    def __init__(
        self,
        coordinator: EtaTouchDataUpdateCoordinator,
        variable: EtaControlVariable,
    ) -> None:
        super().__init__(coordinator)
        if variable.uri is None:
            raise ValueError("ETA Touch number requires a discovered URI")
        self.variable = variable
        self._attr_name = variable.name
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{variable.uri.replace('/', '_')}_number"
        )
        self._attr_native_unit_of_measurement = variable.unit
        self._attr_native_min_value = variable.native_min_value
        self._attr_native_max_value = variable.native_max_value
        self._attr_native_step = variable.native_step
        if variable.unit == UnitOfTemperature.CELSIUS:
            self._attr_device_class = NumberDeviceClass.TEMPERATURE

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the ETA functional block."""

        return eta_touch_function_block_device_info(
            self.coordinator,
            self.variable.function_block,
        )

    @property
    def native_value(self) -> float | None:
        """Return the latest native value."""

        value = self.coordinator.data.values.get(self.variable.uri)
        if value is None:
            return None
        native_value = value.native_value
        return native_value if isinstance(native_value, int | float) else None

    async def async_set_native_value(self, value: float) -> None:
        """Set the ETA variable to a new native value."""

        raw_value = round(value * self.variable.scale_factor)
        await self.coordinator.client.set_variable(self.variable.uri, raw_value)
        await self.coordinator.async_request_refresh()
