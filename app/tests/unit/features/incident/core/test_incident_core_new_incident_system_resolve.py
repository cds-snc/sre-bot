"""Unit tests for resolving the new-incident policy against the configured workplace systems.

The configured systems are a fixed fake; the policy is passed in directly. A
resolution returns the one system that creates a new incident's report and video
call; every unresolvable combination raises a ``SettingError`` naming the policy's
setting path, so the boot failure it causes names the key to fix.
"""

import pytest

from contracts.configuration import SettingError
from contracts.workplace import WorkplaceSystem
from features.incident.core.api import resolve_new_incident_system
from tests.factories.incident import FakeConfiguredSystems

pytestmark = pytest.mark.unit

SETTING = "incident_core.new_incident_system"
SLACK_ONLY = FakeConfiguredSystems({WorkplaceSystem.SLACK: "T0123"})
SLACK_AND_GOOGLE = FakeConfiguredSystems({WorkplaceSystem.SLACK: "T0123", WorkplaceSystem.GOOGLE: "C0abc"})
NONE = FakeConfiguredSystems({})


def test_a_set_policy_resolves_to_its_configured_system() -> None:
    assert resolve_new_incident_system(WorkplaceSystem.GOOGLE, SLACK_AND_GOOGLE) is WorkplaceSystem.GOOGLE


def test_an_unset_policy_resolves_to_the_only_configured_system() -> None:
    assert resolve_new_incident_system(None, SLACK_ONLY) is WorkplaceSystem.SLACK


@pytest.mark.parametrize(
    ("policy", "systems"),
    [
        pytest.param(None, SLACK_AND_GOOGLE, id="unset-with-several"),
        pytest.param(WorkplaceSystem.GOOGLE, SLACK_ONLY, id="named-but-unconfigured"),
        pytest.param(None, NONE, id="unset-with-none"),
        pytest.param(WorkplaceSystem.SLACK, NONE, id="set-with-none"),
    ],
)
def test_an_unresolvable_policy_raises_naming_the_setting(policy: WorkplaceSystem | None, systems: FakeConfiguredSystems) -> None:
    with pytest.raises(SettingError) as raised:
        resolve_new_incident_system(policy, systems)

    assert raised.value.setting == SETTING
    assert SETTING in str(raised.value)
