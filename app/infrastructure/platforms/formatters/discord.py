"""Discord Embed response formatter.

⚠️ OUT OF SCOPE - NOT PLANNED FOR CURRENT IMPLEMENTATION ⚠️

This module is a placeholder for future Discord integration.
Discord support is not currently planned or prioritized.

When implemented, this formatter would:
- Format responses as Discord Embed objects
- Support rich embeds with fields, colors, and thumbnails
- Provide proper styling for success/error/info/warning messages
- Follow Discord's embed limits and best practices

For reference:
- Discord Embed Documentation: https://discord.com/developers/docs/resources/channel#embed-object
- Embed limits: 25 fields max, 6000 characters total, 256 characters per field name/value
"""

from typing import Any, Dict, Optional

from infrastructure.platforms.formatters.base import BaseResponseFormatter


class DiscordEmbedFormatter(BaseResponseFormatter):
    """Placeholder for Discord Embed formatter.

    ⚠️ NOT IMPLEMENTED - OUT OF SCOPE ⚠️
    """

    def __init__(self, translation_service=None, locale: str = "en-US"):
        """Initialize Discord Embed formatter."""
        super().__init__(translation_service=translation_service, locale=locale)
        raise NotImplementedError(
            "Discord formatter is not implemented. "
            "Discord platform support is out of scope for current release."
        )

    def format_success(
        self,
        data: Dict[str, Any],
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format success response - NOT IMPLEMENTED."""
        raise NotImplementedError("Discord support is out of scope")

    def format_error(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format error response - NOT IMPLEMENTED."""
        raise NotImplementedError("Discord support is out of scope")

    def format_info(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format info message - NOT IMPLEMENTED."""
        raise NotImplementedError("Discord support is out of scope")
