"""Climate entities for ETA Touch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import ATTR_TEMPERATURE, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CONTROL_KIND_CLIMATE, EtaTouchDataUpdateCoordinator
from .entity import EtaTouchEntity, eta_touch_function_block_device_info
from .helpers import EtaControlVariable


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ETA Touch climate entities."""

    coordinator: EtaTouchDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        EtaTouchClimate(coordinator, variable)
        for variable in coordinator.control_variables
        if variable.value_kind == CONTROL_KIND_CLIMATE
    )


class EtaTouchClimate(
    EtaTouchEntity, CoordinatorEntity[EtaTouchDataUpdateCoordinator], ClimateEntity
):
    """Climate entity for an ETA room controller."""

    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: EtaTouchDataUpdateCoordinator,
        variable: EtaControlVariable,
    ) -> None:
        super().__init__(coordinator)
        if (
            variable.current_uri is None
            or variable.read_uri is None
            or variable.write_uri is None
        ):
            raise ValueError("ETA Touch climate requires current, read and write URIs")
        self.variable = variable
        self._attr_name = variable.name
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{variable.write_uri.replace('/', '_')}_climate"
        )
        self._attr_min_temp = variable.native_min_value
        self._attr_max_temp = variable.native_max_value
        self._attr_target_temperature_step = variable.native_step

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the ETA functional block."""

        return eta_touch_function_block_device_info(
            self.coordinator,
            self.variable.function_block,
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""

        return self._native_value(self.variable.current_uri)

    @property
    def target_temperature(self) -> float | None:
        """Return the current ETA target temperature."""

        return self._native_value(self.variable.read_uri)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""

        if ATTR_TEMPERATURE not in kwargs:
            return
        value = float(kwargs[ATTR_TEMPERATURE])
        raw_value = round(value * self.variable.scale_factor)
        await self.coordinator.client.set_variable(self.variable.write_uri, raw_value)
        await self.coordinator.async_request_refresh()

    def _native_value(self, uri: str | None) -> float | None:
        """Return a numeric native value from coordinator data."""

        if uri is None:
            return None
        value = self.coordinator.data.values.get(uri)
        if value is None:
            return None
        native_value = value.native_value
        return native_value if isinstance(native_value, int | float) else None
