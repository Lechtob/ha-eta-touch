"""Discovery and partial failures exercised through real HA entity setup."""

import logging
from datetime import timedelta

import pytest
from etatouch_restful import EtaMenuNode, EtaTouchConnectionError, EtaTouchResponseError, EtaValue
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.eta_touch.const import DOMAIN

ROOM_PATH = ("Eing\u00e4nge", "Raumf\u00fchler", "Raum Ist")
GOOD_URI = "112/9001/0/0/2293"
OTHER_URI = "112/9002/0/0/2293"


def menu_block(name, uri, path):
    """Build a minimal real ETA menu tree with one variable in a functional block."""
    node = EtaMenuNode(uri, path[-1], "var")
    for part in reversed(path[:-1]):
        node = EtaMenuNode("", part, "object", (node,))
    return EtaMenuNode("/".join(uri.split("/")[:2]), name, "fub", (node,))


def reading(uri, raw="425"):
    return EtaValue(uri, raw, "42.5", "\u00b0C", 1, 10)


async def setup_auto(hass, mock_client, config_entry, menu, **options):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={**config_entry.data, "auto_discovery": True, "variables": "", **options},
    )
    mock_client.get_menu.return_value = menu
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry.runtime_data


def state_for(hass, config_entry, uri):
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{config_entry.entry_id}_{uri.replace('/', '_')}"
    )
    return hass.states.get(entity_id)


async def test_custom_room_names_and_addresses(hass, mock_client, config_entry):
    coordinator = await setup_auto(
        hass,
        mock_client,
        config_entry,
        [
            menu_block("Living room", GOOD_URI, ROOM_PATH),
            menu_block("Attic", OTHER_URI, ROOM_PATH),
        ],
    )
    assert {(item.uri, item.function_block, item.name) for item in coordinator.variables} == {
        (GOOD_URI, "Living room", "Raum"),
        (OTHER_URI, "Attic", "Raum"),
    }
    assert state_for(hass, config_entry, GOOD_URI).state == "42.5"
    assert state_for(hass, config_entry, OTHER_URI).state == "42.5"
    await coordinator.async_refresh()
    mock_client.get_menu.assert_awaited_once()
    assert mock_client.get_variable.await_count == 4


async def test_duplicate_menu_paths_do_not_hide_variables(hass, mock_client, config_entry):
    coordinator = await setup_auto(
        hass,
        mock_client,
        config_entry,
        [
            menu_block("Room", GOOD_URI, ROOM_PATH),
            menu_block("Room", OTHER_URI, ROOM_PATH),
            menu_block("Alias", GOOD_URI, ROOM_PATH),
        ],
    )
    assert {item.uri for item in coordinator.variables} == {GOOD_URI, OTHER_URI}
    assert mock_client.get_variable.await_count == 2


async def test_readable_parent_nodes_are_discovered(hass, mock_client, config_entry):
    uri = "112/9001/0/0/12111"
    curve = EtaMenuNode(uri, "Heizkurve", "object", (EtaMenuNode("", "Settings", "object"),))
    menu = [
        EtaMenuNode(
            "112/9001", "Radiators", "fub", (EtaMenuNode("", "Heizkreis", "object", (curve,)),)
        )
    ]
    coordinator = await setup_auto(hass, mock_client, config_entry, menu)
    assert [(item.uri, item.name, item.function_block) for item in coordinator.variables] == [
        (uri, "Heizkurve", "Radiators")
    ]


async def test_missing_blocks_are_not_probed_and_empty_menu_is_cached(
    hass, mock_client, config_entry
):
    coordinator = await setup_auto(hass, mock_client, config_entry, [])
    await coordinator.async_refresh()
    assert coordinator.variables == ()
    mock_client.get_variable.assert_not_awaited()
    mock_client.get_menu.assert_awaited_once()


async def test_hidden_overview_values_require_successful_probe(hass, mock_client, config_entry):
    supply_uri = "120/10101/0/0/12241"

    async def get_variable(uri):
        if uri == supply_uri:
            return reading(uri)
        raise EtaTouchResponseError("Not present", status=404)

    mock_client.get_variable.side_effect = get_variable
    coordinator = await setup_auto(
        hass, mock_client, config_entry, [EtaMenuNode("120/10101", "Custom heating circuit", "fub")]
    )
    assert [(item.uri, item.function_block) for item in coordinator.variables] == [
        (supply_uri, "Custom heating circuit")
    ]
    assert state_for(hass, config_entry, supply_uri).state == "42.5"
    # The successful probe is reused for the first update, not requested twice.
    assert sum(call.args == (supply_uri,) for call in mock_client.get_variable.await_args_list) == 1
    assert {call.args[0] for call in mock_client.get_variable.await_args_list} == {
        supply_uri,
        "120/10101/0/0/12111",
    }


async def test_advertised_path_takes_precedence_over_legacy_uri(hass, mock_client, config_entry):
    actual_uri = "120/10101/0/0/99999"

    async def get_variable(uri):
        if uri == actual_uri:
            return reading(uri)
        raise EtaTouchResponseError("Not present", status=404)

    mock_client.get_variable.side_effect = get_variable
    coordinator = await setup_auto(
        hass,
        mock_client,
        config_entry,
        [menu_block("My circuit", actual_uri, ("Heizkreis", "Heizkurve"))],
    )
    assert [item.uri for item in coordinator.variables] == [actual_uri]
    assert "120/10101/0/0/12111" not in {
        call.args[0] for call in mock_client.get_variable.await_args_list
    }


async def test_generic_fallback_skips_rejected_and_unsupported_values(
    hass, mock_client, config_entry
):
    uris = [f"112/9001/0/0/{number}" for number in range(1, 4)]

    async def get_variable(uri):
        if uri == uris[0]:
            raise EtaTouchResponseError("Not readable")
        if uri == uris[1]:
            return EtaValue(uri, "7", "7", "unsupported", 0, 1)
        return reading(uri)

    mock_client.get_variable.side_effect = get_variable
    coordinator = await setup_auto(
        hass,
        mock_client,
        config_entry,
        [menu_block("Other", uri, (f"Temperatur {index}",)) for index, uri in enumerate(uris)],
    )
    assert [item.uri for item in coordinator.variables] == [uris[2]]
    assert mock_client.get_variable.await_count == 3


async def test_limit_is_applied_before_reading_extra_candidates(hass, mock_client, config_entry):
    coordinator = await setup_auto(
        hass,
        mock_client,
        config_entry,
        [
            menu_block("Living room", GOOD_URI, ROOM_PATH),
            menu_block("Attic", OTHER_URI, ROOM_PATH),
            EtaMenuNode("120/10101", "Circuit", "fub"),
        ],
        max_discovered_variables=1,
    )
    assert len(coordinator.variables) == 1
    mock_client.get_variable.assert_awaited_once_with(GOOD_URI)


@pytest.mark.parametrize("initially_missing", [False, True])
async def test_one_missing_value_and_recovery(
    hass, mock_client, config_entry, caplog, initially_missing
):
    missing = initially_missing

    async def get_variable(uri):
        if uri == OTHER_URI and missing:
            raise EtaTouchResponseError("Variable not available", status=404)
        return reading(uri)

    mock_client.get_variable.side_effect = get_variable
    with caplog.at_level(logging.INFO, logger="custom_components.eta_touch.coordinator"):
        coordinator = await setup_auto(
            hass,
            mock_client,
            config_entry,
            [
                menu_block("Living room", GOOD_URI, ROOM_PATH),
                menu_block("Attic", OTHER_URI, ROOM_PATH),
            ],
        )
        missing = True
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.last_update_success
        assert state_for(hass, config_entry, GOOD_URI).state == "42.5"
        failed = state_for(hass, config_entry, OTHER_URI)
        assert failed.state == STATE_UNAVAILABLE
        if not initially_missing:
            assert failed.attributes["unit_of_measurement"] == "\u00b0C"
        assert caplog.text.count(f"ETA variable {OTHER_URI} is unavailable") == 1
        missing = False
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        recovered = state_for(hass, config_entry, OTHER_URI)
        assert recovered.state == "42.5"
        assert recovered.attributes["unit_of_measurement"] == "\u00b0C"
        assert recovered.attributes["state_class"] == "measurement"
        assert caplog.text.count(f"ETA variable {OTHER_URI} is available again") == 1
        mock_client.get_menu.assert_awaited_once()


@pytest.mark.parametrize(
    "error",
    [
        EtaTouchConnectionError("Offline"),
        EtaTouchResponseError("Busy", status=503),
        EtaTouchResponseError("Unauthorized", status=401),
        EtaTouchResponseError("Forbidden", status=403),
        EtaTouchResponseError("Rate limit", status=429),
    ],
)
async def test_controller_failure_and_recovery(hass, mock_client, config_entry, error):
    coordinator = await setup_auto(
        hass, mock_client, config_entry, [menu_block("Room", GOOD_URI, ROOM_PATH)]
    )
    mock_client.get_variable.side_effect = error
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert state_for(hass, config_entry, GOOD_URI).state == STATE_UNAVAILABLE
    mock_client.get_variable.side_effect = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert state_for(hass, config_entry, GOOD_URI).state == "42.5"
    mock_client.get_menu.assert_awaited_once()


async def test_manual_variables_do_not_fetch_menu(hass, mock_client, config_entry):
    mock_client.get_menu.side_effect = AssertionError("Manual setup must not request the menu")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    mock_client.get_menu.assert_not_awaited()


async def test_menu_failure_retries_discovery(hass, mock_client, config_entry, freezer):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, "auto_discovery": True, "variables": ""}
    )
    mock_client.get_menu.side_effect = EtaTouchConnectionError("Offline")
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.get_menu.side_effect = None
    mock_client.get_menu.return_value = [menu_block("Room", GOOD_URI, ROOM_PATH)]
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.state is ConfigEntryState.LOADED
    assert state_for(hass, config_entry, GOOD_URI).state == "42.5"
    assert mock_client.get_menu.await_count == 2
