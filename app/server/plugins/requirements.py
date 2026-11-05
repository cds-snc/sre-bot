"""Host resolution of the requirements enabled plugins declare (decisions/plugins.md).

A plugin returns ``Requirement`` values from ``register_requirements``; it holds no
vendor code. The host resolves each one: a workplace-system tenant through the
configured-systems read, a vendor setting through the cached, validated settings
slice that owns it, and any other table (a feature's own) through the configuration
slice already built for it in the configuration phase, so the host imports no feature;
a slice not built by then is never built here and its requirement is unmet. An empty
secret counts as unset. Every unmet requirement of every enabled plugin is collected,
each is logged once as a CRITICAL ``plugin_boot_failed`` event naming the plugin and
the setting, and one aggregate error stops boot.
The events name settings only, never a configured value.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import SecretStr

from contracts.configuration import built_slices, slice_table
from contracts.plugins.requirements import Requirement
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from integrations.openai.settings import get_openai_settings
from integrations.opsgenie.settings import get_opsgenie_settings
from integrations.slack.settings import get_slack_settings
from server.plugins.boot import attribute_built_slices, call_hook_per_plugin

if TYPE_CHECKING:
    import pluggy
    from structlog.stdlib import BoundLogger

REQUIREMENTS_HOOK = "register_requirements"

# Settings that configure a workplace system: met when the configured-systems read lists it.
WORKPLACE_SETTINGS: Mapping[str, WorkplaceSystem] = {
    "slack.tenant": WorkplaceSystem.SLACK,
    "google_workspace.tenant": WorkplaceSystem.GOOGLE,
}
# The vendor settings slice each table resolves through, built on demand; it takes precedence
# over a built slice on the same table. Any other table resolves only through built_slices().
SETTINGS_SLICES: Mapping[str, Callable[[], object]] = {
    "openai": get_openai_settings,
    "opsgenie": get_opsgenie_settings,
    "slack": get_slack_settings,
}


@dataclass(frozen=True)
class RequirementFailure:
    """An enabled plugin and the setting it requires that is not configured."""

    plugin: str
    setting: str


class PluginRequirementsUnmetError(Exception):
    """Enabled plugins require settings that are not configured; carries every failure."""

    def __init__(self, failures: Sequence[RequirementFailure]) -> None:
        self.failures = tuple(failures)
        listed = ", ".join(f"{failure.plugin} needs {failure.setting}" for failure in self.failures)
        super().__init__(f"required settings not configured: {listed}; configure them or switch the plugin off")


def is_requirement_met(requirement: Requirement, systems: ConfiguredSystems) -> bool:
    """Resolve one requirement; a table no vendor or built slice reads, or a missing attribute, is unmet."""
    system = WORKPLACE_SETTINGS.get(requirement.setting)
    if system is not None:
        return system in systems.tenants()
    table, *path = requirement.setting.split(".")
    if not path:
        return False
    read = SETTINGS_SLICES.get(table)
    value: object = read() if read is not None else _built_slice(table)
    for field in path:
        value = getattr(value, field, None)
    return _is_set(value)


def _built_slice(table: str) -> object | None:
    return next((built for built in built_slices() if slice_table(built) == table), None)


def _is_set(value: object) -> bool:
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value())
    return value is not None and value != ""


def declared_requirements(pm: pluggy.PluginManager, logger: BoundLogger) -> dict[str, tuple[Requirement, ...]]:
    """Fire only ``register_requirements`` and return each plugin's declarations by entry-point name."""
    results = call_hook_per_plugin(pm, REQUIREMENTS_HOOK, logger)
    return {plugin: tuple(req for declared in returned for req in declared) for plugin, returned in results.items()}


def unmet_requirements(declared: Mapping[str, Sequence[Requirement]], systems: ConfiguredSystems) -> list[RequirementFailure]:
    """Return a failure for every unmet requirement of every plugin, in plugin and declaration order.

    The slices a resolution builds are attributed to the plugin that declared it.
    """
    failures: list[RequirementFailure] = []
    for plugin, requirements in declared.items():
        with attribute_built_slices(plugin):
            failures.extend(
                RequirementFailure(plugin, requirement.setting)
                for requirement in requirements
                if not is_requirement_met(requirement, systems)
            )
    return failures


def resolve_requirements(pm: pluggy.PluginManager, logger: BoundLogger, systems: ConfiguredSystems) -> None:
    """Resolve every enabled plugin's declarations; log each failure, then raise one aggregate error.

    Raises:
        PluginRequirementsUnmetError: At least one requirement is not configured.
    """
    failures = unmet_requirements(declared_requirements(pm, logger), systems)
    for failure in failures:
        logger.critical(
            "plugin_boot_failed",
            plugin=failure.plugin,
            phase=REQUIREMENTS_HOOK,
            error_type=PluginRequirementsUnmetError.__name__,
            setting=failure.setting,
        )
    if failures:
        raise PluginRequirementsUnmetError(failures)
