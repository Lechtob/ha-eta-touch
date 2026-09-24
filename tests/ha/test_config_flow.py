"""Exercise the actual Home Assistant flow manager, including error recovery."""

from unittest.mock import patch

import pytest
import voluptuous as vol
from etatouch_restful import EtaTouchConnectionError, EtaTouchResponseError
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eta_touch.const import DOMAIN


@pytest.mark.parametrize("name", [None, "", "My ETA"])
async def test_user_flow(hass, mock_client, name):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    data = {"host": " ETA.TEST. "}
    if name is not None:
        data["name"] = name
    with patch("custom_components.eta_touch.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == (name or "ETA Touch")
    assert result["data"]["host"] == "eta.test"
    assert result["data"]["port"] == 8080
    assert result["result"].unique_id is None
    assert result["result"].version == 2
    mock_client.get_api_version.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (EtaTouchConnectionError("offline"), "cannot_connect"),
        (EtaTouchResponseError("bad XML"), "invalid_response"),
        (RuntimeError("unexpected"), "unknown"),
        (ValueError("bad API data"), "unknown"),
    ],
)
async def test_connection_errors_recover(hass, mock_client, error, expected):
    mock_client.get_api_version.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"host": "eta.test", "port": 8080},
    )
    assert result["errors"] == {"base": expected}
    mock_client.get_api_version.side_effect = None
    with patch("custom_components.eta_touch.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "eta.test", "port": 8080}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_invalid_variables_recover(hass, mock_client):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"host": "eta.test", "port": 8080, "variables": "not-a-uri"},
    )
    assert result["errors"] == {"variables": "invalid_variables"}
    mock_client.get_api_version.assert_not_awaited()
    with patch("custom_components.eta_touch.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "eta.test", "port": 8080, "variables": ""}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("legacy", [False, True])
async def test_duplicate_endpoint(hass, mock_client, legacy):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1 if legacy else 2,
        unique_id="ETA.TEST:8080" if legacy else None,
        data={"host": "ETA.TEST"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"host": "eta.test", "port": 8080},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.get_api_version.assert_not_awaited()


@pytest.mark.parametrize(("host", "port"), [("other.test", 8080), ("eta.test", 8081)])
async def test_different_endpoint_allowed(hass, mock_client, host, port):
    MockConfigEntry(domain=DOMAIN, data={"host": "eta.test", "port": 8080}).add_to_hass(hass)
    with patch("custom_components.eta_touch.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={"host": host, "port": port},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("host", " "),
        ("port", 0),
        ("port", 65536),
        ("scan_interval", 0),
        ("scan_interval", 9),
        ("scan_interval", 3601),
        ("max_discovered_variables", 0),
        ("max_discovered_variables", 201),
    ],
)
async def test_invalid_form_values(hass, field, value):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    with pytest.raises(vol.Invalid):
        result["data_schema"]({"host": "eta.test", field: value})
