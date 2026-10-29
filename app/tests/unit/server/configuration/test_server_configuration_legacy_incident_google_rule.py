"""Unit tests for the configuration-phase rule that a Slack transport needs a Google Workspace tenant.

The legacy incident handlers in modules/ use Google Workspace and are not plugins,
so the host states their requirement while they are registered. The Google slice is
built with model_construct, so neither the environment nor a .env file can satisfy
the rule; the transport slice is built with explicit values. A failure must name
GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID and never carry a tenant value.
"""

import pytest

from contracts.configuration import ConfigurationError
from integrations.google_workspace.settings import GoogleWorkspaceSettings, GoogleWorkspaceTenant
from server.configuration.host_configuration import validate_legacy_incident_google_tenant
from server.slack.settings import SlackTransportSettings

pytestmark = pytest.mark.unit

CUSTOMER_ID = "C0secret123"


def _google(configured: bool) -> GoogleWorkspaceSettings:
    tenant = GoogleWorkspaceTenant.model_construct(customer_id=CUSTOMER_ID) if configured else None
    return GoogleWorkspaceSettings.model_construct(tenant=tenant)


def test_transport_off_without_a_google_tenant_passes() -> None:
    validate_legacy_incident_google_tenant(SlackTransportSettings(enabled=False), _google(configured=False))


def test_transport_on_with_a_google_tenant_passes() -> None:
    validate_legacy_incident_google_tenant(SlackTransportSettings(enabled=True), _google(configured=True))


def test_transport_on_without_a_google_tenant_fails_naming_the_customer_id() -> None:
    with pytest.raises(ConfigurationError) as raised:
        validate_legacy_incident_google_tenant(SlackTransportSettings(enabled=True), _google(configured=False))

    assert str(raised.value) == ("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID is required when [slack_transport] enabled is true")
