"""Switches for ETA Touch."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CONTROL_KIND_SWITCH, EtaTouchDataUpdateCoordinator
from .entity import EtaTouchEntity, eta_touch_function_block_device_info
from .helpers import EtaControlVariable


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ETA Touch switches."""

    coordinator: EtaTouchDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        EtaTouchSwitch(coordinator, variable)
        for variable in coordinator.control_variables
        if variable.value_kind == CONTROL_KIND_SWITCH
    )


class EtaTouchSwitch(
    EtaTouchEntity, CoordinatorEntity[EtaTouchDataUpdateCoordinator], SwitchEntity
):
    """Switch for a writable ETA text variable."""

    def __init__(
        self,
        coordinator: EtaTouchDataUpdateCoordinator,
        variable: EtaControlVariable,
    ) -> None:
        super().__init__(coordinator)
        if variable.uri is None:
            raise ValueError("ETA Touch switch requires a discovered URI")
        self.variable = variable
        self._attr_name = variable.name
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{variable.uri.replace('/', '_')}_switch"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the ETA functional block."""

        return eta_touch_function_block_device_info(
            self.coordinator,
            self.variable.function_block,
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the ETA switch is on."""

        value = self.coordinator.data.values.get(self.variable.uri)
        if value is None:
            return None
        if str(value.raw) == str(self.variable.on_value):
            return True
        if str(value.raw) == str(self.variable.off_value):
            return False
        return None

    async def async_turn_on(self, **kwargs: object) -> None:
        """Turn the ETA switch on."""

        await self.coordinator.client.set_variable(self.variable.uri, self.variable.on_value)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: object) -> None:
        """Turn the ETA switch off."""

        await self.coordinator.client.set_variable(self.variable.uri, self.variable.off_value)
        await self.coordinator.async_request_refresh()
