"""Exercise diagnostics downloads, privacy and cached failure snapshots."""

import json
from http import HTTPStatus
from unittest.mock import patch

import pytest
from etatouch_restful import (
    EtaError,
    EtaMenuNode,
    EtaTouchConnectionError,
    EtaTouchResponseError,
    EtaValue,
)
from homeassistant.components.diagnostics import REDACTED
from homeassistant.setup import async_setup_component

from custom_components.eta_touch.diagnostics import async_get_config_entry_diagnostics
from custom_components.eta_touch.helpers import EtaConfiguredVariable

URI = "112/9001/0/0/2293"
OTHER_URI = "112/9002/0/0/2293"


async def setup_entry(hass, mock_client, config_entry):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        title="Private household",
        unique_id="PRIVATE-SERIAL",
        data={
            **config_entry.data,
            "host": "private-boiler.local",
            "name": "Private controller",
            "variables": f"Private room={URI}\nPrivate status={OTHER_URI}",
            "password": "private-password",
            "future_credentials": {"token": "private-token"},
        },
        options={"future_secret": "private-option"},
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry.runtime_data


async def download(hass, hass_client, config_entry):
    assert await async_setup_component(hass, "diagnostics", {})
    await hass.async_block_till_done()
    client = await hass_client()
    response = await client.get(f"/api/diagnostics/config_entry/{config_entry.entry_id}")
    assert response.status == HTTPStatus.OK
    assert response.content_type == "application/json"
    assert "attachment" in response.headers["Content-Disposition"]
    return await response.json()


async def test_download_redacts_sensitive_data_without_io(
    hass, hass_client, mock_client, config_entry
):
    mock_client.get_variable.side_effect = lambda uri: (
        EtaValue(uri, "425", "private-display", "\u00b0C", 1, 10)
        if uri == URI
        else EtaValue(uri, "private-raw", "private-status", "", 0, 1)
    )
    mock_client.get_errors.return_value = [
        EtaError(
            "private-fub-uri",
            "private-fub-name",
            "private-message",
            "private-priority",
            "private-time",
            "private-description",
        )
    ]
    coordinator = await setup_entry(hass, mock_client, config_entry)
    snapshot = coordinator.data
    original_data = dict(config_entry.data)
    mock_client.reset_mock()
    payload = await download(hass, hass_client, config_entry)
    encoded = json.dumps(payload, allow_nan=False)
    assert "private" not in encoded.lower()
    data = payload["data"]
    assert data["configuration"] == {
        "version": 3,
        "minor_version": 1,
        "state": "loaded",
        "scan_interval": 30,
        "auto_discovery": False,
        "max_discovered_variables": 48,
        "manual_variables": True,
    }
    assert data["coordinator"] == {
        "last_update_success": True,
        "last_exception_type": None,
        "has_snapshot": True,
        "data_is_stale": False,
        "configured_variable_count": 2,
    }
    assert data["active_error_count"] == 1
    assert data["variables"][0] == {
        "uri": URI,
        "block": "block_1",
        "diagnostic": False,
        "available": True,
        "has_cached_value": True,
        "value": {
            "raw": "425",
            "unit": "\u00b0C",
            "native_value": 42.5,
            "decimal_places": 1,
            "scale_factor": 10,
            "advanced_text_offset": None,
        },
    }
    assert data["variables"][1]["value"]["raw"] == REDACTED
    assert data["variables"][1]["value"]["native_value"] is None
    assert coordinator.data is snapshot
    assert dict(config_entry.data) == original_data
    assert mock_client.mock_calls == []


async def test_discovered_blocks_are_aliased(hass, mock_client, config_entry):
    mock_client.get_menu.return_value = [
        EtaMenuNode(
            prefix,
            name,
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
                                EtaMenuNode(f"{prefix}/0/0/2293", "Raum Ist", "var"),
                                EtaMenuNode(f"{prefix}/0/0/2294", "Raum Soll", "var"),
                            ),
                        ),
                    ),
                ),
            ),
        )
        for prefix, name in [("112/9001", "Private bedroom"), ("112/9002", "Private office")]
    ]
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, "auto_discovery": True, "variables": ""}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.reset_mock()
    data = await async_get_config_entry_diagnostics(hass, config_entry)
    assert "private" not in json.dumps(data).lower()
    assert {item["uri"]: item["block"] for item in data["variables"]} == {
        "112/9001/0/0/2293": "block_1",
        "112/9001/0/0/2294": "block_1",
        "112/9002/0/0/2293": "block_2",
        "112/9002/0/0/2294": "block_2",
    }
    assert mock_client.mock_calls == []


async def test_partial_failure_and_offline_snapshot(hass, hass_client, mock_client, config_entry):
    async def get_variable(uri):
        if uri == OTHER_URI:
            raise EtaTouchResponseError("private-variable-error", status=404)
        return EtaValue(uri, "42", "42", "\u00b0C", 0, 1)

    mock_client.get_variable.side_effect = get_variable
    coordinator = await setup_entry(hass, mock_client, config_entry)
    data = (await download(hass, hass_client, config_entry))["data"]
    assert data["variables"][0]["available"]
    assert not data["variables"][1]["available"]
    assert data["variables"][1]["value"] is None
    assert not data["coordinator"]["data_is_stale"]

    mock_client.get_variable.side_effect = EtaTouchConnectionError("http://private-boiler.local")
    await coordinator.async_refresh()
    mock_client.reset_mock()
    data = (await download(hass, hass_client, config_entry))["data"]
    assert data["coordinator"]["data_is_stale"]
    assert not data["coordinator"]["last_update_success"]
    assert data["coordinator"]["last_exception_type"] == "UpdateFailed"
    assert not any(item["available"] for item in data["variables"])
    assert data["variables"][0]["has_cached_value"]
    assert not data["variables"][1]["has_cached_value"]
    assert "private" not in json.dumps(data).lower()
    assert mock_client.mock_calls == []


@pytest.mark.parametrize("failed_setup", [False, True])
async def test_no_runtime_data(hass, mock_client, config_entry, failed_setup):
    if failed_setup:
        mock_client.get_variable.side_effect = EtaTouchConnectionError("private-host")
        config_entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
    mock_client.reset_mock()
    data = await async_get_config_entry_diagnostics(hass, config_entry)
    assert data["coordinator"] is None
    assert data["active_error_count"] is None
    assert data["variables"] == []
    assert data["configuration"]["state"] == ("setup_retry" if failed_setup else "not_loaded")
    assert mock_client.mock_calls == []


@pytest.mark.parametrize("raw,unit", [("nan", "s"), ("inf", "s"), ("secret", "secret-unit")])
async def test_invalid_reading_is_json_safe(hass, mock_client, config_entry, raw, unit):
    mock_client.get_variable.return_value = EtaValue(URI, raw, "secret-display", unit, 0, 1)
    await setup_entry(hass, mock_client, config_entry)
    data = await async_get_config_entry_diagnostics(hass, config_entry)
    encoded = json.dumps(data, allow_nan=False)
    assert "secret" not in encoded
    assert data["variables"][0]["value"]["raw"] == REDACTED
    assert data["variables"][0]["value"]["native_value"] is None


async def test_scientific_duration_encoding_preserved(hass, mock_client, config_entry):
    mock_client.get_variable.return_value = EtaValue(URI, "3.0e+3", "50m", "s", 0, 1)
    await setup_entry(hass, mock_client, config_entry)
    data = await async_get_config_entry_diagnostics(hass, config_entry)
    assert data["variables"][0]["value"]["raw"] == "3.0e+3"
    assert data["variables"][0]["value"]["native_value"] == 3000
    assert "50m" not in json.dumps(data)


async def test_unloaded_snapshot_is_not_reported_as_current(hass, mock_client, config_entry):
    await setup_entry(hass, mock_client, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    mock_client.reset_mock()
    data = await async_get_config_entry_diagnostics(hass, config_entry)
    assert data["configuration"]["state"] == "not_loaded"
    if data["coordinator"] is not None:
        assert data["coordinator"]["data_is_stale"]
    assert not any(item["available"] for item in data["variables"])
    assert mock_client.mock_calls == []


async def test_missing_snapshot_is_not_reported_as_current(hass, mock_client, config_entry):
    coordinator = await setup_entry(hass, mock_client, config_entry)
    mock_client.reset_mock()
    with patch.object(coordinator, "data", None):
        data = await async_get_config_entry_diagnostics(hass, config_entry)
    assert not data["coordinator"]["has_snapshot"]
    assert data["coordinator"]["data_is_stale"]
    assert data["active_error_count"] is None
    assert len(data["variables"]) == 2
    for variable in data["variables"]:
        assert not variable["available"]
        assert not variable["has_cached_value"]
        assert variable["value"] is None
    assert mock_client.mock_calls == []


async def test_untrusted_uri_is_redacted(hass, mock_client, config_entry):
    coordinator = await setup_entry(hass, mock_client, config_entry)
    mock_client.reset_mock()
    with patch.object(
        coordinator, "variables", [EtaConfiguredVariable("Private room", "private-uri")]
    ):
        data = await async_get_config_entry_diagnostics(hass, config_entry)
    assert data["variables"][0]["uri"] == REDACTED
    assert "private" not in json.dumps(data).lower()
    assert mock_client.mock_calls == []
