"""Select and check the configuration files for one ENVIRONMENT.

pydantic-settings skips a missing file, reports malformed TOML without its file
name and ignores a key whose case does not match a field, so the loader checks
each file before any slice reads it and names the file, table and key at fault.
"""

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contracts.configuration import ConfigurationError

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

_LOWER_SNAKE_CASE = re.compile(r"[a-z][a-z0-9_]*")
# A key may also be dotted lower snake_case segments: a plugin enablement key is the
# plugin's entry-point name, such as "incident.comms" (decisions/configuration.md).
_KEY = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*")


@dataclass(frozen=True)
class TomlConfigurationFiles:
    """The checked base file and ENVIRONMENT file, in load order."""

    environment: str
    paths: tuple[Path, ...]


def load_configuration_files(environment: str, directory: Path | None = None) -> TomlConfigurationFiles:
    """Return base.toml then <environment>.toml from the directory, after checking both."""
    root = directory or CONFIG_DIR
    paths = (root / "base.toml", root / f"{environment}.toml")
    for path in paths:
        _check_file(path)
    return TomlConfigurationFiles(environment=environment, paths=paths)


def _check_file(path: Path) -> None:
    if not path.is_file():
        raise ConfigurationError(f"{path}: configuration file not found")
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(f"{path}: invalid TOML: {error}") from error
    for table, body in document.items():
        if not isinstance(body, Mapping):
            raise ConfigurationError(f"{path}: {table} must be a table naming its settings slice")
        _check_keys(path, (table,), body)


def _check_keys(path: Path, table: tuple[str, ...], body: Mapping[str, Any]) -> None:
    name = ".".join(table)
    if not all(_LOWER_SNAKE_CASE.fullmatch(part) for part in table):
        raise ConfigurationError(f"{path}: [{name}] table names must be lower snake_case")
    for key, value in body.items():
        if isinstance(value, Mapping):
            _check_keys(path, (*table, key), value)
        elif not _KEY.fullmatch(key):
            raise ConfigurationError(
                f"{path}: [{name}] {key}: keys must be lower snake_case, dot-separated for an entry-point name"
            )
