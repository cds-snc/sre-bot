"""Platform-agnostic data models for cross-platform features.

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
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = None  # type: ignore


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
    user_email: Optional[str] = None
    channel_id: Optional[str] = None
    user_locale: str = "en-US"
    response_url: Optional[str] = None
    correlation_id: str = ""
    platform_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate correlation ID if not provided."""
        if not self.correlation_id:
            self.correlation_id = f"cmd-{datetime.utcnow().timestamp()}"


@dataclass
class CommandResponse:
    """Platform-agnostic command response."""

    message: str
    ephemeral: bool = False
    blocks: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


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
    handler: Optional[Callable[..., CommandResponse]] = None
    description: str = ""
    description_key: Optional[str] = None
    usage_hint: str = ""
    examples: List[str] = field(default_factory=list)
    example_keys: List[str] = field(default_factory=list)
    parent: Optional[str] = None
    full_path: str = field(init=False)
    is_auto_generated: bool = False
    legacy_mode: bool = False
    arguments: Optional[List[Any]] = None  # List[Argument] from parsing.models
    schema: Optional[Type[Any]] = None  # Type[BaseModel] for validation
    argument_mapper: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    fallback_handler: Optional[Callable[[CommandPayload], CommandResponse]] = None

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
    options: Optional[List[Dict[str, str]]] = None


@dataclass
class ViewDefinition:
    """Platform-agnostic view/modal definition."""

    view_id: str
    title: str
    fields: List[ViewField]
    submit_label: str = "Submit"
    cancel_label: str = "Cancel"
    callback_url: str = ""  # HTTP endpoint for submission


@dataclass
class ViewSubmission:
    """Data submitted from view/modal."""

    view_id: str
    user_id: str
    user_email: Optional[str]
    field_values: Dict[str, Any]
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
    value: Optional[str] = None
    url: Optional[str] = None  # For link buttons
    callback_url: Optional[str] = None  # HTTP endpoint for interaction
    style: CardActionStyle = CardActionStyle.DEFAULT


@dataclass
class CardSection:
    """Section within a card."""

    text: str
    markdown: bool = True
    actions: Optional[List[CardAction]] = None
    fields: Optional[List[Dict[str, str]]] = None  # Key-value pairs


@dataclass
class CardDefinition:
    """Platform-agnostic interactive card definition."""

    title: str
    sections: List[CardSection]
    footer: Optional[str] = None
    color: Optional[str] = None  # Accent color (hex)
    timestamp: Optional[datetime] = None


# HTTP Request Models
@dataclass
class HttpEndpointRequest:
    """Standard HTTP request to internal endpoint."""

    method: str  # GET, POST, PUT, DELETE
    path: str  # /api/v1/groups/add
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    timeout_seconds: int = 30


@dataclass
class HttpEndpointResponse:
    """Standard HTTP response from internal endpoint."""

    status_code: int
    headers: Dict[str, str]
    body: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None


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
