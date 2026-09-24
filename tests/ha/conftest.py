"""Fixtures using the real Home Assistant runtime and a mocked ETA transport."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from etatouch_restful import EtaTouchClient, EtaValue
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow loading the integration under test."""


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    client = AsyncMock(spec=EtaTouchClient)
    client.base_url = "http://eta.test:8080"
    client.get_api_version.return_value = "1.2"
    client.get_menu.return_value = []
    client.get_errors.return_value = []
    client.get_variable.return_value = EtaValue(
        uri="40/10021/0/0/12161",
        raw="425",
        str_value="42.5",
        unit="\u00b0C",
        decimal_places=1,
        scale_factor=10,
    )
    with (
        patch("custom_components.eta_touch.config_flow.EtaTouchClient", return_value=client),
        patch("custom_components.eta_touch.coordinator.EtaTouchClient", return_value=client),
    ):
        yield client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Start from a saved v2 installation to exercise migration during real setup."""
    return MockConfigEntry(
        domain="eta_touch",
        title="ETA Touch",
        version=2,
        data={
            "host": "eta.test",
            "port": 8080,
            "scan_interval": 30,
            "auto_discovery": False,
            "variables": "Boiler=40/10021/0/0/12161",
        },
    )
