"""Active boiler errors must not be confused with connection failures."""

from etatouch_restful import EtaError, EtaTouchConnectionError
from homeassistant.helpers import entity_registry as er


async def test_errors_clear_and_recover_after_connection_failure(hass, mock_client, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = next(
        entity.entity_id
        for entity in er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
        if entity.domain == "binary_sensor"
    )
    assert hass.states.get(entity_id).state == "off"
    assert hass.states.get(entity_id).attributes["errors"] == []

    mock_client.get_errors.return_value = [
        EtaError("40/10021", "Boiler", "Test error", "1", "12:00", "Test description")
    ]
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).state == "on"
    assert hass.states.get(entity_id).attributes["errors"] == [
        {
            "fub": "Boiler",
            "message": "Test error",
            "priority": "1",
            "time": "12:00",
            "description": "Test description",
        }
    ]

    mock_client.get_errors.side_effect = EtaTouchConnectionError("offline")
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).state == "unavailable"

    mock_client.get_errors.side_effect = None
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).state == "on"

    mock_client.get_errors.return_value = []
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).state == "off"
    assert hass.states.get(entity_id).attributes["errors"] == []
