"""Unit tests for the host resolution of plugin requirement declarations.

Declarations come from the real plugin modules' ``register_requirements`` hookimpls
(called directly) and from throwaway plugins on a real pluggy manager. The
configured-systems read is a stub listing the systems a test configures; the vendor
settings slices are replaced by stand-ins in the slice table, and the built-slice read
by a stand-in list of objects carrying a ``_table``, so no configuration file is read.
One test builds a real throwaway ConfigurationSlice over the ci files the autouse
fixture installs, which also clears the built slices before each test.
A workplace tenant resolves through the read, a vendor setting through its slice, any
other table through the already-built slice that reads it, and an empty secret is
unset. Every unmet requirement of every plugin must be collected, logged once as a
CRITICAL ``plugin_boot_failed`` naming plugin and setting only, and raised as one
aggregate error; a disabled (blocked) plugin is never asked.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pluggy
import pytest
import structlog
from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict
from structlog.testing import capture_logs

from contracts.configuration import ConfigurationSlice, install_configuration_files
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


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """The slices built before plugin boot, as the host reads them; tests append to it."""
    slices: list[object] = []
    monkeypatch.setattr(host, "built_slices", lambda: tuple(slices))
    return slices


def _built_on(table: str, **fields: Any) -> object:
    """A stand-in built slice reading ``table``: slice_table reads the class's ``_table``."""
    return type("_BuiltSlice", (SimpleNamespace,), {"_table": table})(**fields)


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


class _FeatureSettings(ConfigurationSlice):
    model_config = SettingsConfigDict(toml_table_header=("feature_x",), env_prefix="FEATURE_X__", env_file=None)

    folder_id: str = ""


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


def test_a_feature_table_requirement_is_met_by_the_built_slice_that_reads_it(built: list[object]) -> None:
    """A table no vendor slice owns resolves against the built slice whose table it names, nested paths included."""
    built.extend([_built_on("other", folder_id=""), _built_on("feature_x", folder_id="f1", tenant=SimpleNamespace(id="t1"))])

    assert is_requirement_met(Requirement("feature_x.folder_id"), _Systems({})) is True
    assert is_requirement_met(Requirement("feature_x.tenant.id"), _Systems({})) is True


@pytest.mark.parametrize(
    ("value", "met"),
    [
        pytest.param("", False, id="empty"),
        pytest.param(None, False, id="none"),
        pytest.param(SecretStr(""), False, id="empty-secret"),
        pytest.param(SecretStr("s"), True, id="secret"),
    ],
)
def test_a_feature_table_requirement_is_unmet_when_its_value_is_unset(built: list[object], value: object, met: bool) -> None:
    built.append(_built_on("feature_x", folder_id=value))

    assert is_requirement_met(Requirement("feature_x.folder_id"), _Systems({})) is met


def test_a_real_configuration_slice_resolves_by_its_table_once_built(tmp_path: Path) -> None:
    """Over the real built-slice read: unmet before the slice is built (never built on demand), met after.

    The test installs its own base file holding the slice's table; the autouse fixture reinstalls the ci files next.
    """
    (tmp_path / "base.toml").write_text('[feature_x]\nfolder_id = "f1"\n', encoding="utf-8")
    install_configuration_files(_Files(environment="ci", paths=(tmp_path / "base.toml",)))
    requirement = Requirement("feature_x.folder_id")

    assert is_requirement_met(requirement, _Systems({})) is False

    _FeatureSettings()

    assert is_requirement_met(requirement, _Systems({})) is True


@pytest.mark.parametrize(
    "setting",
    [
        pytest.param("nowhere.folder_id", id="table-no-slice-reads"),
        pytest.param("feature_x.missing", id="missing-attribute"),
        pytest.param("feature_x", id="bare-table"),
    ],
)
def test_a_feature_requirement_without_a_built_value_is_unmet(built: list[object], setting: str) -> None:
    built.append(_built_on("feature_x", folder_id="f1"))

    assert is_requirement_met(Requirement(setting), _Systems(ALL_SYSTEMS)) is False


def test_a_feature_slice_not_built_when_requirements_resolve_is_unmet(built: list[object]) -> None:
    assert is_requirement_met(Requirement("feature_x.folder_id"), _Systems(ALL_SYSTEMS)) is False


def test_a_vendor_table_resolves_through_its_getter_even_when_a_built_slice_reads_the_same_table(
    slices: dict[str, object], built: list[object]
) -> None:
    """The vendor map keeps precedence: a built stand-in on the same table with a value does not satisfy it."""
    slices["openai"] = SimpleNamespace(tenant=None)
    built.append(_built_on("openai", tenant=object()))

    assert is_requirement_met(Requirement("openai.tenant"), _Systems({})) is False


def test_a_slice_built_before_plugin_boot_resolves_for_every_plugin_that_requires_it(built: list[object]) -> None:
    """The lookup reads every built slice, not only those attributed to the declaring plugin."""
    built.append(_built_on("feature_x", folder_id="f1"))
    requirement = (Requirement("feature_x.folder_id"),)

    assert unmet_requirements({"first": requirement, "second": requirement}, _Systems({})) == []


def test_an_unmet_feature_requirement_is_logged_with_plugin_and_setting_never_a_value(built: list[object]) -> None:
    built.append(_built_on("feature_x", folder_id="", report_template_id="visible-value-123"))
    pm = _manager(first=_plugin("feature_x.folder_id", "feature_x.report_template_id", "feature_x.missing"))

    with capture_logs() as events, pytest.raises(PluginRequirementsUnmetError) as raised:
        resolve_requirements(pm, structlog.get_logger(), _Systems({}))

    assert raised.value.failures == (
        RequirementFailure("first", "feature_x.folder_id"),
        RequirementFailure("first", "feature_x.missing"),
    )
    failed = [event for event in events if event["event"] == "plugin_boot_failed"]
    assert [(event["plugin"], event["setting"]) for event in failed] == [
        ("first", "feature_x.folder_id"),
        ("first", "feature_x.missing"),
    ]
    assert "visible-value-123" not in repr(events)
    assert "visible-value-123" not in str(raised.value)
