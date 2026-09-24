"""Reconfigure the connection through HA without replacing registry identities."""

from unittest.mock import patch

import pytest
import voluptuous as vol
from etatouch_restful import EtaTouchConnectionError, EtaTouchResponseError
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eta_touch.const import DOMAIN


async def start_reconfigure(hass, entry, data=None):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}, data=data
    )


@pytest.mark.parametrize("host,port", [(" NEW.TEST. ", 8081), ("ETA.TEST.", 8080)])
async def test_reconfigure_reloads_and_preserves_identity(
    hass, mock_client, config_entry, host, port
):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={"future_option": "preserved"})
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, config_entry.entry_id)
    sensor = next(entity for entity in entities if entity.domain == "sensor")
    registry.async_update_entity(sensor.entity_id, name="My custom sensor")
    device_registry = dr.async_get(hass)
    device_registry.async_update_device(sensor.device_id, name_by_user="My custom device")
    original_entities = {
        (entity.entity_id, entity.unique_id, entity.device_id) for entity in entities
    }
    original_devices = {
        device.id
        for device in dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    }
    original_data = dict(config_entry.data)
    original_coordinator = config_entry.runtime_data
    original_title = config_entry.title
    original_unique_id = config_entry.unique_id
    result = await start_reconfigure(hass, config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["data_schema"]({}) == {"host": "eta.test", "port": 8080}
    mock_client.get_api_version.assert_not_awaited()
    normalized_host = host.strip().lower().rstrip(".")
    mock_client.base_url = f"http://{normalized_host}:{port}"
    with (
        patch(
            "custom_components.eta_touch.config_flow.EtaTouchClient", return_value=mock_client
        ) as validate,
        patch(
            "custom_components.eta_touch.coordinator.EtaTouchClient", return_value=mock_client
        ) as connect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": host, "port": port}
        )
        await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not original_coordinator
    assert config_entry.data == {**original_data, "host": normalized_host, "port": port}
    assert config_entry.options == {"future_option": "preserved"}
    assert config_entry.title == original_title
    assert config_entry.unique_id == original_unique_id
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    for factory in (validate, connect):
        factory.assert_called_once()
        assert factory.call_args.args == (normalized_host,)
        assert factory.call_args.kwargs["port"] == port
    mock_client.get_api_version.assert_awaited_once()
    assert mock_client.get_variable.await_count == 2
    assert {
        (entity.entity_id, entity.unique_id, entity.device_id)
        for entity in er.async_entries_for_config_entry(registry, config_entry.entry_id)
    } == original_entities
    assert {
        device.id
        for device in dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    } == original_devices
    assert registry.async_get(sensor.entity_id).name == "My custom sensor"
    assert device_registry.async_get(sensor.device_id).name_by_user == "My custom device"
    controller = device_registry.async_get(config_entry.runtime_data.controller_device_id)
    assert controller.configuration_url == mock_client.base_url


@pytest.mark.parametrize(
    "error,expected",
    [
        (EtaTouchConnectionError("offline"), "cannot_connect"),
        (EtaTouchResponseError("bad XML"), "invalid_response"),
        (RuntimeError("unexpected"), "unknown"),
        (ValueError("bad data"), "unknown"),
    ],
)
async def test_reconfigure_error_then_recovery(hass, mock_client, config_entry, error, expected):
    config_entry.add_to_hass(hass)
    before = dict(config_entry.data)
    mock_client.get_api_version.side_effect = error
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await start_reconfigure(hass, config_entry, {"host": "new.test", "port": 8081})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected}
        assert result["data_schema"]({}) == {"host": "new.test", "port": 8081}
        assert config_entry.data == before
        reload.assert_not_called()
        mock_client.get_api_version.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "new.test", "port": 8081}
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert result["reason"] == "reconfigure_successful"
        reload.assert_awaited_once_with(config_entry.entry_id)


async def test_duplicate_endpoint_can_be_corrected(hass, mock_client, config_entry):
    config_entry.add_to_hass(hass)
    other = MockConfigEntry(domain=DOMAIN, data={"host": " OTHER.TEST. "})
    other.add_to_hass(hass)
    before = dict(config_entry.data)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await start_reconfigure(hass, config_entry, {"host": "other.test", "port": 8080})
        assert result["errors"] == {"base": "already_configured"}
        assert config_entry.data == before
        mock_client.get_api_version.assert_not_awaited()
        reload.assert_not_called()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "other.test", "port": 8081}
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert result["reason"] == "reconfigure_successful"
        assert other.data == {"host": " OTHER.TEST. "}
        reload.assert_awaited_once_with(config_entry.entry_id)


async def test_reconfigure_after_old_endpoint_failed(hass, mock_client, config_entry):
    config_entry.add_to_hass(hass)
    mock_client.get_variable.side_effect = EtaTouchConnectionError("Old endpoint offline")
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.get_variable.side_effect = None
    result = await start_reconfigure(hass, config_entry, {"host": "new.test", "port": 8080})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data["host"] == "new.test"


@pytest.mark.parametrize(
    "field,value", [("host", " "), ("port", 0), ("port", 65536), ("port", "bad")]
)
async def test_reconfigure_invalid_form(hass, mock_client, config_entry, field, value):
    config_entry.add_to_hass(hass)
    before = dict(config_entry.data)
    result = await start_reconfigure(hass, config_entry)
    with pytest.raises(vol.Invalid):
        result["data_schema"]({field: value})
    assert config_entry.data == before
    mock_client.get_api_version.assert_not_awaited()


async def test_reconfigure_cancel_and_legacy_defaults(hass, mock_client):
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={"host": "eta.test"})
    entry.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await start_reconfigure(hass, entry)
        assert result["data_schema"]({}) == {"host": "eta.test", "port": 8080}
        hass.config_entries.flow.async_abort(result["flow_id"])
        await hass.async_block_till_done()
        assert entry.data == {"host": "eta.test"}
        reload.assert_not_called()
    mock_client.get_api_version.assert_not_awaited()
