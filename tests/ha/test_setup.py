"""Real setup, entity, registry and unload tests."""

import pytest
from etatouch_restful import EtaTouchConnectionError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.eta_touch import async_migrate_entry
from custom_components.eta_touch.const import DOMAIN


async def test_setup_and_unload(hass, mock_client, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    sensor = next(entity for entity in entities if entity.domain == "sensor")
    assert hass.states.get(sensor.entity_id).state == "42.5"
    registry = dr.async_get(hass)
    block = registry.async_get(sensor.device_id)
    assert block.identifiers == {(DOMAIN, f"{config_entry.entry_id}:ETA Touch")}
    controller = registry.async_get(block.via_device_id)
    assert controller.identifiers == {(DOMAIN, config_entry.entry_id)}
    assert controller.id != block.id
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_offline_retries(hass, mock_client, config_entry):
    mock_client.get_menu.side_effect = EtaTouchConnectionError("offline")
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)


@pytest.mark.parametrize("unique_id", ["eta.test:8080", "future-device-serial", None])
async def test_migrate_preserves_entry_identity(hass, config_entry, unique_id):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, version=1, unique_id=unique_id)
    entry_id = config_entry.entry_id
    assert await async_migrate_entry(hass, config_entry)
    assert config_entry.version == 2
    assert config_entry.entry_id == entry_id
    assert config_entry.unique_id == (None if unique_id == "eta.test:8080" else unique_id)
    assert await async_migrate_entry(hass, config_entry)


async def test_newer_entry_not_downgraded(hass, config_entry):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, version=3)
    assert not await async_migrate_entry(hass, config_entry)
    assert config_entry.version == 3


async def test_legacy_device_keeps_registry_identity(hass, config_entry):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, version=1)
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id, "EG")},
        name="My existing room",
    )
    entity = er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"{config_entry.entry_id}_room",
        config_entry=config_entry,
        device_id=device.id,
    )
    assert await async_migrate_entry(hass, config_entry)
    migrated = registry.async_get(device.id)
    assert migrated.identifiers == {(DOMAIN, f"{config_entry.entry_id}:EG")}
    assert migrated.name == "My existing room"
    assert er.async_get(hass).async_get(entity.entity_id).device_id == device.id
    assert len(dr.async_entries_for_config_entry(registry, config_entry.entry_id)) == 1
