"""Keep the published dependency and supported HA versions aligned with CI."""

import json
from importlib.metadata import version
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("filename", ["requirements_test.txt", "requirements_test_min.txt"])
def test_test_dependency_matches_manifest(filename):
    manifest = json.loads((ROOT / "custom_components/eta_touch/manifest.json").read_text())
    requirement = Requirement(manifest["requirements"][0])
    dependencies = [
        Requirement(line)
        for line in (ROOT / filename).read_text().splitlines()
        if line and not line.startswith("#")
    ]
    assert next(item for item in dependencies if item.name == requirement.name) == requirement
    assert version(requirement.name) in requirement.specifier


def test_test_runtime_meets_declared_minimum():
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert Version(version("homeassistant")) >= Version(hacs["homeassistant"])
