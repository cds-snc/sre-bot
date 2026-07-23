"""Slack Bot bootstrap module.

Contains Slack integration bootstrap code, including Bolt app factories
and setup helpers.
"""

from slack_bolt import App
from slack_bolt.async_app import AsyncApp
from slack_sdk import WebClient
from slack_sdk.http_retry.async_handler import AsyncRetryHandler
from slack_sdk.http_retry.builtin_async_handlers import (
    AsyncConnectionErrorRetryHandler,
    AsyncRateLimitErrorRetryHandler,
    AsyncServerErrorRetryHandler,
)
from slack_sdk.http_retry.builtin_handlers import (
    ConnectionErrorRetryHandler,
    RateLimitErrorRetryHandler,
    ServerErrorRetryHandler,
)
from slack_sdk.http_retry.handler import RetryHandler
from slack_sdk.web.async_client import AsyncWebClient

from integrations.slack.settings import get_slack_settings


class SlackBootstrap:
    """Bootstrap class for the Slack integration."""

    def __init__(
        self,
    ):
        self.settings = get_slack_settings()
        retry_handlers: list[AsyncRetryHandler] = [
            AsyncConnectionErrorRetryHandler(max_retry_count=self.settings.RETRY_MAX_ATTEMPTS),
            AsyncRateLimitErrorRetryHandler(max_retry_count=self.settings.RETRY_MAX_ATTEMPTS),
            AsyncServerErrorRetryHandler(max_retry_count=self.settings.RETRY_MAX_ATTEMPTS),
        ]
        self.web: AsyncWebClient = AsyncWebClient(
            token=self.settings.BOT_TOKEN,
            timeout=self.settings.REQUEST_TIMEOUT_SECONDS,
            retry_handlers=retry_handlers,
        )

    def create_app(self) -> AsyncApp:
        """Create a Bolt AsyncApp configured from Slack settings."""
        request_verification_enabled = not self.settings.SOCKET_MODE
        app = AsyncApp(
            token=self.settings.BOT_TOKEN,
            client=self.web,
            request_verification_enabled=request_verification_enabled,
        )
        return app


class LegacySlackBootstrap:
    """Legacy Bootstrap class for the Slack integration."""

    def __init__(
        self,
    ):
        self.settings = get_slack_settings()
        retry_handlers: list[RetryHandler] = [
            ConnectionErrorRetryHandler(max_retry_count=self.settings.RETRY_MAX_ATTEMPTS),
            RateLimitErrorRetryHandler(max_retry_count=self.settings.RETRY_MAX_ATTEMPTS),
            ServerErrorRetryHandler(max_retry_count=self.settings.RETRY_MAX_ATTEMPTS),
        ]
        self.web: WebClient = WebClient(
            token=self.settings.BOT_TOKEN,
            timeout=self.settings.REQUEST_TIMEOUT_SECONDS,
            retry_handlers=retry_handlers,
        )

    def create_app(self) -> App:
        """Create a Bolt App configured from Slack settings."""
        request_verification_enabled = not self.settings.SOCKET_MODE
        app = App(
            token=self.settings.BOT_TOKEN,
            client=self.web,
            request_verification_enabled=request_verification_enabled,
        )
        return app
