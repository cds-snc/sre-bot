"""Per-plugin hook calls that attribute a boot failure to its plugin (decisions/plugins.md).

Every plugin boot failure aborts startup. Each is logged once as a CRITICAL
``plugin_boot_failed`` event naming the plugin, the phase, the error type and the
configuration setting at fault when one is. The event never carries the error
text: a validation message renders the input value, which may be a secret.
"""

import importlib.metadata
from typing import TYPE_CHECKING

from pydantic import ValidationError

from contracts.plugins.namespace import PLUGIN_NAMESPACE
from contracts.plugins.requirements import RequiredDependencyError

if TYPE_CHECKING:
    import pluggy
    from structlog.stdlib import BoundLogger

UNKNOWN_PLUGIN = "unknown"


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
