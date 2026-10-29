"""Slack Bot bootstrap module.

Contains Slack integration bootstrap code, including Bolt app factories and
setup helpers.

The app selects exactly one delivery mode at startup:
- Socket Mode (WebSocket): request authenticity is handled by the connection
    handshake and Bolt request-signature verification is disabled.
- HTTP Events mode: Bolt request-signature verification is enabled for inbound
    HTTP requests.

HTTP-mode per-request HMAC verification details beyond Bolt's built-in
request-verification flow are handled separately and are not implemented here.
"""

from typing import Any

import structlog
from slack_bolt import App
from slack_bolt.async_app import AsyncApp
from slack_sdk import WebClient
from slack_sdk.web.async_client import AsyncWebClient

from integrations.slack.client import get_async_slack_web_client, get_slack_web_client
from integrations.slack.settings import get_slack_settings

logger = structlog.get_logger()


def log_listener_error(error: Exception, body: dict[str, Any]) -> None:
    """Log a failed Bolt listener with the identifiers needed to find the interaction, never the full payload."""
    actions = body.get("actions") or [{}]
    logger.error(
        "slack_listener_error",
        payload_type=body.get("type"),
        event_type=(body.get("event") or {}).get("type"),
        command=body.get("command"),
        callback_id=body.get("callback_id") or (body.get("view") or {}).get("callback_id"),
        action_id=actions[0].get("action_id"),
        action_name=actions[0].get("name"),
        channel_id=(body.get("channel") or {}).get("id") or body.get("channel_id"),
        user_id=(body.get("user") or {}).get("id") or body.get("user_id"),
        error=str(error),
        exc_info=error,
    )


class SlackBootstrap:
    """Bootstrap class for the Slack integration."""

    def __init__(
        self,
    ):
        self.settings = get_slack_settings()
        self.web: AsyncWebClient = get_async_slack_web_client()

    def create_app(self, socket_mode: bool = True) -> AsyncApp:
        """Create a Bolt AsyncApp configured from Slack settings.

        Socket Mode authenticates the connection itself, so HTTP request verification
        runs only in HTTP Events mode (socket_mode false).
        """
        request_verification_enabled = not socket_mode
        app = AsyncApp(
            token=self.settings.bot_token.get_secret_value(),
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
        self.web: WebClient = get_slack_web_client()

    def create_app(self, socket_mode: bool = True) -> App:
        """Create a Bolt App configured from Slack settings.

        Socket Mode authenticates the connection itself, so HTTP request verification
        runs only in HTTP Events mode (socket_mode false).
        """
        request_verification_enabled = not socket_mode
        app = App(
            token=self.settings.bot_token.get_secret_value(),
            client=self.web,
            request_verification_enabled=request_verification_enabled,
        )
        app.error(log_listener_error)
        return app
