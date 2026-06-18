import importlib.util
import sys
from pathlib import Path

HELPERS_PATH = (
    Path(__file__).parents[1] / "custom_components" / "eta_touch" / "helpers.py"
)
spec = importlib.util.spec_from_file_location("eta_touch_helpers", HELPERS_PATH)
assert spec is not None
helpers = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["eta_touch_helpers"] = helpers
spec.loader.exec_module(helpers)

parse_variable_lines = helpers.parse_variable_lines
validate_variable_uri = helpers.validate_variable_uri
format_discovered_variable_name = helpers.format_discovered_variable_name


def test_parse_variable_lines_accepts_named_and_plain_variables() -> None:
    variables = parse_variable_lines(
        """
        Kesseltemperatur=112/10021/0/0/12150
        112/10021/0/0/12112
        """
    )

    assert variables[0].name == "Kesseltemperatur"
    assert variables[0].uri == "112/10021/0/0/12150"
    assert variables[1].name == "112/10021/0/0/12112"


def test_validate_variable_uri_normalizes_slashes() -> None:
    assert validate_variable_uri("/112/10021/0/0/12112/") == "112/10021/0/0/12112"


def test_format_discovered_variable_name_compacts_eta_paths() -> None:
    assert (
        format_discovered_variable_name(("EG", "Eingänge", "Raumfühler", "Raum Ist"))
        == "EG Raum Ist"
    )
    assert (
        format_discovered_variable_name(("WW", "Warmwasserspeicher", "Warmwasserspeicher"))
        == "WW Warmwasserspeicher"
    )
