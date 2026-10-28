"""Integration tests for vendor settings slices in lifespan's configuration phase.

The real lifespan runs with every later phase stubbed (core services, security,
directory, the Slack provider, plugins, translation), so only the configuration
phase does real work. The vendor slices are built from monkeypatched
environment variables with their caches cleared and the .env file disabled. A
recording spy replaces socket.connect to show the configuration phase opens no
connection. An invalid vendor slice must stop startup with a ConfigurationError naming the
key, before the lifespan yields and before core services are built.
"""

import shutil
import socket
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from structlog.testing import capture_logs

from contracts.configuration import ConfigurationError
from features.cloud_operations.spending.settings import get_cloud_operations_spending_settings
from features.incident.common.settings import get_incident_core_settings
from features.incident.postmortem.settings import get_incident_postmortem_settings
from features.incident.response.settings import get_incident_response_settings
from features.talent.settings import get_talent_settings
from infrastructure.configuration.features.aws_ops import get_aws_feature_settings
from infrastructure.configuration.features.sre_ops import get_sre_ops_settings
from integrations.aws.settings import AWSSettings, get_aws_settings
from integrations.google_workspace.settings import GoogleWorkspaceSettings, get_google_workspace_settings
from integrations.maxmind.settings import MaxMindSettings, get_maxmind_settings
from integrations.notify.settings import NotifySettings, get_notify_settings
from integrations.openai.settings import OpenAISettings, get_openai_settings
from integrations.opsgenie.settings import OpsGenieSettings, get_opsgenie_settings
from integrations.sentinel.settings import SentinelSettings, get_sentinel_settings
from integrations.slack.settings import SlackSettings, get_slack_settings
from integrations.trello.settings import TrelloSettings, get_trello_settings
from server.configuration import host_configuration
from server.configuration.loader import CONFIG_DIR, load_configuration_files
from server.slack.settings import get_slack_transport_settings
from tests.factories.google_service_account import private_key_body, service_account_key
from tests.factories.lifespan import lifespan

pytestmark = pytest.mark.integration

_VENDOR_SECRETS = (
    "NOTIFY__SRE_USER_NAME",
    "NOTIFY__SRE_CLIENT_SECRET",
    "OPSGENIE__INTEGRATIONS_KEY",
    "TRELLO__TENANT__APP_KEY",
    "TRELLO__TENANT__TOKEN",
    "TRELLO__ATIP_BOARD",
    "SENTINEL__CUSTOMER_ID",
    "SENTINEL__SHARED_KEY",
)
_VENDOR_GETTERS = (get_notify_settings, get_trello_settings, get_opsgenie_settings, get_maxmind_settings)
_FEATURE_GETTERS = (
    get_sre_ops_settings,
    get_aws_feature_settings,
    get_incident_core_settings,
    get_incident_response_settings,
    get_incident_postmortem_settings,
    get_cloud_operations_spending_settings,
    get_talent_settings,
)


@pytest.fixture(autouse=True)
def _vendor_slices_without_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the vendor slices from the environment only, fresh for each test."""
    monkeypatch.setitem(SlackSettings.model_config, "env_file", None)
    monkeypatch.setitem(GoogleWorkspaceSettings.model_config, "env_file", None)
    monkeypatch.setitem(AWSSettings.model_config, "env_file", None)
    monkeypatch.setitem(OpenAISettings.model_config, "env_file", None)
    monkeypatch.setenv("OPENAI__API_KEY", "")
    for slice_class in (NotifySettings, TrelloSettings, OpsGenieSettings, MaxMindSettings, SentinelSettings):
        monkeypatch.setitem(slice_class.model_config, "env_file", None)
    for name in _VENDOR_SECRETS:
        monkeypatch.setenv(name, "")
    monkeypatch.delenv("SLACK_TRANSPORT__ENABLED", raising=False)
    monkeypatch.delenv("SLACK__TENANT__TEAM_ID", raising=False)
    for field in ("bot_token", "user_token", "app_token", "signing_secret"):
        monkeypatch.setenv(f"SLACK__{field.upper()}", "")
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "")
    for field in ("service_account_key", "delegated_user_email"):
        monkeypatch.setenv(f"GOOGLE_WORKSPACE__TENANT__{field.upper()}", "")
    get_slack_settings.cache_clear()
    get_slack_transport_settings.cache_clear()
    get_google_workspace_settings.cache_clear()
    get_aws_settings.cache_clear()
    get_openai_settings.cache_clear()
    for getter in (*_VENDOR_GETTERS, get_sentinel_settings):
        getter.cache_clear()
    yield
    get_slack_settings.cache_clear()
    get_slack_transport_settings.cache_clear()
    get_google_workspace_settings.cache_clear()
    get_aws_settings.cache_clear()
    get_openai_settings.cache_clear()
    for getter in (*_VENDOR_GETTERS, get_sentinel_settings):
        getter.cache_clear()


def _stub_later_phases(stack: ExitStack) -> AsyncMock:
    provider = MagicMock()
    provider.app = None
    core_services = AsyncMock()
    stack.enter_context(patch("server.lifespan.initialize_core_services", core_services))
    stack.enter_context(patch("server.lifespan._initialize_security_services"))
    stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
    stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
    stack.enter_context(patch("server.lifespan.load_plugins"))
    stack.enter_context(patch("server.lifespan._initialize_translation_service"))
    stack.enter_context(patch("server.lifespan.register_feature_integrations"))
    stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))
    stack.enter_context(patch("server.lifespan._start_scheduled_tasks"))
    stack.enter_context(patch("server.lifespan._stop_scheduled_tasks"))
    return core_services


async def _boot_fails_naming(key: str) -> str:
    """Boot, expect the failure naming the key, and return the raised text and every log line."""
    reached_yield = False
    with ExitStack() as stack, capture_logs() as entries:
        core_services = _stub_later_phases(stack)
        with pytest.raises(ConfigurationError, match=key) as raised:
            async with lifespan(FastAPI()):
                reached_yield = True

    assert reached_yield is False
    core_services.assert_not_awaited()
    return str(raised.value) + repr(entries)


async def test_slack_transport_on_without_the_tenant_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_TRANSPORT__ENABLED", "true")

    await _boot_fails_naming(r"\[slack.tenant\] team_id")


async def test_slack_tenant_without_the_bot_token_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK__TENANT__TEAM_ID", "T0TENANT")
    monkeypatch.setenv("SLACK__APP_TOKEN", "xapp-secret-boot-0001")

    rendered = await _boot_fails_naming("SLACK__BOT_TOKEN")

    assert "xapp-secret-boot-0001" not in rendered


async def test_slack_secret_without_the_tenant_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK__BOT_TOKEN", "xoxb-secret-boot-0001")

    rendered = await _boot_fails_naming("SLACK__BOT_TOKEN")

    assert "xoxb-secret-boot-0001" not in rendered


async def test_google_key_with_the_my_customer_alias_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", service_account_key())
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "my_customer")

    rendered = await _boot_fails_naming("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID")

    assert private_key_body() not in rendered


async def test_google_tenant_without_the_key_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "C03abc123")

    await _boot_fails_naming("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY")


async def test_google_delegated_user_without_the_tenant_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL", "delegated-boot-0001@example.com")

    rendered = await _boot_fails_naming("GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL")

    assert "delegated-boot-0001@example.com" not in rendered


async def test_aws_tenant_off_the_instance_id_format_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS__TENANT__INSTANCE_ID", "not-an-identity-store-id")
    monkeypatch.setenv("AWS__TENANT__INSTANCE_ARN", "arn:aws:sso:::instance/ssoins-1234567890abcdef")

    await _boot_fails_naming("instance_id")


async def test_aws_tenant_unknown_key_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS__TENANT__INSTANCE_ID", "d-1234567890")
    monkeypatch.setenv("AWS__TENANT__INSTANCE_ARN", "arn:aws:sso:::instance/ssoins-1234567890abcdef")
    monkeypatch.setenv("AWS__TENANT__ORG_ROLE", "arn:aws:iam::123456789012:role/org-role")

    await _boot_fails_naming("org_role")


async def test_aws_unknown_key_in_the_table_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    with (tmp_path / "config" / "ci.toml").open("a", encoding="utf-8") as ci_file:
        ci_file.write("\n[aws]\nretry_max_attemps = 3\n")
    monkeypatch.setattr(
        host_configuration,
        "load_configuration_files",
        lambda environment, directory=None: load_configuration_files(environment, tmp_path / "config"),
    )

    await _boot_fails_naming("retry_max_attemps")


@pytest.mark.parametrize(
    "table",
    [
        "sre_ops",
        "cloud_operations",
        "incident_core",
        "incident_response",
        "incident_postmortem",
        "cloud_operations_spending",
        "talent",
        "sentinel",
    ],
)
async def test_feature_unknown_key_in_the_table_fails_boot_naming_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, table: str
) -> None:
    """The feature slices the legacy modules read validate at boot with the vendor slices."""
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    with (tmp_path / "config" / "ci.toml").open("a", encoding="utf-8") as ci_file:
        ci_file.write(f"\n[{table}]\nnot_a_feature_key = 1\n")
    monkeypatch.setattr(
        host_configuration,
        "load_configuration_files",
        lambda environment, directory=None: load_configuration_files(environment, tmp_path / "config"),
    )
    for getter in _FEATURE_GETTERS:
        getter.cache_clear()

    try:
        await _boot_fails_naming("not_a_feature_key")
    finally:
        for getter in _FEATURE_GETTERS:
            getter.cache_clear()


async def test_absent_vendor_entries_boot_without_a_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    connects: list[object] = []
    real_connect = socket.socket.connect

    def _spy_connect(self: socket.socket, address: tuple[object, ...] | str) -> None:
        connects.append(address)
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", _spy_connect)
    reached_yield = False

    with ExitStack() as stack:
        _stub_later_phases(stack)
        async with lifespan(FastAPI()):
            reached_yield = True

    assert reached_yield is True
    assert get_slack_settings().tenant is None
    assert get_google_workspace_settings().tenant is None
    assert get_aws_settings().tenant is None
    assert get_openai_settings().tenant is None
    assert all(getter().tenant is None for getter in _VENDOR_GETTERS)
    assert get_sentinel_settings().customer_id == ""
    assert connects == []


def _with_ci_file_lines(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, lines: str) -> None:
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    with (tmp_path / "config" / "ci.toml").open("a", encoding="utf-8") as ci_file:
        ci_file.write(lines)
    monkeypatch.setattr(
        host_configuration,
        "load_configuration_files",
        lambda environment, directory=None: load_configuration_files(environment, tmp_path / "config"),
    )


async def test_openai_unknown_key_in_the_table_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _with_ci_file_lines(monkeypatch, tmp_path, "\n[openai]\ntimeout_second = 30\n")

    await _boot_fails_naming("timeout_second")


async def test_openai_tenant_without_the_key_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _with_ci_file_lines(monkeypatch, tmp_path, '\n[openai.tenant]\nbase_url = "https://models.example.test"\nmodel = "m"\n')

    await _boot_fails_naming("OPENAI__API_KEY")


async def test_openai_key_without_the_tenant_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI__API_KEY", "sk-boot-0001")

    rendered = await _boot_fails_naming("OPENAI__API_KEY")

    assert "sk-boot-0001" not in rendered


async def test_notify_tenant_without_the_secret_fails_boot_naming_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _with_ci_file_lines(monkeypatch, tmp_path, '\n[notify.tenant]\napi_url = "https://notify.example.test"\n')
    monkeypatch.setenv("NOTIFY__SRE_USER_NAME", "notify-boot-0001")

    rendered = await _boot_fails_naming("NOTIFY__SRE_CLIENT_SECRET")

    assert "notify-boot-0001" not in rendered


async def test_trello_token_without_the_app_key_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRELLO__TENANT__TOKEN", "trello-boot-0001")

    rendered = await _boot_fails_naming("TRELLO__TENANT__APP_KEY")

    assert "trello-boot-0001" not in rendered


async def test_opsgenie_key_without_the_tenant_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPSGENIE__INTEGRATIONS_KEY", "genie-boot-0001")

    rendered = await _boot_fails_naming("OPSGENIE__INTEGRATIONS_KEY")

    assert "genie-boot-0001" not in rendered


async def test_maxmind_unknown_key_in_the_table_fails_boot_naming_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _with_ci_file_lines(monkeypatch, tmp_path, '\n[maxmind]\ndb_path = "./geodb/GeoLite2-City.mmdb"\n')

    await _boot_fails_naming("db_path")
