"""Standalone SlackBot service for agent-first interaction registration.

This service coexists with the legacy PlatformService-based Slack provider and
provides a dedicated registration surface for feature hooks.
"""

from functools import cache
from typing import Any, Callable

import structlog

from infrastructure.configuration.integrations.slack import (
    SlackSettings,
    get_slack_settings,
)
from infrastructure.operations import OperationResult
from infrastructure.platforms.clients.slack import SlackClientFacade, get_slack_client
from infrastructure.platforms.providers.slack import SlackPlatformProvider

logger = structlog.get_logger()


class SlackBot:
    """Dedicated Slack service for feature interaction registration.

    The service wraps the existing SlackPlatformProvider to preserve behavior
    while offering a standalone dependency boundary for phased monolith
    decomposition.
    """

    def __init__(
        self,
        slack_settings: SlackSettings,
        slack_client: SlackClientFacade,
    ) -> None:
        self._settings = slack_settings
        self._slack_client = slack_client
        self._provider = SlackPlatformProvider(settings=slack_settings)
        self._view_handlers: dict[str, Callable[..., Any]] = {}
        self._action_handlers: dict[str, Callable[..., Any]] = {}
        self._logger = logger.bind(component="slack_bot")

    def initialize_app(self) -> OperationResult:
        """Initialize Slack transport and bind deferred interaction handlers."""
        result = self._provider.initialize_app()
        if not result.is_success:
            return result

        app = self._provider.app
        if app is not None:
            for callback_id, handler in self._view_handlers.items():
                app.view(callback_id)(handler)
            for action_id, handler in self._action_handlers.items():
                app.action(action_id)(handler)

        return result

    def start(self) -> OperationResult:
        """Start Slack transport lifecycle when socket mode is enabled."""
        return self._provider.start()

    def stop(self) -> None:
        """Stop Slack transport lifecycle."""
        self._provider.stop()

    def register_command(self, *args: Any, **kwargs: Any) -> None:
        """Register a command using the underlying Slack provider contract."""
        self._provider.register_command(*args, **kwargs)

    def register_view_handler(
        self, callback_id: str, handler: Callable[..., Any]
    ) -> None:
        """Register a Slack view (modal) handler by callback id."""
        self._view_handlers[callback_id] = handler
        if self._provider.app is not None:
            self._provider.app.view(callback_id)(handler)

    def register_action_handler(
        self, action_id: str, handler: Callable[..., Any]
    ) -> None:
        """Register a Slack block/action handler by action id."""
        self._action_handlers[action_id] = handler
        if self._provider.app is not None:
            self._provider.app.action(action_id)(handler)

    @property
    def provider(self) -> SlackPlatformProvider:
        """Expose wrapped provider for phased backward compatibility."""
        return self._provider

    @property
    def app(self) -> Any:
        """Expose managed Slack Bolt app for compatibility with startup wiring."""
        return self._provider.app

    @property
    def socket_mode_handler(self) -> Any:
        """Expose socket mode handler managed by the underlying provider."""
        return self._provider.socket_mode_handler


@cache
def get_slack_bot() -> SlackBot:
    """Get application-scoped standalone SlackBot singleton.

    Returns:
        SlackBot: Cached standalone Slack service.
    """

    return SlackBot(
        slack_settings=get_slack_settings(),
        slack_client=get_slack_client(),
    )
