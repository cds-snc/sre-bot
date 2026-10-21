"""Integration tests for vendor settings slices in lifespan's configuration phase.

The real lifespan runs with every later phase stubbed (core services, security,
directory, the Slack provider, plugins, translation), so only the configuration
phase does real work. The vendor slices are built from monkeypatched
environment variables with their caches cleared and the .env file disabled. A
recording spy replaces socket.connect to show the configuration phase opens no
connection. An invalid vendor slice must stop startup before the lifespan
yields and before core services are built.
"""

import socket
from collections.abc import Iterator
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from integrations.google_workspace.settings import GoogleWorkspaceSettings, get_google_workspace_settings
from integrations.slack.settings import SlackSettings, get_slack_settings
from server.lifespan import lifespan

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _vendor_slices_without_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the vendor slices from the environment only, fresh for each test."""
    monkeypatch.setitem(SlackSettings.model_config, "env_file", None)
    monkeypatch.setitem(GoogleWorkspaceSettings.model_config, "env_file", None)
    monkeypatch.setenv("SLACK_ENABLED", "false")
    monkeypatch.delenv("SLACK_TEAM_ID", raising=False)
    monkeypatch.setenv("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", "")
    monkeypatch.delenv("GOOGLE_WORKSPACE_CUSTOMER_ID", raising=False)
    get_slack_settings.cache_clear()
    get_google_workspace_settings.cache_clear()
    yield
    get_slack_settings.cache_clear()
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


async def _boot_fails_naming(key: str) -> None:
    reached_yield = False
    with ExitStack() as stack:
        core_services = _stub_later_phases(stack)
        with pytest.raises(ValidationError, match=key):
            async with lifespan(FastAPI()):
                reached_yield = True

    assert reached_yield is False
    core_services.assert_not_awaited()


async def test_slack_transport_on_without_team_id_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_ENABLED", "true")
    monkeypatch.setenv("SLACK_SOCKET_MODE", "true")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-token")

    await _boot_fails_naming("SLACK_TEAM_ID")


async def test_google_key_with_the_my_customer_alias_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", '{"type": "service_account"}')
    monkeypatch.setenv("GOOGLE_WORKSPACE_CUSTOMER_ID", "my_customer")

    await _boot_fails_naming("GOOGLE_WORKSPACE_CUSTOMER_ID")


async def test_google_customer_id_without_the_key_fails_boot_naming_the_key_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_WORKSPACE_CUSTOMER_ID", "C03abc123")

    await _boot_fails_naming("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE")


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
    assert get_slack_settings().team_id is None
    assert get_google_workspace_settings().gcp_sre_service_account_key_file == ""
    assert connects == []
