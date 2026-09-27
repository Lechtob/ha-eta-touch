"""Active boiler errors must not be confused with connection failures."""

import pytest
from etatouch_restful import EtaError, EtaTouchConnectionError
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize(
    "priorities,expected",
    [
        (["Nachricht"], "off"),
        (["  NACHRICHT\t", "Nachricht"], "off"),
        (["Warnung"], "on"),
        (["Fehler"], "on"),
        (["Error"], "on"),
        (["Warning"], "on"),
        ([""], "on"),
        (["0"], "on"),
        (["Message"], "on"),
        (["future-priority"], "on"),
        (["Nachricht", "Fehler"], "on"),
        (["Warnung", "Nachricht"], "on"),
        (["Nachricht", "future-priority"], "on"),
    ],
)
async def test_priorities_preserve_all_message_details(
    hass, mock_client, config_entry, priorities, expected
):
    messages = [
        EtaError("40/10021", "Boiler", "Test message", priority, "12:00", "Test details")
        for priority in priorities
    ]
    mock_client.get_errors.return_value = messages
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", "eta_touch", f"{config_entry.entry_id}_active_errors"
    )
    state = hass.states.get(entity_id)
    assert state.state == expected
    assert [error["priority"] for error in state.attributes["errors"]] == priorities
    assert config_entry.runtime_data.data.errors == tuple(messages)


async def test_information_fault_and_connection_failure_transitions(
    hass, mock_client, config_entry
):
    information = EtaError("40/10021", "Boiler", "Maintenance", "Nachricht", "12:00", "Details")
    fault = EtaError("40/10021", "Boiler", "Test fault", "Fehler", "12:01", "Details")
    mock_client.get_errors.return_value = [information]
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", "eta_touch", f"{config_entry.entry_id}_active_errors"
    )
    coordinator = config_entry.runtime_data
    assert hass.states.get(entity_id).state == "off"

    mock_client.get_errors.return_value = [information, fault]
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).state == "on"
    mock_client.get_errors.return_value = [information]
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).state == "off"

    mock_client.get_errors.side_effect = EtaTouchConnectionError("offline")
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).state == "unavailable"
    mock_client.get_errors.side_effect = None
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).state == "off"
    assert len(hass.states.get(entity_id).attributes["errors"]) == 1
    mock_client.get_errors.return_value = []
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).attributes["errors"] == []


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
