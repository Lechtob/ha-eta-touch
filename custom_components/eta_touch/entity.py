"""Base entities for ETA Touch."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EtaTouchDataUpdateCoordinator


class EtaTouchEntity(CoordinatorEntity[EtaTouchDataUpdateCoordinator]):
    """Base ETA Touch entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the ETA Touch controller."""

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=self.coordinator.entry.title,
            manufacturer="ETA Heiztechnik",
            model="ETA Touch",
            configuration_url=self.coordinator.client.base_url,
        )

