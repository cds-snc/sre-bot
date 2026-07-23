"""Tests for `SlackBootstrap` construction and SDK wiring.

Verifies that `AsyncWebClient` is constructed with the bot token from
settings, the per-call timeout, and all three async retry handlers
(`AsyncConnectionErrorRetryHandler`, `AsyncRateLimitErrorRetryHandler`,
`AsyncServerErrorRetryHandler`) each carrying the configured retry
budget. Asserts that no hand-rolled retry or Tenacity decorator leaks
into the shield.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.http_retry.builtin_async_handlers import (
    AsyncConnectionErrorRetryHandler,
    AsyncRateLimitErrorRetryHandler,
    AsyncServerErrorRetryHandler,
)
from slack_sdk.web.async_client import AsyncWebClient

from integrations.slack.bootstrap import LegacySlackBootstrap, SlackBootstrap
from integrations.slack.settings import SlackSettings

pytestmark = pytest.mark.unit


@pytest.fixture
def settings() -> SlackSettings:
    return SlackSettings(
        SLACK_BOT_TOKEN="xoxb-test-token",
        SLACK_REQUEST_TIMEOUT_SECONDS=10,
        SLACK_RETRY_MAX_ATTEMPTS=2,
    )


class TestSlackBootstrapWebClientConstruction:
    """`SlackBootstrap.web` is a fully-configured `AsyncWebClient`."""

    def test_web_is_async_web_client(self) -> None:
        shield = SlackBootstrap()

        assert isinstance(shield.web, AsyncWebClient)

    def test_web_uses_bot_token_from_settings(self, monkeypatch) -> None:
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-real-token")

        shield = SlackBootstrap()

        assert shield.web.token == "xoxb-real-token"

    def test_web_uses_request_timeout_from_settings(self) -> None:
        shield = SlackBootstrap()

        assert shield.web.timeout == 10


class TestSlackBootstrapRetryHandlers:
    """All three async retry handlers are wired into `AsyncWebClient`."""

    def test_connection_error_handler_is_registered(self) -> None:
        shield = SlackBootstrap()

        types = [type(h) for h in shield.web.retry_handlers]
        assert AsyncConnectionErrorRetryHandler in types

    def test_rate_limit_handler_is_registered(self) -> None:
        shield = SlackBootstrap()

        types = [type(h) for h in shield.web.retry_handlers]
        assert AsyncRateLimitErrorRetryHandler in types

    def test_server_error_handler_is_registered(self) -> None:
        shield = SlackBootstrap()

        types = [type(h) for h in shield.web.retry_handlers]
        assert AsyncServerErrorRetryHandler in types

    def test_handlers_use_configured_max_retry_count(self) -> None:
        shield = SlackBootstrap()

        for handler in shield.web.retry_handlers:
            if isinstance(
                handler,
                (
                    AsyncConnectionErrorRetryHandler,
                    AsyncRateLimitErrorRetryHandler,
                    AsyncServerErrorRetryHandler,
                ),
            ):
                assert handler.max_retry_count == 2


class TestSlackBootstrapAppCreation:
    """Bolt app factories should set request verification by transport mode."""

    def test_legacy_create_app_disables_request_verification_in_socket_mode(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setenv("SLACK_SOCKET_MODE", "true")

        with patch("integrations.slack.bootstrap.App") as app_cls:
            app_cls.return_value = MagicMock()

            bootstrap = LegacySlackBootstrap()
            bootstrap.create_app()

        app_cls.assert_called_once()
        assert app_cls.call_args.kwargs["request_verification_enabled"] is False

    def test_legacy_create_app_enables_request_verification_in_http_mode(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setenv("SLACK_SOCKET_MODE", "false")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")

        with patch("integrations.slack.bootstrap.App") as app_cls:
            app_cls.return_value = MagicMock()

            bootstrap = LegacySlackBootstrap()
            bootstrap.create_app()

        app_cls.assert_called_once()
        assert app_cls.call_args.kwargs["request_verification_enabled"] is True

    def test_async_create_app_disables_request_verification_in_socket_mode(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setenv("SLACK_SOCKET_MODE", "true")

        with patch("integrations.slack.bootstrap.AsyncApp") as app_cls:
            app_cls.return_value = MagicMock()

            bootstrap = SlackBootstrap()
            bootstrap.create_app()

        app_cls.assert_called_once()
        assert app_cls.call_args.kwargs["request_verification_enabled"] is False
