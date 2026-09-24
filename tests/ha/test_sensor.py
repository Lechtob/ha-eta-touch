"""Sensor semantics through real HA setup and state updates."""

import pytest
from etatouch_restful import EtaMenuNode, EtaTouchResponseError, EtaValue
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from custom_components.eta_touch.const import DOMAIN

URI = "112/9001/0/0/2293"


def reading(unit, raw="25", display="25"):
    return EtaValue(URI, raw, display, unit, 0, 1)


async def setup_sensor(hass, mock_client, config_entry, unit, path=(), raw="25", display="25"):
    """Discover a semantic path, or set up a manual sensor when none is supplied."""
    mock_client.get_variable.return_value = reading(unit, raw, display)
    data = {**config_entry.data, "variables": f"Custom name={URI}"}
    if path:
        node = EtaMenuNode(URI, path[-1], "var")
        for name in reversed(path[:-1]):
            node = EtaMenuNode("", name, "object", (node,))
        mock_client.get_menu.return_value = [EtaMenuNode("112/9001", "My block", "fub", (node,))]
        data.update(auto_discovery=True, variables="")
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, data=data)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{config_entry.entry_id}_{URI.replace('/', '_')}"
    )
    assert entity_id is not None
    return entity_id, config_entry.runtime_data


@pytest.mark.parametrize(
    ("unit", "device_class"),
    [
        ("\u00b0C", "temperature"),
        ("\u00b0F", "temperature"),
        ("K", "temperature"),
        ("bar", "pressure"),
        ("mbar", "pressure"),
        ("Pa", "pressure"),
        ("W", "power"),
        ("kW", "power"),
        ("V", "voltage"),
        ("A", "current"),
        ("mA", "current"),
        ("kg", "weight"),
        ("s", "duration"),
        ("%", None),
        ("kg/h", None),
        ("U/min", None),
        ("rpm", None),
    ],
)
async def test_measurement_classes(hass, mock_client, config_entry, unit, device_class):
    entity_id, _ = await setup_sensor(hass, mock_client, config_entry, unit)
    state = hass.states.get(entity_id)
    assert state.attributes.get("device_class") == device_class
    assert state.attributes["state_class"] == "measurement"
    assert state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)


@pytest.mark.parametrize(
    ("path", "unit", "state_class"),
    [
        (("Z\u00e4hlerst\u00e4nde", "Gesamtverbrauch"), "kg", "total"),
        (("Z\u00e4hlerst\u00e4nde", "Verbrauch seit Entaschung"), "kg", "total_increasing"),
        (("Z\u00e4hlerst\u00e4nde", "Verbrauch seit Aschebox leeren"), "kg", "total_increasing"),
        (("Z\u00e4hlerst\u00e4nde", "Volllaststunden"), "s", "total"),
        (("Z\u00e4hlerst\u00e4nde", "Laufzeit Abgasgebl\u00e4se"), "s", "total"),
        (("Z\u00e4hlerst\u00e4nde", "Laufzeit Stoker"), "s", "total"),
        (("Z\u00e4hlerst\u00e4nde", "Laufzeit Entaschung"), "s", "total"),
        (("Z\u00e4hlerst\u00e4nde", "Laufzeit Saugturbine"), "s", "total"),
        (("Z\u00e4hlerst\u00e4nde", "Z\u00e4hler Heizbetriebe"), "", "total"),
        (("Z\u00e4hlerst\u00e4nde", "Z\u00e4hler Z\u00fcndungen"), "", "total"),
        (("Austragung", "Laufzeit Austragschnecke"), "s", "total"),
        (("Z\u00e4hlerst\u00e4nde", "Inhalt Pelletsbeh\u00e4lter"), "kg", "measurement"),
        (("Vorrat",), "kg", "measurement"),
    ],
)
async def test_counter_and_stock_semantics(
    hass, mock_client, config_entry, path, unit, state_class
):
    entity_id, _ = await setup_sensor(hass, mock_client, config_entry, unit, path)
    state = hass.states.get(entity_id)
    assert state.attributes["state_class"] == state_class
    assert state.attributes.get("device_class") == {"kg": "weight", "s": "duration"}.get(unit)
    assert float(state.state) == 25


async def test_counter_requires_matching_unit(hass, mock_client, config_entry):
    entity_id, _ = await setup_sensor(
        hass, mock_client, config_entry, "\u00b0C", ("Z\u00e4hlerst\u00e4nde", "Gesamtverbrauch")
    )
    state = hass.states.get(entity_id)
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["state_class"] == "measurement"


async def test_manual_name_does_not_enable_counter(hass, mock_client, config_entry):
    entity_id, _ = await setup_sensor(hass, mock_client, config_entry, "kg")
    er.async_get(hass).async_update_entity(entity_id, name="Gesamtverbrauch")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["state_class"] == "measurement"


@pytest.mark.parametrize(("raw", "display"), [("1800", "30m"), ("3.0e+3", "50m")])
async def test_runtime_seconds(hass, mock_client, config_entry, raw, display):
    entity_id, _ = await setup_sensor(
        hass,
        mock_client,
        config_entry,
        "s",
        ("Z\u00e4hlerst\u00e4nde", "Volllaststunden"),
        raw,
        display,
    )
    state = hass.states.get(entity_id)
    assert float(state.state) == float(raw)
    assert state.attributes["unit_of_measurement"] == "s"
    assert state.attributes["device_class"] == "duration"
    assert state.attributes["state_class"] == "total"


@pytest.mark.parametrize("path", [(), ("Warmwasserspeicher", "Vorlauf", "Differenz")])
async def test_temperature_conversion(hass, mock_client, config_entry, path):
    hass.config.units = US_CUSTOMARY_SYSTEM
    entity_id, _ = await setup_sensor(hass, mock_client, config_entry, "\u00b0C", path)
    if path:
        # HA leaves deltas in the native unit until the user selects a display unit.
        assert hass.states.get(entity_id).attributes["unit_of_measurement"] == "\u00b0C"
        er.async_get(hass).async_update_entity_options(
            entity_id, "sensor", {"unit_of_measurement": "\u00b0F"}
        )
        await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["device_class"] == ("temperature_delta" if path else "temperature")
    assert state.attributes["unit_of_measurement"] == "\u00b0F"
    assert float(state.state) == (45 if path else 77)


async def test_text_status_has_no_numeric_metadata(hass, mock_client, config_entry):
    entity_id, _ = await setup_sensor(
        hass, mock_client, config_entry, "", raw="1800", display="Bereit"
    )
    state = hass.states.get(entity_id)
    assert state.state == "Bereit"
    assert "state_class" not in state.attributes
    assert "device_class" not in state.attributes
    assert "unit_of_measurement" not in state.attributes


@pytest.mark.parametrize(
    "unit,path",
    [
        ("s", ("Z\u00e4hlerst\u00e4nde", "Volllaststunden")),
        ("", ("Z\u00e4hlerst\u00e4nde", "Z\u00e4hler Z\u00fcndungen")),
    ],
)
async def test_counter_metadata_survives_invalid_values_and_outages(
    hass, mock_client, config_entry, unit, path
):
    entity_id, coordinator = await setup_sensor(hass, mock_client, config_entry, unit, path)
    metadata = {
        key: value
        for key, value in hass.states.get(entity_id).attributes.items()
        if key in ("unit_of_measurement", "device_class", "state_class")
    }
    for raw, display in [("bad", "---"), ("nan", "nan"), ("inf", "inf")]:
        mock_client.get_variable.return_value = reading(unit, raw, display)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNKNOWN
        assert metadata.items() <= state.attributes.items()
    mock_client.get_variable.side_effect = EtaTouchResponseError("Missing", status=404)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE
    assert metadata.items() <= state.attributes.items()
    mock_client.get_variable.side_effect = None
    mock_client.get_variable.return_value = reading(unit, "30", "30")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert float(state.state) == 30
    assert metadata.items() <= state.attributes.items()


async def test_maintenance_counter_reset(hass, mock_client, config_entry):
    entity_id, coordinator = await setup_sensor(
        hass,
        mock_client,
        config_entry,
        "kg",
        ("Z\u00e4hlerst\u00e4nde", "Verbrauch seit Entaschung"),
    )
    for value in (26, 0, 2):
        mock_client.get_variable.return_value = reading("kg", str(value), str(value))
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert float(state.state) == value
        assert state.attributes["state_class"] == "total_increasing"


async def test_initially_missing_counter_gets_metadata_on_recovery(hass, mock_client, config_entry):
    mock_client.get_variable.side_effect = EtaTouchResponseError("Missing", status=404)
    entity_id, coordinator = await setup_sensor(
        hass, mock_client, config_entry, "kg", ("Z\u00e4hlerst\u00e4nde", "Gesamtverbrauch")
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    mock_client.get_variable.side_effect = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert float(state.state) == 25
    assert state.attributes["device_class"] == "weight"
    assert state.attributes["state_class"] == "total"
    assert state.attributes["unit_of_measurement"] == "kg"
