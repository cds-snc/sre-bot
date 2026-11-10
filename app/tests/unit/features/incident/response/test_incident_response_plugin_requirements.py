"""Unit tests for what the incident.response plugin requires at boot.

The hookimpls are called directly. The [incident_core] slice the warmup reads is
replaced on the plugin module with a constructed slice holding only the policy,
and the configured systems are a fixed fake, so each case states exactly which
policy meets which systems. A warmup that cannot resolve the policy raises the
``SettingError`` the host logs as the boot failure naming the key.
"""

import pytest
import structlog

from contracts.configuration import SettingError
from contracts.plugins.requirements import Requirement
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import IncidentCoreSettings
from features.incident.response import plugin
from tests.factories.incident import FakeConfiguredSystems

pytestmark = pytest.mark.unit

SLACK_AND_GOOGLE = FakeConfiguredSystems({WorkplaceSystem.SLACK: "T0123", WorkplaceSystem.GOOGLE: "C0abc"})


def use_policy(monkeypatch: pytest.MonkeyPatch, policy: WorkplaceSystem | None) -> None:
    core = IncidentCoreSettings.model_construct(new_incident_system=policy)
    monkeypatch.setattr(plugin, "get_incident_core_settings", lambda: core)


def test_the_plugin_requires_the_handbook_id() -> None:
    assert Requirement("incident_response.handbook_id") in plugin.register_requirements()


def test_warmup_accepts_a_policy_naming_a_configured_system(monkeypatch: pytest.MonkeyPatch) -> None:
    use_policy(monkeypatch, WorkplaceSystem.GOOGLE)

    plugin.startup_warmup(logger=structlog.get_logger(), systems=SLACK_AND_GOOGLE)


def test_warmup_fails_naming_the_policy_when_it_does_not_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    use_policy(monkeypatch, None)

    with pytest.raises(SettingError) as raised:
        plugin.startup_warmup(logger=structlog.get_logger(), systems=SLACK_AND_GOOGLE)

    assert raised.value.setting == "incident_core.new_incident_system"
