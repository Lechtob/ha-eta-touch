"""ETA Touch integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DEFAULT_PORT, DOMAIN, OPTION_DEFAULTS
from .coordinator import EtaTouchDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

type EtaTouchConfigEntry = ConfigEntry[EtaTouchDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EtaTouchConfigEntry) -> bool:
    """Set up ETA Touch from a config entry."""

    coordinator = EtaTouchDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    device_registry = dr.async_get(hass)
    controller = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="ETA Heiztechnik",
        model="ETA Touch",
        configuration_url=coordinator.client.base_url,
    )
    coordinator.controller_device_id = controller.id
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EtaTouchConfigEntry) -> bool:
    """Unload an ETA Touch config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Retain registry identities while upgrading legacy configuration."""
    if entry.version > 3:
        return False
    if entry.version == 1:
        registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
            identifiers = {
                (DOMAIN, f"{entry.entry_id}:{identifier[2]}")
                if len(identifier) == 3 and identifier[:2] == (DOMAIN, entry.entry_id)
                else identifier
                for identifier in device.identifiers
            }
            if identifiers != device.identifiers:
                registry.async_update_device(device.id, new_identifiers=identifiers)
        # Older versions used the mutable endpoint as a supposedly stable unique ID.
        legacy_unique_id = f"{entry.data[CONF_HOST]}:{entry.data.get(CONF_PORT, DEFAULT_PORT)}"
        hass.config_entries.async_update_entry(
            entry,
            version=2,
            unique_id=None if entry.unique_id == legacy_unique_id else entry.unique_id,
        )
    if entry.version == 2:
        data = dict(entry.data)
        options = dict(entry.options)
        for key, default in OPTION_DEFAULTS.items():
            options.setdefault(key, data.pop(key, default))
        hass.config_entries.async_update_entry(entry, data=data, options=options, version=3)
    return True
