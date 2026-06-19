"""Helpers for ETA Touch."""

from __future__ import annotations

import re
from dataclasses import dataclass

_VARIABLE_RE = re.compile(r"^\d+/\d+/\d+/\d+/\d+$")
_DISCOVERY_NAME_OMIT_PARTS = frozenset(
    {
        "Ausgänge",
        "Eingänge",
        "Heizkreis",
        "Raum",
        "Raumfühler",
    }
)


@dataclass(frozen=True, slots=True)
class EtaConfiguredVariable:
    """A user-configured ETA variable."""

    name: str
    uri: str
    function_block: str | None = None
    path: tuple[str, ...] = ()
    is_diagnostic: bool = False


@dataclass(frozen=True, slots=True)
class EtaControlVariable:
    """A writable ETA variable exposed as a Home Assistant control."""

    name: str
    function_block: str
    value_kind: str
    read_uri: str | None = None
    write_uri: str | None = None
    read_full_name: str | None = None
    write_full_name: str | None = None
    unit: str | None = None
    scale_factor: float = 1.0
    native_min_value: float | None = None
    native_max_value: float | None = None
    native_step: float | None = None
    on_value: str | int | float | None = None
    off_value: str | int | float | None = None


def parse_variable_lines(value: str) -> tuple[EtaConfiguredVariable, ...]:
    """Parse one configured variable per line.

    Supported formats:
    - 112/10021/0/0/12112
    - Ash removal key=112/10021/0/0/12112
    """

    variables: list[EtaConfiguredVariable] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "=" in line:
            name, uri = [part.strip() for part in line.split("=", 1)]
        else:
            uri = line
            name = uri
        try:
            uri = validate_variable_uri(uri)
        except ValueError as err:
            raise ValueError(f"Invalid ETA variable line: {raw_line}") from err
        if not name:
            raise ValueError(f"Invalid ETA variable line: {raw_line}")
        variables.append(EtaConfiguredVariable(name=name, uri=uri))
    return tuple(variables)


def validate_variable_uri(uri: str) -> str:
    """Validate and normalize an ETA variable URI."""

    normalized = uri.strip().strip("/")
    if not _VARIABLE_RE.match(normalized):
        raise ValueError(f"Invalid ETA variable URI: {uri}")
    return normalized


def format_discovered_variable_name(path: tuple[str, ...]) -> str:
    """Format an ETA menu path into a compact Home Assistant entity name."""

    function_block = infer_function_block(path)
    parts = [
        part
        for part in path
        if part
        and part != function_block
        and part not in _DISCOVERY_NAME_OMIT_PARTS
    ]
    compact_parts: list[str] = []
    for part in parts:
        if compact_parts and compact_parts[-1] == part:
            continue
        compact_parts.append(part)
    if compact_parts:
        return " ".join(compact_parts)
    return path[-1] if path else ""


def infer_function_block(path: tuple[str, ...]) -> str | None:
    """Infer the ETA functional block from a menu path."""

    return path[0] if path else None


def normalize_function_block(function_block: str | None) -> str:
    """Return a display-safe functional block name."""

    return function_block or "ETA Touch"


def is_diagnostic_variable(path: tuple[str, ...], name: str) -> bool:
    """Return whether a discovered variable should be categorized as diagnostic."""

    full_name = " > ".join((*path, name))
    diagnostic_parts = {
        "Abgasgebläse",
        "Austragung",
        "Luftschieber",
        "Position",
        "Restsauerstoff",
        "Strom",
        "Vorlaufmischer",
        "Zählerstände",
    }
    return any(part in full_name for part in diagnostic_parts)
