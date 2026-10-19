"""Unit tests for the configured-systems read and its vendor tenant sources.

read_configured_systems is driven by stub TenantSource rows returning fixed
values, so the tests state only the systems they are about. The vendor tenant
functions get Slack and Google slices built with model_construct, holding values
their validators accept; the blank-id and my_customer alias rejections belong to
boot validation and are covered by the settings tests. One test builds the
slices from monkeypatched environment variables with the .env file disabled, to
show the validated path end to end. structlog's capture_logs checks the boot
event names systems and never carries a tenant id.
"""

import pytest
from structlog.testing import capture_logs

from contracts.workplace import WorkplaceSystem
from infrastructure.configuration.integrations.google import GoogleWorkspaceSettings
from integrations.slack.settings import SlackSettings
from server.configured_systems import (
    TENANT_SOURCES,
    StaticConfiguredSystems,
    TenantSource,
    google_tenant,
    read_configured_systems,
    slack_tenant,
)

pytestmark = pytest.mark.unit


def _source(system: WorkplaceSystem, tenant: str | None) -> TenantSource:
    return TenantSource(system, lambda: tenant)


def _slack(team_id: str | None = None, *, enabled: bool = False) -> SlackSettings:
    return SlackSettings.model_construct(TEAM_ID=team_id, ENABLED=enabled)


def _google(customer_id: str = "my_customer", key_file: str = "") -> GoogleWorkspaceSettings:
    return GoogleWorkspaceSettings.model_construct(
        GOOGLE_WORKSPACE_CUSTOMER_ID=customer_id, GCP_SRE_SERVICE_ACCOUNT_KEY_FILE=key_file
    )


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


def test_slack_tenant_entry_counts_with_the_transport_off() -> None:
    """A tenant entry is what configures a system; SLACK_ENABLED only switches the transport."""
    assert slack_tenant(_slack("T0123", enabled=False)) == "T0123"


def test_google_tenant_is_the_stripped_customer_id_when_the_key_file_is_set() -> None:
    assert google_tenant(_google(" C0abc ", key_file="/run/key.json")) == "C0abc"


def test_google_without_a_key_file_is_not_configured() -> None:
    assert google_tenant(_google("C0abc")) is None


def test_validated_settings_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty SLACK_TEAM_ID is absent after validation; a set key file and real id configure Google."""
    monkeypatch.setenv("SLACK_ENABLED", "false")
    monkeypatch.setenv("SLACK_TEAM_ID", "")
    monkeypatch.setenv("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", "/run/key.json")
    monkeypatch.setenv("GOOGLE_WORKSPACE_CUSTOMER_ID", "C0abc")

    assert slack_tenant(SlackSettings(_env_file=None)) is None  # type: ignore[call-arg]
    assert google_tenant(GoogleWorkspaceSettings(_env_file=None)) == "C0abc"  # type: ignore[call-arg]


def test_tenants_are_read_only_and_copied() -> None:
    source = {WorkplaceSystem.SLACK: "T0123"}
    systems = StaticConfiguredSystems(source)

    source[WorkplaceSystem.GOOGLE] = "C0abc"

    assert dict(systems.tenants()) == {WorkplaceSystem.SLACK: "T0123"}
    with pytest.raises(TypeError):
        systems.tenants()[WorkplaceSystem.GOOGLE] = "C0abc"  # type: ignore[index]


def test_boot_event_names_the_systems_and_no_tenant_id() -> None:
    with capture_logs() as logs:
        read_configured_systems([_source(WorkplaceSystem.SLACK, "T0123"), _source(WorkplaceSystem.GOOGLE, "C0abc")])

    events = [entry for entry in logs if entry["event"] == "configured_systems_built"]
    assert events == [{"event": "configured_systems_built", "log_level": "info", "systems": ["slack", "google"]}]
