"""ETA Touch integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import voluptuous as vol

from .const import DOMAIN, SERVICE_SET_VARIABLE
from .coordinator import EtaTouchDataUpdateCoordinator
from .helpers import validate_variable_uri

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
ATTR_BEGIN = "begin"
ATTR_END = "end"
ATTR_URI = "uri"
ATTR_VALUE = "value"

SET_VARIABLE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URI): str,
        vol.Required(ATTR_VALUE): vol.Any(str, int, float),
        vol.Optional(ATTR_BEGIN): vol.All(vol.Coerce(int), vol.Range(min=0, max=96)),
        vol.Optional(ATTR_END): vol.All(vol.Coerce(int), vol.Range(min=0, max=96)),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ETA Touch from a config entry."""

    coordinator = EtaTouchDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an ETA Touch config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register ETA Touch services once."""

    if hass.services.has_service(DOMAIN, SERVICE_SET_VARIABLE):
        return

    async def async_set_variable(call: Any) -> None:
        uri = validate_variable_uri(call.data[ATTR_URI])
        value = call.data[ATTR_VALUE]
        begin = call.data.get(ATTR_BEGIN)
        end = call.data.get(ATTR_END)

        coordinators = [
            entry.runtime_data
            for entry in hass.config_entries.async_entries(DOMAIN)
            if hasattr(entry, "runtime_data")
        ]
        if not coordinators:
            return

        await coordinators[0].client.set_variable(uri, value, begin=begin, end=end)
        await coordinators[0].async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_VARIABLE,
        async_set_variable,
        schema=SET_VARIABLE_SCHEMA,
    )
