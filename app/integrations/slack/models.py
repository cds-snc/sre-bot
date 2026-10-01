"""Slack command metadata, view, card and HTTP models.

The command payload, response and argument models live in
contracts.slack.models.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from contracts.slack.models import CommandPayload, CommandResponse


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
