"""Unit tests for the configured-systems read and its vendor tenant sources.

read_configured_systems is driven by stub TenantSource rows returning fixed
values, so the tests state only the systems they are about. The vendor tenant
functions read each slice's tenant entry; they get Slack and Google slices
built with model_construct, holding values their validators accept. The
blank-id, my_customer alias and missing-key rejections belong to boot
validation and are covered by the settings tests. Two tests build the slices
from monkeypatched environment variables with the .env file disabled, to show
the validated path end to end and that an invalid entry never reaches a source. structlog's capture_logs checks the boot
event names systems and never carries a tenant id.
"""

import pytest
from structlog.testing import capture_logs

from contracts.configuration import ConfigurationError
from contracts.workplace import WorkplaceSystem
from integrations.google_workspace.settings import GoogleWorkspaceSettings, GoogleWorkspaceTenant
from integrations.slack.settings import SlackSettings, SlackTenant
from server import services
from server.configured_systems import (
    TENANT_SOURCES,
    StaticConfiguredSystems,
    TenantSource,
    google_tenant,
    read_configured_systems,
    slack_tenant,
)
from tests.factories.google_service_account import service_account_key

pytestmark = pytest.mark.unit


def _source(system: WorkplaceSystem, tenant: str | None) -> TenantSource:
    return TenantSource(system, lambda: tenant)


def _slack(team_id: str | None = None) -> SlackSettings:
    return SlackSettings.model_construct(tenant=SlackTenant(team_id=team_id) if team_id is not None else None)


def _google(customer_id: str | None = None) -> GoogleWorkspaceSettings:
    tenant = (
        GoogleWorkspaceTenant(customer_id=customer_id, service_account_key=service_account_key())
        if customer_id is not None
        else None
    )
    return GoogleWorkspaceSettings.model_construct(tenant=tenant)


def test_configured_sources_are_returned_in_source_order() -> None:
    systems = read_configured_systems([_source(WorkplaceSystem.SLACK, "T0123"), _source(WorkplaceSystem.GOOGLE, "C0abc")])

    assert list(systems.tenants().items()) == [(WorkplaceSystem.SLACK, "T0123"), (WorkplaceSystem.GOOGLE, "C0abc")]


def test_a_source_returning_none_is_left_out() -> None:
    systems = read_configured_systems([_source(WorkplaceSystem.SLACK, None), _source(WorkplaceSystem.GOOGLE, "C0abc")])

    assert dict(systems.tenants()) == {WorkplaceSystem.GOOGLE: "C0abc"}


def test_no_sources_configured_returns_an_empty_mapping() -> None:
    assert dict(read_configured_systems([_source(WorkplaceSystem.SLACK, None)]).tenants()) == {}


def test_the_default_sources_cover_slack_then_google() -> None:
    assert [source.system for source in TENANT_SOURCES] == [WorkplaceSystem.SLACK, WorkplaceSystem.GOOGLE]


def test_slack_tenant_is_the_stripped_team_id() -> None:
    assert slack_tenant(_slack(" T0123 ")) == "T0123"


def test_slack_without_a_team_id_is_not_configured() -> None:
    assert slack_tenant(_slack()) is None


def test_slack_tenant_entry_configures_the_system() -> None:
    """A tenant entry is what configures a system; [slack_transport] enabled only switches the transport."""
    assert slack_tenant(_slack("T0123")) == "T0123"


def test_google_tenant_is_the_entry_customer_id() -> None:
    assert google_tenant(_google(" C0abc ")) == "C0abc"


def test_google_without_an_entry_is_not_configured() -> None:
    assert google_tenant(_google()) is None


def test_validated_settings_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a [slack.tenant] entry Slack is absent after validation; a tenant entry and its key configure Google."""
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "C0abc")
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", service_account_key())

    assert slack_tenant(SlackSettings(_env_file=None)) is None  # type: ignore[call-arg]
    assert google_tenant(GoogleWorkspaceSettings(_env_file=None)) == "C0abc"  # type: ignore[call-arg]


def test_an_invalid_google_entry_fails_before_any_tenant_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A customer id without its key is a present entry missing a secret, so the slice never builds."""
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", "")
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "C0abc")
    source = TenantSource(WorkplaceSystem.GOOGLE, lambda: google_tenant(GoogleWorkspaceSettings(_env_file=None)))  # type: ignore[call-arg]

    with pytest.raises(ConfigurationError, match="GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY"):
        read_configured_systems([source])


def test_tenants_are_read_only_and_copied() -> None:
    source = {WorkplaceSystem.SLACK: "T0123"}
    systems = StaticConfiguredSystems(source)

    source[WorkplaceSystem.GOOGLE] = "C0abc"

    assert dict(systems.tenants()) == {WorkplaceSystem.SLACK: "T0123"}
    with pytest.raises(TypeError):
        systems.tenants()[WorkplaceSystem.GOOGLE] = "C0abc"  # type: ignore[index]


def test_reading_logs_nothing_so_a_second_read_adds_no_boot_event() -> None:
    """The read is called by the core-service build and again by plugin requirement resolution; only the build logs."""
    with capture_logs() as logs:
        read_configured_systems([_source(WorkplaceSystem.SLACK, "T0123")])

    assert logs == []


def test_boot_event_names_the_systems_and_no_tenant_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """The core-service build logs one configured_systems_built event naming the systems, never a tenant id."""
    systems = StaticConfiguredSystems({WorkplaceSystem.SLACK: "T0123", WorkplaceSystem.GOOGLE: "C0abc"})
    monkeypatch.setattr(services, "read_configured_systems", lambda: systems)

    with capture_logs() as logs:
        built = services._build_configured_systems()

    assert built is systems
    events = [entry for entry in logs if entry["event"] == "configured_systems_built"]
    assert events == [{"event": "configured_systems_built", "log_level": "info", "systems": ["slack", "google"]}]
