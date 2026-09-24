"""Privacy-preserving diagnostics from cached ETA Touch data."""

from __future__ import annotations

from math import isfinite
from typing import Any

from etatouch_restful import EtaValue
from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from . import EtaTouchConfigEntry
from .const import (
    CONF_AUTO_DISCOVERY,
    CONF_MAX_DISCOVERED_VARIABLES,
    CONF_VARIABLES,
    DEFAULT_AUTO_DISCOVERY,
    DEFAULT_MAX_DISCOVERED_VARIABLES,
    DEFAULT_SCAN_INTERVAL,
)
from .helpers import format_sensor_value, is_diagnostic_variable, validate_variable_uri

_SAFE_UNITS = frozenset(
    {
        "",
        "\u00b0C",
        "\u00b0F",
        "K",
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
        "s",
        "min",
        "h",
    }
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EtaTouchConfigEntry
) -> dict[str, Any]:
    """Return an allowlisted snapshot, without contacting the controller."""
    result: dict[str, Any] = {
        "configuration": {
            "version": entry.version,
            "minor_version": entry.minor_version,
            "state": entry.state.value,
            "scan_interval": entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            "auto_discovery": entry.data.get(CONF_AUTO_DISCOVERY, DEFAULT_AUTO_DISCOVERY),
            "max_discovered_variables": entry.data.get(
                CONF_MAX_DISCOVERED_VARIABLES, DEFAULT_MAX_DISCOVERED_VARIABLES
            ),
            "manual_variables": bool(entry.data.get(CONF_VARIABLES)),
        },
        "coordinator": None,
        "variables": [],
        "active_error_count": None,
    }
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return result

    data = coordinator.data
    current = entry.state is ConfigEntryState.LOADED and coordinator.last_update_success
    result["coordinator"] = {
        "last_update_success": coordinator.last_update_success,
        "last_exception_type": (
            type(coordinator.last_exception).__name__ if coordinator.last_exception else None
        ),
        "has_snapshot": data is not None,
        "data_is_stale": not current,
        "configured_variable_count": len(coordinator.variables),
    }
    # Aliases preserve grouping without exposing user-defined room or block names.
    blocks: dict[str | None, str] = {}
    for variable in coordinator.variables:
        block = blocks.setdefault(variable.function_block, f"block_{len(blocks) + 1}")
        value = data.values.get(variable.uri) if data is not None else None
        try:
            uri = validate_variable_uri(variable.uri)
        except ValueError:
            uri = REDACTED
        result["variables"].append(
            {
                "uri": uri,
                "block": block,
                "diagnostic": variable.is_diagnostic
                or is_diagnostic_variable(variable.path, variable.name),
                "available": current and value is not None,
                "has_cached_value": value is not None,
                "value": _reading_diagnostics(value) if value is not None else None,
            }
        )
    if data is not None:
        result["active_error_count"] = len(data.errors)
    return result


def _finite_number(value: object) -> int | float | None:
    """Do not serialize text or non-finite numbers as numeric metadata."""
    return value if isinstance(value, int | float) and isfinite(value) else None


def _reading_diagnostics(value: EtaValue) -> dict[str, Any]:
    """Retain numeric encoding, but never arbitrary controller text."""
    try:
        raw = value.raw if isfinite(float(value.raw)) else REDACTED
    except (ValueError, TypeError):
        raw = REDACTED
    return {
        "raw": raw,
        "unit": value.unit if value.unit in _SAFE_UNITS else REDACTED,
        "native_value": _finite_number(
            format_sensor_value(value.native_value, value.str_value, value.unit)
        ),
        "decimal_places": _finite_number(value.decimal_places),
        "scale_factor": _finite_number(value.scale_factor),
        "advanced_text_offset": _finite_number(value.advanced_text_offset),
    }
