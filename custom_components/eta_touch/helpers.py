"""Helpers for ETA Touch."""

from __future__ import annotations

from dataclasses import dataclass
import re

_VARIABLE_RE = re.compile(r"^\d+/\d+/\d+/\d+/\d+$")


@dataclass(frozen=True, slots=True)
class EtaConfiguredVariable:
    """A user-configured ETA variable."""

    name: str
    uri: str


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
