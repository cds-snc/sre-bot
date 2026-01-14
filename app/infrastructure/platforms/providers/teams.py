"""Microsoft Teams platform provider.

HTTP-based platform provider for Microsoft Teams Bot Framework integration.

Connection Mode: HTTP (Webhook-based)
- Teams sends events via HTTP POST to webhook endpoints
- No persistent WebSocket connection required
- Signature verification for security

Example:
    >>> from infrastructure.platforms.providers.teams import TeamsPlatformProvider
    >>> from infrastructure.configuration.infrastructure.platforms import TeamsPlatformSettings
    >>>
    >>> settings = TeamsPlatformSettings(
    ...     ENABLED=True,
    ...     APP_ID="your-app-id",
    ...     APP_PASSWORD="your-app-password"
    ... )
    >>> provider = TeamsPlatformProvider(settings=settings)
    >>> caps = provider.get_capabilities()
    >>> caps.connection_mode
    'http'
"""

import structlog
from typing import Any, Dict, Optional

from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import (
    CapabilityDeclaration,
    PlatformCapability,
    create_capability_declaration,
)
from infrastructure.platforms.formatters.teams import TeamsAdaptiveCardsFormatter
from infrastructure.platforms.providers.base import BasePlatformProvider

logger = structlog.get_logger()


class TeamsPlatformProvider(BasePlatformProvider):
    """Microsoft Teams platform provider with HTTP webhook support.

    Provides Teams Bot Framework integration via HTTP webhooks. Unlike Slack's
    Socket Mode, Teams uses standard HTTP POST webhooks for all bot interactions.

    Key Features:
    - HTTP webhook-based communication (no WebSocket)
    - Bot Framework SDK compatibility
    - Adaptive Cards formatting
    - Task modules and messaging extensions
    - Activity-based event handling

    Attributes:
        _settings: Teams platform configuration
        _formatter: TeamsAdaptiveCardsFormatter for response formatting
        _app_initialized: Whether Bot Framework app has been configured

    Example:
        >>> provider = TeamsPlatformProvider(settings=teams_settings)
        >>> result = provider.send_message(
        ...     channel="19:meeting_thread_id",
        ...     message={"text": "Hello Teams!"}
        ... )
        >>> if result.is_success:
        ...     print("Message sent successfully")
    """

    def __init__(
        self,
        settings,  # TeamsPlatformSettings type
        formatter: Optional[TeamsAdaptiveCardsFormatter] = None,
        name: str = "teams",
        version: str = "1.0.0",
    ):
        """Initialize Teams platform provider.

        Args:
            settings: TeamsPlatformSettings instance with app credentials and config
            formatter: Optional TeamsAdaptiveCardsFormatter for response formatting
            name: Provider name (default: "teams")
            version: Provider version (default: "1.0.0")
        """
        super().__init__(
            name=name,
            version=version,
            enabled=settings.ENABLED,
        )

        self._settings = settings
        self._formatter = formatter or TeamsAdaptiveCardsFormatter()

        # Will be initialized when app is started
        self._app = None
        self._adapter = None
        self._app_initialized = False

        self._logger.info(
            "teams_provider_initialized",
            connection_mode="http",
            enabled=settings.ENABLED,
        )

    def get_capabilities(self) -> CapabilityDeclaration:
        """Get Teams platform capabilities.

        Returns:
            CapabilityDeclaration with supported Teams capabilities
        """
        return create_capability_declaration(
            "teams",
            PlatformCapability.COMMANDS,
            PlatformCapability.INTERACTIVE_CARDS,
            PlatformCapability.VIEWS_MODALS,
            PlatformCapability.FILE_SHARING,
            PlatformCapability.REACTIONS,
            metadata={
                "connection_mode": "http",
                "platform": "teams",
                "framework": "botframework",
            },
        )

    def send_message(
        self,
        channel: str,
        message: Dict[str, Any],
        thread_ts: Optional[str] = None,
    ) -> OperationResult:
        """Send a message to a Teams channel or chat.

        Args:
            channel: Teams conversation/channel ID (e.g., "19:meeting_id@thread.v2")
            message: Message payload (Adaptive Card or text)
            thread_ts: Optional reply-to message ID (not commonly used in Teams)

        Returns:
            OperationResult with send status

        Example:
            >>> result = provider.send_message(
            ...     channel="19:meeting_id@thread.v2",
            ...     message={"text": "Hello!", "attachments": [...]}
            ... )
        """
        log = self._logger.bind(channel=channel, has_thread=bool(thread_ts))
        log.info("sending_teams_message")

        if not self.enabled:
            log.warning("teams_provider_disabled")
            return OperationResult.permanent_error(
                message="Teams provider is disabled",
                error_code="PROVIDER_DISABLED",
            )

        # Validate message
        if not message:
            log.error("empty_message_provided")
            return OperationResult.permanent_error(
                message="Message cannot be empty",
                error_code="INVALID_MESSAGE",
            )

        log.debug("preparing_teams_message")

        # Build Teams activity payload
        payload: dict[str, Any] = {
            "type": "message",
            "conversation": {"id": channel},
        }

        # Merge message content (Adaptive Card or simple text)
        payload.update(message)

        # Add reply-to reference if provided (optional in Teams)
        if thread_ts:
            payload["replyToId"] = thread_ts

        log.info(
            "teams_message_prepared",
            channel=channel,
            has_attachments="attachments" in message,
        )

        # In real implementation, this would call Bot Framework Connector API
        # For now, return success to indicate message was formatted correctly
        return OperationResult.success(
            message="Message formatted for Teams",
            data={"channel": channel, "payload": payload},
        )

    def format_response(
        self,
        data: Dict[str, Any],
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format response using TeamsAdaptiveCardsFormatter.

        Args:
            data: Response data payload
            error: Optional error message

        Returns:
            Formatted response dict with Teams Adaptive Card
        """
        if error:
            return self._formatter.format_error(message=error)
        return self._formatter.format_success(data=data)

    def initialize_app(self) -> OperationResult:
        """Initialize Teams Bot Framework application.

        For HTTP mode, this validates configuration but doesn't establish
        a persistent connection (unlike Slack Socket Mode).

        Returns:
            OperationResult indicating initialization status

        Example:
            >>> result = provider.initialize_app()
            >>> if result.is_success:
            ...     print("Teams app configured")
        """
        log = self._logger.bind(connection_mode="http")
        log.info("initializing_teams_app")

        if not self._settings.ENABLED:
            log.warning("teams_disabled_skipping_init")
            return OperationResult.success(
                message="Teams provider disabled, skipping initialization"
            )

        # Validate required credentials
        if not self._settings.APP_ID:
            log.error("missing_app_id")
            return OperationResult.permanent_error(
                message="APP_ID is required",
                error_code="MISSING_APP_ID",
            )

        if not self._settings.APP_PASSWORD:
            log.error("missing_app_password")
            return OperationResult.permanent_error(
                message="APP_PASSWORD is required",
                error_code="MISSING_APP_PASSWORD",
            )

        # TODO: Initialize Bot Framework Adapter when ready
        # from botbuilder.core import BotFrameworkAdapter
        # from botbuilder.schema import Activity
        #
        # self._adapter = BotFrameworkAdapter(
        #     app_id=self._settings.APP_ID,
        #     app_password=self._settings.APP_PASSWORD
        # )

        self._app_initialized = True

        log.info("teams_app_initialized_placeholder")
        return OperationResult.success(
            data={"initialized": True, "connection_mode": "http"},
            message="Teams app initialization completed (placeholder)",
        )

    @property
    def formatter(self) -> TeamsAdaptiveCardsFormatter:
        """Get the Teams Adaptive Cards formatter.

        Returns:
            TeamsAdaptiveCardsFormatter instance
        """
        return self._formatter

    @property
    def settings(self):
        """Get Teams platform settings.

        Returns:
            TeamsPlatformSettings instance
        """
        return self._settings
