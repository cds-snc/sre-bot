"""Platform capability models and declarations.

Defines the capabilities that collaboration platforms can support, and provides
dataclasses for declaring which capabilities a specific provider implements.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Optional


class PlatformCapability(str, Enum):
    """Capabilities that a collaboration platform can support.

    Platforms declare which capabilities they implement via CapabilityDeclaration.
    Feature modules can query providers by capability to determine available features.
    """

    COMMANDS = "commands"  # Text-based command execution (/slash, @mention)
    HIERARCHICAL_TEXT_COMMANDS = "hierarchical_text_commands"  # Slack-style text
    STRUCTURED_COMMANDS = "structured_commands"  # Structured options (Teams, Discord)
    VIEWS_MODALS = "views_modals"  # Rich form-based interactions
    INTERACTIVE_CARDS = "interactive_cards"  # Rich messages with buttons/actions
    MESSAGING = "messaging"  # Send messages to channels/users
    MESSAGE_ACTIONS = "message_actions"  # Context menu actions on messages
    FILE_SHARING = "file_sharing"  # Upload/download files
    WORKFLOWS = "workflows"  # Platform-native automation (Workflow Builder, etc.)
    PRESENCE = "presence"  # User online/away status
    REACTIONS = "reactions"  # Emoji reactions on messages
    THREADS = "threads"  # Threaded conversations


class PlatformFeatureType(str, Enum):
    """Types of platform features that can be registered.

    Used internally for tracking what platform-specific handlers are registered.
    """

    COMMAND_HANDLER = "command_handler"  # Slash command handler
    VIEW_HANDLER = "view_handler"  # Modal/form submission handler
    BUTTON_HANDLER = "button_handler"  # Interactive button handler
    MESSAGE_ACTION_HANDLER = "message_action_handler"  # Message action handler
    EVENT_LISTENER = "event_listener"  # Platform event listener


# Platform identifier constants
PLATFORM_SLACK = "slack"
PLATFORM_TEAMS = "teams"
PLATFORM_DISCORD = "discord"
PLATFORM_API = "api"  # HTTP API (platform-agnostic)


@dataclass(frozen=True)
class CapabilityDeclaration:
    """Declares the capabilities supported by a platform provider.

    Attributes:
        platform_id: Unique identifier for the platform (slack, teams, discord).
        capabilities: Set of PlatformCapability values this provider supports.
        metadata: Optional additional metadata about the provider.
    """

    platform_id: str
    capabilities: FrozenSet[PlatformCapability]
    metadata: Dict[str, str] = field(default_factory=dict)

    def supports(self, capability: PlatformCapability) -> bool:
        """Check if this provider supports the given capability.

        Args:
            capability: The capability to check.

        Returns:
            True if capability is supported, False otherwise.
        """
        return capability in self.capabilities

    def supports_all(self, *capabilities: PlatformCapability) -> bool:
        """Check if this provider supports all given capabilities.

        Args:
            *capabilities: Variable number of capabilities to check.

        Returns:
            True if all capabilities are supported, False otherwise.
        """
        return all(cap in self.capabilities for cap in capabilities)

    def supports_any(self, *capabilities: PlatformCapability) -> bool:
        """Check if this provider supports any of the given capabilities.

        Args:
            *capabilities: Variable number of capabilities to check.

        Returns:
            True if any capability is supported, False otherwise.
        """
        return any(cap in self.capabilities for cap in capabilities)


def create_capability_declaration(
    platform_id: str,
    *capabilities: PlatformCapability,
    metadata: Optional[Dict[str, str]] = None,
) -> CapabilityDeclaration:
    """Factory function for creating CapabilityDeclaration instances.

    Args:
        platform_id: Unique identifier for the platform.
        *capabilities: Variable number of PlatformCapability values.
        metadata: Optional metadata dict.

    Returns:
        CapabilityDeclaration instance.

    Example:
        >>> decl = create_capability_declaration(
        ...     PLATFORM_SLACK,
        ...     PlatformCapability.COMMANDS,
        ...     PlatformCapability.VIEWS_MODALS,
        ...     PlatformCapability.INTERACTIVE_CARDS,
        ...     metadata={"version": "1.0.0"}
        ... )
    """
    return CapabilityDeclaration(
        platform_id=platform_id,
        capabilities=frozenset(capabilities),
        metadata=metadata or {},
    )
