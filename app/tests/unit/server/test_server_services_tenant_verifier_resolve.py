"""Unit tests for resolving the tenant verifier from the host registry.

The AWS client factory read by server.services is a MagicMock and the vendor
settings providers read by server.configured_systems return settings built by
model_construct, so the real registration builds without environment or network.
The Slack Web client factory read by server.tenant_verification raises on any
call, so a resolution or startup that reached Slack would fail the test. The
tests assert resolution by the Protocol, the per-registry singleton lifetime,
and that startup resolution makes no Slack call.
"""

from unittest.mock import MagicMock

import pytest
import structlog
import svcs

from contracts.workplace import TenantVerifier
from integrations.slack.settings import SlackSettings, SlackTenant
from server.services import initialize_core_services, register_core_services
from server.tenant_verification import HostTenantVerifier

pytestmark = pytest.mark.unit


def _no_slack_call() -> object:
    raise AssertionError("startup must not build a Slack client")


@pytest.fixture(autouse=True)
def _stub_settings_aws_and_slack(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SlackSettings.model_construct(tenant=SlackTenant(team_id="T0123"))
    monkeypatch.setattr("server.services.get_aws_client", MagicMock())
    monkeypatch.setattr("server.configured_systems.get_slack_settings", lambda: settings)
    monkeypatch.setattr("server.configured_systems.get_google_workspace_settings", lambda: MagicMock(tenant=None))
    monkeypatch.setattr("server.tenant_verification.get_slack_settings", _no_slack_call)
    monkeypatch.setattr("server.tenant_verification.get_slack_web_client", _no_slack_call)


def _registry() -> svcs.Registry:
    registry = svcs.Registry()
    register_core_services(registry)
    return registry


def test_resolves_the_host_verifier_under_the_protocol() -> None:
    with svcs.Container(_registry()) as container:
        assert isinstance(container.get(TenantVerifier), HostTenantVerifier)


def test_one_registry_builds_it_once() -> None:
    registry = _registry()

    with svcs.Container(registry) as first, svcs.Container(registry) as second:
        assert first.get(TenantVerifier) is second.get(TenantVerifier)


async def test_startup_resolves_every_core_service_without_calling_slack() -> None:
    registry = svcs.Registry()

    await initialize_core_services(registry, structlog.get_logger())

    async with svcs.Container(registry) as container:
        assert isinstance(await container.aget(TenantVerifier), HostTenantVerifier)
