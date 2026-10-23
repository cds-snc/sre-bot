"""Integration tests for the security settings slice in lifespan's configuration phase.

The real lifespan runs with every later phase stubbed (core services, security,
directory, the Slack provider, plugins, translation), so only the configuration
phase does real work. The security slice and the vendor slices validated beside
it are built from monkeypatched environment variables with their caches cleared
and the .env file disabled. An invalid security slice must stop startup before
the lifespan yields and before core services are built, with the error naming
the key.
"""

import json
from collections.abc import Iterator
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from contracts.configuration import ConfigurationError
from infrastructure.security.settings import SecuritySettings, get_security_settings
from integrations.google_workspace.settings import GoogleWorkspaceSettings, get_google_workspace_settings
from integrations.slack.settings import SlackSettings, get_slack_settings
from tests.factories.lifespan import lifespan

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _security_slice_without_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the security slice, and the vendor slices beside it, from the environment only."""
    monkeypatch.setitem(SecuritySettings.model_config, "env_file", None)
    monkeypatch.setitem(SlackSettings.model_config, "env_file", None)
    monkeypatch.setitem(GoogleWorkspaceSettings.model_config, "env_file", None)
    monkeypatch.setenv("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", "")
    monkeypatch.delenv("GOOGLE_WORKSPACE_CUSTOMER_ID", raising=False)
    for field in SecuritySettings.model_fields:
        monkeypatch.delenv(f"SECURITY__{field.upper()}", raising=False)
    caches = (get_security_settings, get_slack_settings, get_google_workspace_settings)
    for cache in caches:
        cache.cache_clear()
    yield
    for cache in caches:
        cache.cache_clear()


def _stub_later_phases(stack: ExitStack) -> tuple[AsyncMock, MagicMock]:
    provider = MagicMock()
    provider.app = None
    core_services = AsyncMock()
    security = MagicMock()
    stack.enter_context(patch("server.lifespan.initialize_core_services", core_services))
    stack.enter_context(patch("server.lifespan._initialize_security_services", security))
    stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
    stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
    stack.enter_context(patch("server.lifespan.load_plugins"))
    stack.enter_context(patch("server.lifespan._initialize_translation_service"))
    stack.enter_context(patch("server.lifespan.register_feature_integrations"))
    stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))
    stack.enter_context(patch("server.lifespan._start_scheduled_tasks"))
    stack.enter_context(patch("server.lifespan._stop_scheduled_tasks"))
    return core_services, security


async def _boot_fails_naming(key: str) -> None:
    reached_yield = False
    with ExitStack() as stack:
        core_services, _ = _stub_later_phases(stack)
        with pytest.raises(ConfigurationError, match=key):
            async with lifespan(FastAPI()):
                reached_yield = True

    assert reached_yield is False
    core_services.assert_not_awaited()


async def test_wildcard_cors_origin_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__CORS_ALLOWED_ORIGINS", '["*"]')

    await _boot_fails_naming("cors_allowed_origins")


async def test_issuer_without_audience_fails_boot_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__ISSUERS", json.dumps([{"issuer": "issuer-1", "jwks_uri": "https://issuer.example.com/jwks"}]))

    await _boot_fails_naming("issuers.0.audience")


async def test_valid_security_slice_boots_and_reaches_security_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__CORS_ALLOWED_ORIGINS", '["https://frontend.example"]')
    reached_yield = False

    with ExitStack() as stack:
        _, security = _stub_later_phases(stack)
        async with lifespan(FastAPI()):
            reached_yield = True

    assert reached_yield is True
    security_settings = security.call_args.args[0]
    assert isinstance(security_settings, SecuritySettings)
    assert security_settings.cors_allowed_origins == ["https://frontend.example"]
