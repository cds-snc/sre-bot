"""Per-plugin hook calls that attribute a boot failure to its plugin (decisions/plugins.md).

Every plugin boot failure aborts startup. Each is logged once as a CRITICAL
``plugin_boot_failed`` event naming the plugin, the phase, the error type and the
configuration setting at fault when one is. The event never carries the error
text: a validation message renders the input value, which may be a secret.
"""

import importlib.metadata
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from pydantic import ValidationError

from contracts.configuration import ConfigurationSlice, built_slices
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from contracts.plugins.requirements import RequiredDependencyError

if TYPE_CHECKING:
    import pluggy
    from structlog.stdlib import BoundLogger

UNKNOWN_PLUGIN = "unknown"

# The slice classes each plugin's boot hooks first built, for the plugin_configuration_summary event.
_built_by_plugin: dict[str, set[type]] = {}


def reset_plugin_built_slices() -> None:
    """Forget the slices attributed to plugins; the lifespan calls it before plugin boot starts."""
    _built_by_plugin.clear()


def plugin_built_slices() -> dict[str, tuple[ConfigurationSlice, ...]]:
    """Return, per plugin in boot order, the slices first built during its boot hooks, sorted by table."""
    built = built_slices()
    return {plugin: tuple(entry for entry in built if type(entry) in classes) for plugin, classes in _built_by_plugin.items()}


@contextmanager
def attribute_built_slices(plugin: str) -> Iterator[None]:
    """Attribute to ``plugin`` every slice built inside the block that no earlier boot step built."""
    before = {type(built) for built in built_slices()}
    yield
    added = {type(built) for built in built_slices()} - before
    if added:
        _built_by_plugin.setdefault(plugin, set()).update(added)


def call_hook_per_plugin(pm: pluggy.PluginManager, hook_name: str, logger: BoundLogger, /, **kwargs: object) -> None:
    """Call ``hook_name`` on each registered plugin in turn, logging and re-raising the first failure.

    The event's phase is the hook name. A blocked (disabled) plugin is listed
    without a plugin object and is skipped.
    """
    plugins = [(name, plugin) for name, plugin in pm.list_name_plugin() if plugin is not None]
    for name, plugin in plugins:
        others = [other for _, other in plugins if other is not plugin]
        hook = pm.subset_hook_caller(hook_name, remove_plugins=others)
        try:
            with attribute_built_slices(name):
                hook(**kwargs)
        except Exception as error:
            log_plugin_boot_failed(logger, plugin=name, phase=hook_name, error=error)
            raise


def load_entry_points(pm: pluggy.PluginManager, logger: BoundLogger) -> None:
    """Load every unblocked entry point, attributing an import failure to its entry-point name.

    pluggy loads the entry points in distribution order and stops at the first
    that fails, so the failing one is the first still neither registered nor blocked.
    """
    try:
        pm.load_setuptools_entrypoints(PLUGIN_NAMESPACE)
    except Exception as error:
        pending = [
            entry_point.name
            for distribution in importlib.metadata.distributions()
            for entry_point in distribution.entry_points
            if entry_point.group == PLUGIN_NAMESPACE
            and not pm.has_plugin(entry_point.name)
            and not pm.is_blocked(entry_point.name)
        ]
        log_plugin_boot_failed(logger, plugin=pending[0] if pending else UNKNOWN_PLUGIN, phase="plugin_loading", error=error)
        raise


def log_plugin_boot_failed(logger: BoundLogger, *, plugin: str, phase: str, error: Exception) -> None:
    """Log the one CRITICAL ``plugin_boot_failed`` event for a plugin boot abort."""
    logger.critical(
        "plugin_boot_failed",
        plugin=plugin,
        phase=phase,
        error_type=type(error).__name__,
        setting=_setting_at_fault(error),
    )


def _setting_at_fault(error: Exception) -> str | None:
    """Name the configuration setting at fault, from the error's structure only."""
    match error:
        case RequiredDependencyError():
            return error.setting
        case ValidationError():
            locations = (".".join(str(part) for part in detail["loc"]) for detail in error.errors(include_input=False))
            return ", ".join(f"{error.title}.{location}" if location else error.title for location in locations)
        case _:
            return None
