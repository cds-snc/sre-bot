"""Discord client facade.

Placeholder for Discord SDK integration (currently out of scope).
"""

import structlog
from typing import Any, Dict, List, Optional

from infrastructure.operations import OperationResult

logger = structlog.get_logger()


class DiscordClientFacade:
    """Facade for Discord SDK (placeholder - not yet implemented).

    This class is a placeholder for future Discord integration.
    Discord-related features are currently out of scope per project requirements.

    Args:
        token: Discord bot token

    Note:
        All methods return NotImplementedError until Discord integration
        is added to project scope.
    """

    def __init__(self, token: str):
        """Initialize Discord client facade.

        Args:
            token: Discord bot token
        """
        self._token = token
        self._log = logger.bind(component="discord_client_facade")
        self._log.warning(
            "discord_client_not_implemented",
            message="Discord integration is out of scope",
        )

    def send_message(
        self,
        channel_id: str,
        content: Optional[str] = None,
        embeds: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> OperationResult:
        """Send a message to a Discord channel.

        Args:
            channel_id: Discord channel ID
            content: Plain text message content
            embeds: List of Discord embed objects
            **kwargs: Additional message parameters

        Returns:
            OperationResult with NotImplementedError
        """
        return OperationResult.permanent_error(
            message="Discord integration not implemented (out of scope)",
            error_code="DISCORD_NOT_IMPLEMENTED",
        )

    def edit_message(
        self,
        channel_id: str,
        message_id: str,
        content: Optional[str] = None,
        embeds: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> OperationResult:
        """Edit an existing Discord message.

        Args:
            channel_id: Discord channel ID
            message_id: Message ID to edit
            content: New plain text content
            embeds: New embed objects
            **kwargs: Additional message parameters

        Returns:
            OperationResult with NotImplementedError
        """
        return OperationResult.permanent_error(
            message="Discord integration not implemented (out of scope)",
            error_code="DISCORD_NOT_IMPLEMENTED",
        )

    def get_channel(self, channel_id: str) -> OperationResult:
        """Get information about a Discord channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            OperationResult with NotImplementedError
        """
        return OperationResult.permanent_error(
            message="Discord integration not implemented (out of scope)",
            error_code="DISCORD_NOT_IMPLEMENTED",
        )

    def get_user(self, user_id: str) -> OperationResult:
        """Get information about a Discord user.

        Args:
            user_id: Discord user ID

        Returns:
            OperationResult with NotImplementedError
        """
        return OperationResult.permanent_error(
            message="Discord integration not implemented (out of scope)",
            error_code="DISCORD_NOT_IMPLEMENTED",
        )

    @property
    def is_available(self) -> bool:
        """Check if Discord SDK is available.

        Returns:
            Always False (not implemented)
        """
        return False
