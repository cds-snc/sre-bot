"""Configuration contract: the settings-slice base and the files it reads.

Every owner's settings slice derives from ConfigurationSlice and names its own
table. The host loads the base file and the ENVIRONMENT file, checks them, and
installs them here in lifespan's configuration phase before any slice builds
(decisions/configuration.md); a slice built earlier fails instead of silently
running on defaults. A value resolves from, highest first: constructor
arguments, the process environment, the .env file, the configuration files
(the environment file over the base file, key by key), the field default.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Protocol

from pydantic import ValidationError
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class ConfigurationError(Exception):
    """Invalid or missing configuration; the message names the file, table and key to fix."""


class ConfigurationFiles(Protocol):
    """The configuration files for one environment, base file first."""

    @property
    def environment(self) -> str: ...

    @property
    def paths(self) -> tuple[Path, ...]: ...


@dataclass
class _Installed:
    files: ConfigurationFiles | None = None


_installed = _Installed()


def install_configuration_files(files: ConfigurationFiles) -> None:
    """Install the checked files every slice reads; a later install replaces them."""
    _installed.files = files


def uninstall_configuration_files() -> None:
    """Remove the installed files, so building a slice fails until the next install."""
    _installed.files = None


def installed_configuration_files() -> ConfigurationFiles:
    """Return the installed files, or fail when the configuration phase has not run."""
    if _installed.files is None:
        raise ConfigurationError("configuration files not loaded: lifespan's configuration phase installs them")
    return _installed.files


def _read(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


class _OwnFieldsOnly(PydanticBaseSettingsSource):
    """Pass on only the slice's own fields from a source shared by every slice.

    The .env file holds every slice's names, and pydantic-settings reports each
    unrelated one as an extra input under extra="forbid", which guards the table.
    """

    def __init__(self, settings_cls: type[BaseSettings], source: PydanticBaseSettingsSource) -> None:
        super().__init__(settings_cls)
        self._source = source

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self._source.get_field_value(field, field_name)

    def __call__(self) -> dict[str, Any]:
        return {key: value for key, value in self._source().items() if key in self.settings_cls.model_fields}


class ConfigurationSlice(BaseSettings):
    """Base for a settings slice that reads one table of the configuration files.

    A slice sets ``toml_table_header=("<table>",)`` and ``env_prefix="<TABLE>__"``
    in its model_config; its fields are lower snake_case.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="forbid",
    )

    _table: ClassVar[str]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        header = cls.model_config.get("toml_table_header", ())
        if len(header) != 1:
            raise TypeError(f"{cls.__name__} must name exactly one table in toml_table_header")
        expected_prefix = f"{header[0].upper()}__"
        if cls.model_config.get("env_prefix") != expected_prefix:
            raise TypeError(f"{cls.__name__} must set env_prefix={expected_prefix!r} to match its [{header[0]}] table")
        cls._table = header[0]

    def __init__(self, **values: Any) -> None:
        try:
            super().__init__(**values)
        except ValidationError as error:
            located = _locate_file_errors(type(self), error)
            if not located:
                raise
            raise ConfigurationError("; ".join(located)) from error

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        if _installed.files is None:
            raise ConfigurationError(f"{settings_cls.__name__}: configuration files not loaded before the slice was built")
        paths = _installed.files.paths
        if cls._table not in _read(paths[0]):
            raise ConfigurationError(f"{paths[0]}: [{cls._table}] missing; the base file holds every slice's table")
        toml_settings = TomlConfigSettingsSource(settings_cls, toml_file=list(paths), deep_merge=True)
        own_dotenv_settings = _OwnFieldsOnly(settings_cls, dotenv_settings)
        return init_settings, env_settings, own_dotenv_settings, toml_settings, file_secret_settings


def _locate_file_errors(slice_cls: type[ConfigurationSlice], error: ValidationError) -> list[str]:
    """Name the last installed file setting each failing key of the slice's table."""
    if _installed.files is None:
        return []
    tables = [(path, _read(path).get(slice_cls._table, {})) for path in _installed.files.paths]
    located: list[str] = []
    for detail in error.errors():
        key = str(detail["loc"][0]) if detail["loc"] else ""
        files = [path for path, table in tables if key in table]
        if files:
            located.append(f"{files[-1]}: [{slice_cls._table}] {key}: {detail['msg']}")
    return located
