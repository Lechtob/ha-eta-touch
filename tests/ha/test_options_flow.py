"""Options use the real flow manager, reload and registry lifecycle."""

from datetime import timedelta
from unittest.mock import patch

import pytest
import voluptuous as vol
from etatouch_restful import EtaMenuNode, EtaTouchConnectionError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.eta_touch.const import DOMAIN, OPTION_DEFAULTS
from custom_components.eta_touch.diagnostics import async_get_config_entry_diagnostics

URI = "40/10021/0/0/12161"
OTHER_URI = "112/9001/0/0/2293"


async def setup(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def save(hass, config_entry, options):
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], options)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    return result


async def test_options_defaults_and_cancel_without_io(hass, mock_client):
    entry = MockConfigEntry(domain=DOMAIN, version=3, data={"host": "eta.test"})
    entry.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_reload") as reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        assert result["data_schema"]({}) == OPTION_DEFAULTS
        hass.config_entries.options.async_abort(result["flow_id"])
        await hass.async_block_till_done()
        reload.assert_not_called()
    assert entry.options == {}
    assert mock_client.mock_calls == []


async def test_interval_reload_preserves_identity_and_polls_at_new_interval(
    hass, mock_client, config_entry, freezer
):
    await setup(hass, config_entry)
    registry = er.async_get(hass)
    sensor = next(
        entry
        for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id)
        if entry.domain == "sensor"
    )
    registry.async_update_entity(sensor.entity_id, name="My boiler")
    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, "future_option": "preserved"}
    )
    old_coordinator = config_entry.runtime_data
    original_data = dict(config_entry.data)
    options = {**config_entry.options, "scan_interval": 120}
    await save(hass, config_entry, {key: options[key] for key in OPTION_DEFAULTS})
    coordinator = config_entry.runtime_data
    assert coordinator is not old_coordinator
    assert coordinator.update_interval == timedelta(seconds=120)
    assert config_entry.data == original_data
    assert config_entry.options == options
    assert registry.async_get(sensor.entity_id).id == sensor.id
    assert registry.async_get(sensor.entity_id).device_id == sensor.device_id
    assert registry.async_get(sensor.entity_id).name == "My boiler"
    assert hass.states.get(sensor.entity_id).state == "42.5"
    mock_client.reset_mock()
    freezer.tick(35)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_client.mock_calls == []
    freezer.tick(90)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_client.get_variable.assert_awaited_once_with(URI)
    mock_client.get_errors.assert_awaited_once()
    data = await async_get_config_entry_diagnostics(hass, config_entry)
    assert data["configuration"]["scan_interval"] == 120
    assert data["configuration"]["manual_variables"]
    assert "future_option" not in data["configuration"]


async def test_invalid_variables_recover_without_saving_or_io(hass, mock_client, config_entry):
    await setup(hass, config_entry)
    before = dict(config_entry.options)
    mock_client.reset_mock()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {**before, "scan_interval": 90, "variables": "not-a-uri"}
        )
        assert result["errors"] == {"variables": "invalid_variables"}
        assert result["data_schema"]({})["scan_interval"] == 90
        assert config_entry.options == before
        assert mock_client.mock_calls == []
        reload.assert_not_called()
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {**before, "scan_interval": 90}
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        reload.assert_awaited_once_with(config_entry.entry_id)


@pytest.mark.parametrize(
    "field,value",
    [
        ("scan_interval", 9),
        ("scan_interval", 3601),
        ("scan_interval", "bad"),
        ("max_discovered_variables", 0),
        ("max_discovered_variables", 201),
        ("variables", 42),
    ],
)
async def test_options_schema_rejects_invalid_values(hass, mock_client, config_entry, field, value):
    await setup(hass, config_entry)
    before = dict(config_entry.options)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    with pytest.raises(vol.Invalid):
        result["data_schema"]({field: value})
    assert config_entry.options == before


async def test_unchanged_options_do_not_reload(hass, mock_client, config_entry):
    await setup(hass, config_entry)
    mock_client.reset_mock()
    with patch.object(hass.config_entries, "async_reload") as reload:
        await save(hass, config_entry, dict(config_entry.options))
        reload.assert_not_called()
    assert mock_client.mock_calls == []


@pytest.mark.parametrize("clear", [{"variables": ""}, {}])
async def test_clear_manual_selection_enables_bounded_discovery(
    hass, mock_client, config_entry, clear
):
    await setup(hass, config_entry)
    mock_client.get_menu.return_value = [
        EtaMenuNode(
            "112/9001",
            "Room",
            "fub",
            (
                EtaMenuNode(
                    "",
                    "Eing\u00e4nge",
                    "object",
                    (
                        EtaMenuNode(
                            "",
                            "Raumf\u00fchler",
                            "object",
                            (
                                EtaMenuNode(OTHER_URI, "Raum Ist", "var"),
                                EtaMenuNode("112/9001/0/0/2294", "Raum Soll", "var"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    ]
    mock_client.reset_mock()
    await save(
        hass,
        config_entry,
        {"scan_interval": 60, "auto_discovery": True, "max_discovered_variables": 1, **clear},
    )
    assert config_entry.options["variables"] == ""
    assert [item.uri for item in config_entry.runtime_data.variables] == [OTHER_URI]
    mock_client.get_menu.assert_awaited_once()
    mock_client.get_variable.assert_awaited_once_with(OTHER_URI)
    data = await async_get_config_entry_diagnostics(hass, config_entry)
    assert data["configuration"]["max_discovered_variables"] == 1
    assert not data["configuration"]["manual_variables"]


async def test_deselect_and_reselect_keeps_registry_name_and_id(hass, mock_client, config_entry):
    await setup(hass, config_entry)
    registry = er.async_get(hass)
    sensor = next(
        entry
        for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id)
        if entry.domain == "sensor"
    )
    registry.async_update_entity(sensor.entity_id, name="My temperature")
    original_options = dict(config_entry.options)
    mock_client.reset_mock()
    await save(hass, config_entry, {**original_options, "variables": ""})
    assert config_entry.runtime_data.variables == ()
    mock_client.get_variable.assert_not_awaited()
    mock_client.get_menu.assert_not_awaited()
    assert hass.states.get(sensor.entity_id).state == "unavailable"
    await save(hass, config_entry, original_options)
    assert registry.async_get(sensor.entity_id).id == sensor.id
    assert registry.async_get(sensor.entity_id).name == "My temperature"
    assert hass.states.get(sensor.entity_id).state == "42.5"


async def test_manual_list_overrides_discovery_and_its_limit(hass, mock_client, config_entry):
    await setup(hass, config_entry)
    mock_client.reset_mock()
    await save(
        hass,
        config_entry,
        {
            **config_entry.options,
            "auto_discovery": True,
            "max_discovered_variables": 1,
            "variables": f"Boiler={URI}\nOther={OTHER_URI}",
        },
    )
    assert [item.uri for item in config_entry.runtime_data.variables] == [URI, OTHER_URI]
    assert mock_client.get_variable.await_count == 2
    assert [call.args[0] for call in mock_client.get_variable.await_args_list] == [URI, OTHER_URI]
    mock_client.get_menu.assert_not_awaited()


async def test_options_can_be_saved_while_controller_offline(hass, mock_client, config_entry):
    await setup(hass, config_entry)
    mock_client.get_variable.side_effect = EtaTouchConnectionError("offline")
    await save(hass, config_entry, {**config_entry.options, "scan_interval": 90})
    assert config_entry.options["scan_interval"] == 90
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.get_api_version.assert_not_awaited()


async def test_new_entry_splits_connection_and_options(hass, mock_client):
    settings = {
        "scan_interval": 75,
        "auto_discovery": False,
        "max_discovered_variables": 12,
        "variables": f"My boiler={URI}",
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"host": "eta.test", "port": 8080, "name": "My ETA", **settings},
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = result["result"]
    assert entry.data == {"host": "eta.test", "port": 8080}
    assert entry.options == settings
    assert entry.title == "My ETA"
    assert entry.version == 3
    assert entry.runtime_data.update_interval == timedelta(seconds=75)
    assert [item.uri for item in entry.runtime_data.variables] == [URI]
