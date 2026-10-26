"""Integration tests for vendor settings slices in lifespan's configuration phase.

The real lifespan runs with every later phase stubbed (core services, security,
directory, the Slack provider, plugins, translation), so only the configuration
phase does real work. The vendor slices are built from monkeypatched
environment variables with their caches cleared and the .env file disabled. A
recording spy replaces socket.connect to show the configuration phase opens no
connection. An invalid vendor slice must stop startup with a ConfigurationError naming the
key, before the lifespan yields and before core services are built.
"""

import socket
from collections.abc import Iterator
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from structlog.testing import capture_logs

from contracts.configuration import ConfigurationError
from integrations.google_workspace.settings import GoogleWorkspaceSettings, get_google_workspace_settings
from integrations.slack.settings import SlackSettings, get_slack_settings
from server.slack.settings import get_slack_transport_settings
from tests.factories.lifespan import lifespan

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _vendor_slices_without_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the vendor slices from the environment only, fresh for each test."""
    monkeypatch.setitem(SlackSettings.model_config, "env_file", None)
    monkeypatch.setitem(GoogleWorkspaceSettings.model_config, "env_file", None)
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
    yield
    get_slack_settings.cache_clear()
    get_slack_transport_settings.cache_clear()
    get_google_workspace_settings.cache_clear()


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
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY", '{"private_key": "secret-key-boot-0001"}')
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "my_customer")

    rendered = await _boot_fails_naming("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID")

    assert "secret-key-boot-0001" not in rendered


async def test_google_tenant_without_the_key_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID", "C03abc123")

    await _boot_fails_naming("GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY")


async def test_google_delegated_user_without_the_tenant_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL", "delegated-boot-0001@example.com")

    rendered = await _boot_fails_naming("GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL")

    assert "delegated-boot-0001@example.com" not in rendered


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
    assert connects == []
