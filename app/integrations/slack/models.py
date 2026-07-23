"""Temporary host both legacy platform-specific models and command parsing models during transition.
---
Platform-agnostic data models for cross-platform features.

These models provide a standard interface for platform-specific data,
allowing business logic to remain platform-independent while platforms
translate their native formats to/from these models.

Usage:
    # Platform provider parses platform-specific payload
    command = CommandPayload(
        text="/sre groups add user@example.com --group=eng-team",
        user_id="U12345",
        user_email="requester@example.com",
        channel_id="C67890",
    )

    # Business logic processes standard format
    result = execute_command(command)

    # Platform provider formats response for platform
    response = format_to_slack_blocks(result)

---
Argument definition models for command parsing.

Provides:
- ArgumentType: Enum of supported argument types
- Argument: Definition of a single command argument (positional, flag, or option)
- ArgumentParsingError: Exception raised when parsing fails
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
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
            self.correlation_id = f"cmd-{datetime.utcnow().timestamp()}"


@dataclass
class CommandResponse:
    """Platform-agnostic command response."""

    message: str
    ephemeral: bool = False
    blocks: list[dict[str, Any]] | None = None
    attachments: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandDefinition:
    """Command metadata for auto-help generation.

    Supports hierarchical command trees with auto-generated intermediate nodes.

    Attributes:
        name: Command name (e.g., "aws", "google", "dev")
        handler: Optional handler (None for auto-generated intermediate nodes)
        description: English description for fallback
        description_key: i18n translation key (e.g., "geolocate.slack.description")
        usage_hint: Usage string (e.g., "<ip_address>")
        examples: List of example invocations (just the arguments, not full command)
        example_keys: List of translation keys for examples
        parent: Parent command path in dot notation (e.g., "sre.dev" for /sre dev aws)
        full_path: Full command path (e.g., "sre.dev.aws") - computed automatically
        is_auto_generated: True if this node was auto-created for hierarchy
        legacy_mode: True to bypass help interception and pass all text to handler
        arguments: List of Argument definitions for parsing
        schema: Pydantic schema for validation
        argument_mapper: Function to transform parsed args to schema fields
        fallback_handler: Optional handler called when command expects arguments but none provided
    """

    name: str
    handler: Callable[..., CommandResponse] | None = None
    description: str = ""
    description_key: str | None = None
    usage_hint: str = ""
    examples: list[str] = field(default_factory=list)
    example_keys: list[str] = field(default_factory=list)
    parent: str | None = None
    full_path: str = field(init=False)
    is_auto_generated: bool = False
    legacy_mode: bool = False
    arguments: list[Any] | None = None  # List[Argument] from parsing.models
    schema: type[Any] | None = None  # Type[BaseModel] for validation
    argument_mapper: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    fallback_handler: Callable[[CommandPayload], CommandResponse] | None = None

    def __post_init__(self):
        """Compute full_path from parent and name."""
        if self.parent:
            # parent="sre.dev" + name="aws" -> full_path="sre.dev.aws"
            self.full_path = f"{self.parent}.{self.name}"
        else:
            # No parent -> top-level command
            self.full_path = self.name


# View/Modal Models
@dataclass
class ViewField:
    """Single form field in a view/modal."""

    field_id: str
    field_type: str  # text, select, date, etc.
    label: str
    required: bool = False
    placeholder: str = ""
    options: list[dict[str, str]] | None = None


@dataclass
class ViewDefinition:
    """Platform-agnostic view/modal definition."""

    view_id: str
    title: str
    fields: list[ViewField]
    submit_label: str = "Submit"
    cancel_label: str = "Cancel"
    callback_url: str = ""  # HTTP endpoint for submission


@dataclass
class ViewSubmission:
    """Data submitted from view/modal."""

    view_id: str
    user_id: str
    user_email: str | None
    field_values: dict[str, Any]
    correlation_id: str = ""


# Interactive Card Models
class CardElementType(Enum):
    """Types of interactive elements in cards."""

    BUTTON = "button"
    SELECT = "select"
    DATE_PICKER = "date_picker"
    TEXT_INPUT = "text_input"


class CardActionStyle(Enum):
    """Visual styles for card actions."""

    DEFAULT = "default"
    PRIMARY = "primary"
    DANGER = "danger"
    SUCCESS = "success"


@dataclass
class CardAction:
    """Interactive action in a card (button, dropdown, etc.)."""

    action_id: str
    action_type: CardElementType
    label: str
    value: str | None = None
    url: str | None = None  # For link buttons
    callback_url: str | None = None  # HTTP endpoint for interaction
    style: CardActionStyle = CardActionStyle.DEFAULT


@dataclass
class CardSection:
    """Section within a card."""

    text: str
    markdown: bool = True
    actions: list[CardAction] | None = None
    fields: list[dict[str, str]] | None = None  # Key-value pairs


@dataclass
class CardDefinition:
    """Platform-agnostic interactive card definition."""

    title: str
    sections: list[CardSection]
    footer: str | None = None
    color: str | None = None  # Accent color (hex)
    timestamp: datetime | None = None


# HTTP Request Models
@dataclass
class HttpEndpointRequest:
    """Standard HTTP request to internal endpoint."""

    method: str  # GET, POST, PUT, DELETE
    path: str  # /api/v1/groups/add
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] | None = None
    timeout_seconds: int = 30


@dataclass
class HttpEndpointResponse:
    """Standard HTTP response from internal endpoint."""

    status_code: int
    headers: dict[str, str]
    body: dict[str, Any] | None = None
    raw_text: str | None = None


__all__ = [
    # Command models
    "CommandPayload",
    "CommandResponse",
    "CommandDefinition",
    # View/Modal models
    "ViewField",
    "ViewDefinition",
    "ViewSubmission",
    # Card models
    "CardElementType",
    "CardActionStyle",
    "CardAction",
    "CardSection",
    "CardDefinition",
    # HTTP models
    "HttpEndpointRequest",
    "HttpEndpointResponse",
]
