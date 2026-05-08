"""Slack command and event models.

Platform-specific data models for command payloads, responses, and definitions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class CommandPayload:
    """Command data extracted from Slack event.

    Attributes:
        text: Command text (e.g., "incident list --managed")
        user_id: Slack user ID
        user_email: User email (if available)
        channel_id: Channel ID where command was invoked
        user_locale: User locale (e.g., "en-US")
        response_url: URL for async responses
        correlation_id: For tracing and debugging
        platform_metadata: Slack-specific event data
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
    """Command handler response."""

    message: str
    ephemeral: bool = False
    blocks: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandDefinition:
    """Command metadata for help generation and registration.

    Attributes:
        name: Command name (e.g., "incident")
        handler: Handler function (None for intermediate nodes)
        description: English description
        description_key: i18n key
        usage_hint: Usage string (e.g., "<incident_id>")
        examples: Example invocations
        parent: Parent path in dot notation (e.g., "sre.incident")
        full_path: Full path (computed)
        is_auto_generated: True if auto-created for hierarchy
        legacy_mode: Bypass automatic help interception
        arguments: Argument definitions for parsing
        schema: Pydantic schema for validation
        argument_mapper: Function to transform parsed args
        fallback_handler: Handler when no args provided
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
    arguments: Optional[List[Any]] = None
    schema: Optional[type] = None
    argument_mapper: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    fallback_handler: Optional[Callable[[CommandPayload], CommandResponse]] = None

    def __post_init__(self):
        """Compute full_path."""
        if self.parent:
            self.full_path = f"{self.parent}.{self.name}"
        else:
            self.full_path = self.name


__all__ = [
    "CommandPayload",
    "CommandResponse",
    "CommandDefinition",
]
