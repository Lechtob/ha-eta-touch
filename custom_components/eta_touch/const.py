"""Constants for ETA Touch."""

from __future__ import annotations

from homeassistant.const import CONF_SCAN_INTERVAL

DOMAIN = "eta_touch"

CONF_VARIABLES = "variables"
CONF_AUTO_DISCOVERY = "auto_discovery"
CONF_MAX_DISCOVERED_VARIABLES = "max_discovered_variables"
DEFAULT_AUTO_DISCOVERY = True
DEFAULT_MAX_DISCOVERED_VARIABLES = 48
DEFAULT_NAME = "ETA Touch"
DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = 30

OPTION_DEFAULTS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_AUTO_DISCOVERY: DEFAULT_AUTO_DISCOVERY,
    CONF_MAX_DISCOVERED_VARIABLES: DEFAULT_MAX_DISCOVERED_VARIABLES,
    CONF_VARIABLES: "",
}

# Only curated measurements receive a translation key. User and device-provided
# names from manual configuration and generic discovery remain untouched.
SENSOR_TRANSLATION_KEYS = {
    "Kessel": "boiler_temperature",
    "Kesseldruck": "boiler_pressure",
    "Abgas": "flue_gas_temperature",
    "Restsauerstoff": "residual_oxygen",
    "Raum": "room_temperature",
    "Raum Soll": "room_target_temperature",
    "Betrieb": "operating_mode",
    "Au\u00dfentemperatur": "outside_temperature",
    "Vorlauf": "flow_temperature",
    "Heizkurve": "heating_curve_temperature",
    "Kessel Soll": "boiler_target_temperature",
    "Kessel unten": "boiler_lower_temperature",
    "Vorlaufregler 1 Angeforderte Temperatur": "flow_controller_1_requested_temperature",
    "Vorlaufregler 1 Angeforderte Leistung": "flow_controller_1_requested_power",
    "Vorlaufregler 2 Angeforderte Temperatur": "flow_controller_2_requested_temperature",
    "Vorlaufregler 2 Angeforderte Leistung": "flow_controller_2_requested_power",
    "Warmwasserspeicher": "hot_water_temperature",
    "Warmwasserspeicher Soll": "hot_water_target_temperature",
    "Registerleistung": "coil_power",
    "Vorlauf Differenz": "flow_temperature_difference",
    "Inhalt Pelletsbeh\u00e4lter": "pellet_container_content",
    "Gesamtverbrauch": "total_pellet_consumption",
    "Verbrauch seit Entaschung": "consumption_since_ash_removal",
    "Verbrauch seit Aschebox leeren": "consumption_since_ash_box_emptied",
    "Abgasgebl\u00e4se": "flue_gas_fan_speed",
    "Luftschieber Stellung": "air_damper_position",
    "Vorlaufmischer 1 Ist Temperatur": "flow_mixer_1_temperature",
    "Vorlaufmischer 1 Position": "flow_mixer_1_position",
    "Vorlaufmischer 2 Ist Temperatur": "flow_mixer_2_temperature",
    "Vorlaufmischer 2 Position": "flow_mixer_2_position",
    "Vorrat": "pellet_stock",
    "Austragleistung": "extraction_rate",
    "Laufzeit Austragschnecke": "extraction_screw_runtime",
    "Volllaststunden": "full_load_runtime",
    "Laufzeit Abgasgebl\u00e4se": "flue_gas_fan_runtime",
    "Z\u00e4hler Heizbetriebe": "heating_cycle_count",
    "Z\u00e4hler Z\u00fcndungen": "ignition_count",
    "Laufzeit Stoker": "stoker_runtime",
    "Laufzeit Entaschung": "ash_removal_runtime",
    "Laufzeit Saugturbine": "suction_turbine_runtime",
}
