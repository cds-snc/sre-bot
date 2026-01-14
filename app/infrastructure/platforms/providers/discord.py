"""Discord platform provider.

⚠️ OUT OF SCOPE - NOT PLANNED FOR CURRENT IMPLEMENTATION ⚠️

This module is a placeholder for future Discord integration.
Discord support is not currently planned or prioritized.

When implemented, this provider would:
- Integrate with discord.py library
- Support Discord slash commands
- Handle Discord interactions and events
- Manage Discord bot lifecycle
- Support Discord-specific features (threads, buttons, select menus)

For reference:
- discord.py Documentation: https://discordpy.readthedocs.io/
- Discord Developer Portal: https://discord.com/developers/docs/
- Slash Commands: https://discord.com/developers/docs/interactions/application-commands
"""

from typing import Any, Dict, Optional

from infrastructure.platforms.providers.base import BasePlatformProvider
from infrastructure.platforms.capabilities.models import PlatformCapability
from infrastructure.operations import OperationResult


class DiscordPlatformProvider(BasePlatformProvider):
    """Placeholder for Discord platform provider.

    ⚠️ NOT IMPLEMENTED - OUT OF SCOPE ⚠️
    """

    def __init__(self, settings, formatter=None):
        """Initialize Discord platform provider."""
        raise NotImplementedError(
            "Discord provider is not implemented. "
            "Discord platform support is out of scope for current release."
        )

    def get_capabilities(self) -> PlatformCapability:
        """Get platform capabilities - NOT IMPLEMENTED."""
        raise NotImplementedError("Discord support is out of scope")

    def send_message(
        self,
        channel: str,
        message: Dict[str, Any],
        thread_ts: Optional[str] = None,
    ) -> OperationResult:
        """Send message - NOT IMPLEMENTED."""
        raise NotImplementedError("Discord support is out of scope")

    def format_response(self, result: OperationResult) -> Dict[str, Any]:
        """Format response - NOT IMPLEMENTED."""
        raise NotImplementedError("Discord support is out of scope")

    def initialize_app(self) -> OperationResult:
        """Initialize Discord bot - NOT IMPLEMENTED."""
        raise NotImplementedError("Discord support is out of scope")
