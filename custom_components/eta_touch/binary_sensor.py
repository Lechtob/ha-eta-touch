"""Binary sensors for ETA Touch."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import EtaTouchDataUpdateCoordinator
from .entity import EtaTouchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ETA Touch binary sensors."""

    coordinator: EtaTouchDataUpdateCoordinator = entry.runtime_data
    async_add_entities([EtaTouchActiveErrorsBinarySensor(coordinator)])


class EtaTouchActiveErrorsBinarySensor(
    EtaTouchEntity, CoordinatorEntity[EtaTouchDataUpdateCoordinator], BinarySensorEntity
):
    """Reports whether ETA Touch currently has active errors."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_has_entity_name = True
    _attr_name = "Active errors"
    _attr_translation_key = "active_errors"

    def __init__(self, coordinator: EtaTouchDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_active_errors"

    @property
    def is_on(self) -> bool:
        """Return true when active errors are present."""

        return bool(self.coordinator.data.errors)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return active error details."""

        return {
            "errors": [
                {
                    "fub": error.fub_name,
                    "message": error.message,
                    "priority": error.priority,
                    "time": error.time,
                    "description": error.description,
                }
                for error in self.coordinator.data.errors
            ]
        }

