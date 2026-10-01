"""Platform-agnostic Slack command models.

Command payload and response models let business logic stay independent of
the platform: a provider translates its native payload into a CommandPayload
and renders the returned CommandResponse back into the platform format.

Argument definition models describe how command text is parsed:

- ArgumentType: supported argument types
- Argument: definition of a single argument (positional, flag or option)
- ArgumentParsingError: raised when parsing fails
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ArgumentType(StrEnum):
    """Supported argument types for parsing and validation."""

    STRING = "string"
    EMAIL = "email"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    CHOICE = "choice"
    CSV = "csv"  # Comma-separated values


@dataclass
class Argument:
    """Definition of a single command argument.

    Supports:
    - Positional args: name="group_id"
    - Flags: name="--managed" (automatically boolean)
    - Options: name="--role" (takes a value)
    - Aliases: name="--role,-r" (alternative flag names)

    Attributes:
        name: Argument name (e.g., 'group_id', '--role', '--managed').
        type: Argument type for validation. Defaults to STRING.
        required: Whether argument is required. Defaults to False.
        description: Human-readable description.
        description_key: i18n translation key for description.
        choices: Valid choices for CHOICE type.
        default: Default value if not provided.
        aliases: Alternative names (e.g., ['-r'] for '--role').
        allow_multiple: Whether argument can be specified multiple times.
    """

    name: str
    """Argument name (e.g., 'group_id', '--role', '--managed')"""

    type: ArgumentType = ArgumentType.STRING
    """Argument type for validation"""

    required: bool = False
    """Whether argument is required"""

    description: str = ""
    """Human-readable description"""

    description_key: str | None = None
    """i18n translation key"""

    choices: list[str] | None = None
    """Valid choices (for CHOICE type)"""

    default: Any | None = None
    """Default value if not provided"""

    aliases: list[str] | None = None
    """Alternative names (e.g., ['-r'] for '--role')"""

    allow_multiple: bool = False
    """Whether argument can be specified multiple times"""

    @property
    def is_flag(self) -> bool:
        """Is this a boolean flag (--managed)?"""
        return self.type == ArgumentType.BOOLEAN and self.name.startswith("--")

    @property
    def is_option(self) -> bool:
        """Is this an option that takes a value (--role VALUE)?"""
        return self.name.startswith("--") and not self.is_flag

    @property
    def is_positional(self) -> bool:
        """Is this a positional argument?"""
        return not self.name.startswith("--")

    def get_canonical_name(self) -> str:
        """Get the canonical name (primary flag/option name)."""
        # For flags/options, it's the first part before any aliases
        # For positionals, just return the name
        return self.name.split(",")[0].strip()


@dataclass
class ArgumentParsingError(Exception):
    """Raised when argument parsing fails.

    Attributes:
        argument: The argument that failed to parse.
        message: Error message.
        suggestion: Optional suggestion for fixing the error.
    """

    argument: str
    message: str
    suggestion: str | None = None

    def __str__(self) -> str:
        """Format error message for display."""
        result = f"Error parsing {self.argument}: {self.message}"
        if self.suggestion:
            result += f"\n  Suggestion: {self.suggestion}"
        return result


@dataclass
class CommandPayload:
    """Platform-agnostic command data extracted from platform events.

    Attributes:
        text: Full command text (e.g., "/sre groups add user@example.com")
        user_id: Platform-specific user ID
        user_email: User's email address (if available from platform)
        channel_id: Channel/conversation ID where command was invoked
        user_locale: User's locale (e.g., "en-US", "fr-FR") for i18n
        response_url: URL for sending async responses (Slack, Teams)
        correlation_id: For distributed tracing and debugging
        platform_metadata: Platform-specific extras not normalized
    """

    text: str
    user_id: str
    user_email: str | None = None
    channel_id: str | None = None
    user_locale: str = "en-US"
    response_url: str | None = None
    correlation_id: str = ""
    platform_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate correlation ID if not provided."""
        if not self.correlation_id:
            self.correlation_id = f"cmd-{datetime.now(UTC).timestamp()}"


@dataclass
class CommandResponse:
    """Platform-agnostic command response."""

    message: str
    ephemeral: bool = False
    blocks: list[dict[str, Any]] | None = None
    attachments: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "Argument",
    "ArgumentParsingError",
    "ArgumentType",
    "CommandPayload",
    "CommandResponse",
]
