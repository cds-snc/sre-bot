"""Unit tests for the host resolution of plugin requirement declarations.

Declarations come from the real plugin modules' ``register_requirements`` hookimpls
(called directly) and from throwaway plugins on a real pluggy manager. The
configured-systems read is a stub listing the systems a test configures; the settings
slices are replaced by stand-ins in the slice table, so no configuration file is read.
A workplace tenant resolves through the read, any other setting through its slice, and
an empty secret is unset. Every unmet requirement of every plugin must be collected,
logged once as a CRITICAL ``plugin_boot_failed`` naming plugin and setting only, and
raised as one aggregate error; a disabled (blocked) plugin is never asked.
"""

from collections.abc import Mapping
from types import ModuleType, SimpleNamespace

import pluggy
import pytest
import structlog
from pydantic import SecretStr
from structlog.testing import capture_logs

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl
from contracts.plugins.requirements import Requirement
from contracts.workplace import WorkplaceSystem
from features.incident import scribe
from packages import oncall_sync, rant, user_rotations
from server.plugins import requirements as host
from server.plugins.requirements import (
    PluginRequirementsUnmetError,
    RequirementFailure,
    declared_requirements,
    is_requirement_met,
    resolve_requirements,
    unmet_requirements,
)

pytestmark = pytest.mark.unit

ALL_SYSTEMS = {WorkplaceSystem.SLACK: "T1", WorkplaceSystem.GOOGLE: "C1"}
CONFIGURED_SLICES = {
    "openai": SimpleNamespace(tenant=object()),
    "opsgenie": SimpleNamespace(tenant=object()),
    "slack": SimpleNamespace(user_token=SecretStr("set")),
}


class _Systems:
    def __init__(self, tenants: Mapping[WorkplaceSystem, str]) -> None:
        self._tenants = tenants

    def tenants(self) -> Mapping[WorkplaceSystem, str]:
        return self._tenants


@pytest.fixture
def slices(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    table: dict[str, object] = dict(CONFIGURED_SLICES)
    monkeypatch.setattr(host, "SETTINGS_SLICES", {name: (lambda name=name: table[name]) for name in CONFIGURED_SLICES})
    return table


def _plugin(*settings: str) -> ModuleType:
    @hookimpl
    def register_requirements() -> tuple[Requirement, ...]:
        return tuple(Requirement(setting) for setting in settings)

    plugin = ModuleType("fake_plugin")
    plugin.register_requirements = register_requirements  # type: ignore[attr-defined]
    return plugin


def _manager(**plugins: ModuleType) -> pluggy.PluginManager:
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    for name, plugin in plugins.items():
        pm.register(plugin, name=name)
    return pm


PLUGIN_DECLARATIONS = [
    pytest.param(scribe, ("openai.tenant", "slack.tenant", "google_workspace.tenant"), id="incident.scribe"),
    pytest.param(oncall_sync, ("slack.tenant", "slack.user_token", "opsgenie.tenant"), id="oncall_sync"),
    pytest.param(rant, ("slack.tenant",), id="rant"),
    pytest.param(user_rotations, ("slack.tenant",), id="user_rotations"),
]


@pytest.mark.parametrize(("module", "settings"), PLUGIN_DECLARATIONS)
def test_plugin_declares_exactly_its_requirements(module: ModuleType, settings: tuple[str, ...]) -> None:
    assert module.register_requirements() == tuple(Requirement(setting) for setting in settings)


@pytest.mark.parametrize(("module", "settings"), PLUGIN_DECLARATIONS)
def test_plugin_requirements_are_met_when_everything_is_configured(
    module: ModuleType, settings: tuple[str, ...], slices: dict[str, object]
) -> None:
    assert unmet_requirements({"plugin": module.register_requirements()}, _Systems(ALL_SYSTEMS)) == []


@pytest.mark.parametrize(("module", "settings"), PLUGIN_DECLARATIONS)
def test_plugin_requirements_fail_naming_each_setting_that_is_not_configured(
    module: ModuleType, settings: tuple[str, ...], slices: dict[str, object]
) -> None:
    slices["openai"] = SimpleNamespace(tenant=None)
    slices["opsgenie"] = SimpleNamespace(tenant=None)
    slices["slack"] = SimpleNamespace(user_token=SecretStr(""))

    failures = unmet_requirements({"plugin": module.register_requirements()}, _Systems({}))

    assert failures == [RequirementFailure("plugin", setting) for setting in settings]


@pytest.mark.parametrize(
    ("setting", "system"),
    [("slack.tenant", WorkplaceSystem.SLACK), ("google_workspace.tenant", WorkplaceSystem.GOOGLE)],
)
def test_workplace_tenants_resolve_through_the_configured_systems_read(setting: str, system: WorkplaceSystem) -> None:
    assert is_requirement_met(Requirement(setting), _Systems({system: "id"})) is True
    assert is_requirement_met(Requirement(setting), _Systems({})) is False


def test_other_settings_resolve_through_their_slice(slices: dict[str, object]) -> None:
    assert is_requirement_met(Requirement("opsgenie.tenant"), _Systems({})) is True

    slices["opsgenie"] = SimpleNamespace(tenant=None)

    assert is_requirement_met(Requirement("opsgenie.tenant"), _Systems({})) is False


def test_an_empty_secret_counts_as_unset(slices: dict[str, object]) -> None:
    slices["slack"] = SimpleNamespace(user_token=SecretStr(""))

    assert is_requirement_met(Requirement("slack.user_token"), _Systems({})) is False


def test_an_unknown_settings_table_is_unmet(slices: dict[str, object]) -> None:
    assert is_requirement_met(Requirement("nowhere.tenant"), _Systems(ALL_SYSTEMS)) is False


def test_declarations_are_collected_per_plugin_from_the_hook_only() -> None:
    pm = _manager(first=_plugin("slack.tenant"), second=_plugin("openai.tenant", "opsgenie.tenant"))

    declared = declared_requirements(pm, structlog.get_logger())

    assert declared == {
        "first": (Requirement("slack.tenant"),),
        "second": (Requirement("openai.tenant"), Requirement("opsgenie.tenant")),
    }


def test_every_unmet_requirement_of_every_plugin_is_logged_once_then_one_error_is_raised(
    slices: dict[str, object],
) -> None:
    slices["openai"] = SimpleNamespace(tenant=None)
    pm = _manager(first=_plugin("openai.tenant", "slack.tenant"), met=_plugin("slack.tenant"), second=_plugin("openai.tenant"))

    with capture_logs() as events, pytest.raises(PluginRequirementsUnmetError) as raised:
        resolve_requirements(pm, structlog.get_logger(), _Systems({}))

    assert raised.value.failures == (
        RequirementFailure("first", "openai.tenant"),
        RequirementFailure("first", "slack.tenant"),
        RequirementFailure("met", "slack.tenant"),
        RequirementFailure("second", "openai.tenant"),
    )
    assert [event for event in events if event["event"] == "plugin_boot_failed"] == [
        {
            "event": "plugin_boot_failed",
            "log_level": "critical",
            "plugin": failure.plugin,
            "phase": "register_requirements",
            "error_type": "PluginRequirementsUnmetError",
            "setting": failure.setting,
        }
        for failure in raised.value.failures
    ]


def test_met_requirements_log_nothing_and_raise_nothing(slices: dict[str, object]) -> None:
    pm = _manager(first=_plugin("slack.tenant", "openai.tenant"))

    with capture_logs() as events:
        resolve_requirements(pm, structlog.get_logger(), _Systems(ALL_SYSTEMS))

    assert events == []


def test_a_blocked_plugin_is_not_asked_for_its_requirements(slices: dict[str, object]) -> None:
    pm = _manager(on=_plugin("slack.tenant"))
    pm.set_blocked("off")

    assert declared_requirements(pm, structlog.get_logger()) == {"on": (Requirement("slack.tenant"),)}
