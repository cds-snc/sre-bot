"""Plugin enablement settings slice.

Owns which plugins this deployment runs, read from one [plugins.<area>] table
per product area (decisions/product-scope.md), each mapping an entry-point name
to a boolean (decisions/plugins.md). The host never names a plugin in code: the
configuration phase checks the keys against the installed entry points
(server/configuration/host_configuration.py), and the plugin loader blocks the
disabled names before loading, so a disabled plugin is never imported.
"""

from collections import defaultdict
from collections.abc import Iterable
from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationError, ConfigurationSlice


class PluginsSettings(ConfigurationSlice):
    """Enablement keys by product area: entry-point name to enabled."""

    model_config = SettingsConfigDict(toml_table_header=("plugins",), env_prefix="PLUGINS__")

    incident_response: dict[str, bool] = Field(description="Incident response plugins, by entry-point name.")
    cloud_operations: dict[str, bool] = Field(description="Cloud operations plugins, by entry-point name.")
    platform_access: dict[str, bool] = Field(description="Platform access plugins, by entry-point name.")
    workplace_utilities: dict[str, bool] = Field(description="Workplace utilities plugins, by entry-point name.")

    def areas(self) -> dict[str, dict[str, bool]]:
        """Return each area's table, keyed by area name."""
        return {area: getattr(self, area) for area in type(self).model_fields}

    def disabled(self) -> frozenset[str]:
        """Return the entry-point names set to false in any area."""
        return frozenset(name for keys in self.areas().values() for name, enabled in keys.items() if not enabled)


def check_plugin_enablement(settings: PluginsSettings, installed: Iterable[str]) -> None:
    """Fail when the keys and the installed entry points differ, naming every name to fix.

    Raises:
        ConfigurationError: An installed entry point has no key, a key names no installed
            entry point, or a name sits under two areas.
    """
    installed_names = set(installed)
    areas_by_name: defaultdict[str, list[str]] = defaultdict(list)
    for area, keys in settings.areas().items():
        for name in keys:
            areas_by_name[name].append(area)
    problems = [
        f"entry point '{name}' has no enablement key in any [plugins.<area>] table"
        for name in sorted(installed_names - areas_by_name.keys())
    ]
    problems += [
        f"[plugins.{areas[0]}] '{name}' names no installed entry point"
        for name, areas in sorted(areas_by_name.items())
        if name not in installed_names
    ]
    problems += [
        f"'{name}' is under {' and '.join(f'[plugins.{area}]' for area in areas)}; keep it in one area"
        for name, areas in sorted(areas_by_name.items())
        if len(areas) > 1
    ]
    if problems:
        raise ConfigurationError("; ".join(problems))


@lru_cache(maxsize=1)
def get_plugins_settings() -> PluginsSettings:
    """Return the process-wide `PluginsSettings` singleton."""

    return PluginsSettings()
