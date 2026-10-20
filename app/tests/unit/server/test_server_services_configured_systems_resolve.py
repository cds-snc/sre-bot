"""Unit tests for resolving the configured-systems read from the host registry.

The vendor settings providers read by server.configured_systems are replaced with
settings built by model_construct, and the AWS client factory with a MagicMock,
so the real registration builds without environment, .env file or network. The
tests assert resolution by the Protocol, the settings-to-tenants wiring, and
the per-registry singleton lifetime.
"""

from unittest.mock import MagicMock

import pytest
import svcs

from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from integrations.google_workspace.settings import GoogleWorkspaceSettings
from integrations.slack.settings import SlackSettings
from server.configured_systems import StaticConfiguredSystems
from server.services import register_core_services

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _stub_settings_and_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("server.services.get_aws_client", MagicMock())
    monkeypatch.setattr("server.configured_systems.get_slack_settings", lambda: SlackSettings.model_construct(TEAM_ID="T0123"))
    monkeypatch.setattr(
        "server.configured_systems.get_google_workspace_settings",
        lambda: GoogleWorkspaceSettings.model_construct(
            GOOGLE_WORKSPACE_CUSTOMER_ID="C0abc", GCP_SRE_SERVICE_ACCOUNT_KEY_FILE="/run/key.json"
        ),
    )


def _registry() -> svcs.Registry:
    registry = svcs.Registry()
    register_core_services(registry)
    return registry


def test_resolves_under_the_protocol_from_the_vendor_slices() -> None:
    with svcs.Container(_registry()) as container:
        systems = container.get(ConfiguredSystems)

    assert isinstance(systems, StaticConfiguredSystems)
    assert dict(systems.tenants()) == {WorkplaceSystem.SLACK: "T0123", WorkplaceSystem.GOOGLE: "C0abc"}


def test_one_registry_builds_it_once_and_a_new_registry_builds_again() -> None:
    registry = _registry()

    with svcs.Container(registry) as first, svcs.Container(registry) as second, svcs.Container(_registry()) as other:
        assert first.get(ConfiguredSystems) is second.get(ConfiguredSystems)
        assert first.get(ConfiguredSystems) is not other.get(ConfiguredSystems)
