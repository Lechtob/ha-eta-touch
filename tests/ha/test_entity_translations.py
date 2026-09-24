"""Translated curated names without changing user names or entity identities."""

import json
from pathlib import Path

import pytest
from etatouch_restful import EtaMenuNode
from homeassistant.helpers import entity_registry as er

from custom_components.eta_touch.const import DOMAIN, SENSOR_TRANSLATION_KEYS
from custom_components.eta_touch.coordinator import CURATED_DISCOVERY_VARIABLES

URI = "112/9001/0/0/2293"
COMPONENT = Path(__file__).parents[2] / "custom_components" / DOMAIN


def test_translation_catalog_is_complete():
    source = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    english = json.loads((COMPONENT / "translations/en.json").read_text(encoding="utf-8"))
    german = json.loads((COMPONENT / "translations/de.json").read_text(encoding="utf-8"))
    assert set(SENSOR_TRANSLATION_KEYS) == {item.name for item in CURATED_DISCOVERY_VARIABLES}
    keys = set(SENSOR_TRANSLATION_KEYS.values())
    assert len(keys) == len(SENSOR_TRANSLATION_KEYS)
    assert set(source["entity"]["sensor"]) == keys
    assert set(german["entity"]["sensor"]) == keys
    assert english["entity"] == source["entity"]
    for name, key in SENSOR_TRANSLATION_KEYS.items():
        assert german["entity"]["sensor"][key]["name"] == name
        assert source["entity"]["sensor"][key]["name"]


def block_with_path(path):
    node = EtaMenuNode(URI, path[-1], "var")
    for name in reversed(path[:-1]):
        node = EtaMenuNode("", name, "object", (node,))
    return EtaMenuNode("112/9001", "My room", "fub", (node,))


async def setup_discovery(hass, mock_client, config_entry, path):
    mock_client.get_menu.return_value = [block_with_path(path)]
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, "auto_discovery": True, "variables": ""}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    return registry.async_get_entity_id(
        "sensor", DOMAIN, f"{config_entry.entry_id}_{URI.replace('/', '_')}"
    )


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize(
    "path,key,english,german",
    [
        (
            ("Eing\u00e4nge", "Raumf\u00fchler", "Raum Ist"),
            "room_temperature",
            "Room temperature",
            "Raum",
        ),
        (
            ("Z\u00e4hlerst\u00e4nde", "Gesamtverbrauch"),
            "total_pellet_consumption",
            "Total pellet consumption",
            "Gesamtverbrauch",
        ),
        (("Sonstiges", "Betrieb"), "operating_mode", "Operating mode", "Betrieb"),
    ],
)
async def test_curated_and_binary_names(
    hass, mock_client, config_entry, language, path, key, english, german
):
    hass.config.language = language
    config_entry.add_to_hass(hass)
    entity_id = await setup_discovery(hass, mock_client, config_entry, path)
    assert config_entry.runtime_data.variables[0].translation_key == key
    expected = german if language == "de" else english
    assert hass.states.get(entity_id).attributes["friendly_name"] == f"ETA My room {expected}"
    assert er.async_get(hass).async_get(entity_id).translation_key == key
    binary_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{config_entry.entry_id}_active_errors"
    )
    error_name = "Aktive Fehler" if language == "de" else "Active errors"
    assert hass.states.get(binary_id).attributes["friendly_name"] == f"ETA Touch {error_name}"


@pytest.mark.parametrize("language", ["en", "de"])
async def test_generic_device_name_is_not_translated(hass, mock_client, config_entry, language):
    hass.config.language = language
    config_entry.add_to_hass(hass)
    entity_id = await setup_discovery(hass, mock_client, config_entry, ("My custom measurement",))
    assert config_entry.runtime_data.variables[0].translation_key is None
    assert (
        hass.states.get(entity_id).attributes["friendly_name"]
        == "ETA My room My custom measurement"
    )


@pytest.mark.parametrize("language", ["en", "de"])
async def test_manual_name_is_not_translated(hass, mock_client, config_entry, language):
    hass.config.language = language
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, "variables": f"Raum={URI}"}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{config_entry.entry_id}_{URI.replace('/', '_')}"
    )
    assert config_entry.runtime_data.variables[0].translation_key is None
    assert hass.states.get(entity_id).attributes["friendly_name"] == "ETA ETA Touch Raum"


async def test_hidden_overview_name_is_translated(hass, mock_client, config_entry):
    hass.config.language = "en"
    mock_client.get_menu.return_value = [EtaMenuNode("120/10101", "My circuit", "fub")]
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, "auto_discovery": True, "variables": ""}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{config_entry.entry_id}_120_10101_0_0_12241"
    )
    assert (
        hass.states.get(entity_id).attributes["friendly_name"] == "ETA My circuit Flow temperature"
    )


@pytest.mark.parametrize("custom_name", [None, "My existing sensor"])
async def test_existing_registry_identity_is_retained(hass, mock_client, config_entry, custom_name):
    hass.config.language = "en"
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    existing = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{config_entry.entry_id}_{URI.replace('/', '_')}",
        suggested_object_id="legacy_room",
        config_entry=config_entry,
        original_name="Raum",
        name=custom_name,
    )
    entity_id = await setup_discovery(
        hass, mock_client, config_entry, ("Eing\u00e4nge", "Raumf\u00fchler", "Raum Ist")
    )
    assert entity_id == existing.entity_id == "sensor.legacy_room"
    current = registry.async_get(entity_id)
    assert current.id == existing.id
    assert current.unique_id == existing.unique_id
    assert current.name == custom_name
    assert hass.states.get(entity_id).state == "42.5"
    if custom_name:
        assert hass.states.get(entity_id).attributes["friendly_name"] == custom_name
