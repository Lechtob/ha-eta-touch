"""Upgrade saved settings without losing registry or configuration identity."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eta_touch import async_migrate_entry
from custom_components.eta_touch.const import DOMAIN, OPTION_DEFAULTS


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("existing_options", [{}, {"scan_interval": 90, "future": "keep"}])
async def test_migrate_settings_preserves_values_and_is_idempotent(hass, version, existing_options):
    settings = {
        "scan_interval": 45,
        "auto_discovery": False,
        "max_discovered_variables": 23,
        "variables": "My room=112/9001/0/0/2293",
    }
    connection = {"host": "eta.test", "port": 8081, "name": "Old name", "future_data": "keep"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=version,
        title="My ETA",
        unique_id="future-serial",
        data={**connection, **settings},
        options=existing_options,
    )
    entry.add_to_hass(hass)
    original_id = entry.entry_id
    for _ in range(2):
        assert await async_migrate_entry(hass, entry)
        assert entry.version == 3
        assert entry.entry_id == original_id
        assert entry.unique_id == "future-serial"
        assert entry.title == "My ETA"
        assert entry.data == connection
        assert entry.options == {**settings, **existing_options}


@pytest.mark.parametrize("version", [1, 2])
async def test_migration_fills_missing_defaults(hass, version):
    entry = MockConfigEntry(domain=DOMAIN, version=version, data={"host": "eta.test"})
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry)
    assert entry.options == OPTION_DEFAULTS
    assert entry.data == {"host": "eta.test"}
