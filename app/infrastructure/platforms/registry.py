"""Platform command registry for auto-discovery pattern.

This module provides a global registry for platform commands that allows
features to self-register without requiring manual coordination.

Features declare their commands at module level, and the platform service
auto-discovers and registers them at startup.
"""

import structlog
from typing import Callable, Optional, List, Dict
from dataclasses import dataclass, field

from infrastructure.platforms.models import CommandPayload, CommandResponse

logger = structlog.get_logger()


@dataclass
class PlatformCommandMetadata:
    """Metadata for platform command registration.

    This metadata is declared by feature packages at module level and
    discovered by the platform service at startup.
    """

    command: str
    """Subcommand name (e.g., 'geolocate', 'incident', 'webhooks')"""

    handler: Callable[[CommandPayload], CommandResponse]
    """Command handler function"""

    parent_command: Optional[str] = None
    """Parent command for hierarchical structure (e.g., 'sre' creates /sre geolocate)"""

    description: str = ""
    """Human-readable command description"""

    description_key: Optional[str] = None
    """I18n translation key for description"""

    usage_hint: Optional[str] = None
    """Usage hint displayed in help (e.g., '<ip_address>', '[--force]')"""

    examples: List[str] = field(default_factory=list)
    """Example command invocations"""

    example_keys: List[str] = field(default_factory=list)
    """I18n translation keys for examples"""

    platform: str = "slack"
    """Target platform (default: slack)"""

    registration_order: int = 100
    """Registration order - lower values registered first (for dependencies)"""


# Global registry for auto-discovery
_PLATFORM_COMMANDS: List[PlatformCommandMetadata] = []


def register_platform_command(
    command: str,
    handler: Callable[[CommandPayload], CommandResponse],
    parent_command: Optional[str] = None,
    description: str = "",
    description_key: Optional[str] = None,
    usage_hint: Optional[str] = None,
    examples: Optional[List[str]] = None,
    example_keys: Optional[List[str]] = None,
    platform: str = "slack",
    registration_order: int = 100,
) -> None:
    """Register a platform command for auto-discovery.

    This function should be called at module level in feature packages.
    The platform service will discover and register all commands at startup.

    Example:
        # packages/geolocate/slack.py

        def handle_geolocate_command(payload: CommandPayload) -> CommandResponse:
            # Handler implementation...
            pass

        # Register at module level (executed on import)
        register_platform_command(
            command="geolocate",
            handler=handle_geolocate_command,
            parent_command="sre",  # Creates /sre geolocate
            description="Lookup geographic location of IP address",
            usage_hint="<ip_address>",
            examples=["8.8.8.8", "1.1.1.1"],
        )

    Args:
        command: Subcommand name
        handler: Command handler function
        parent_command: Optional parent command for hierarchical structure
        description: Human-readable description
        description_key: I18n key for description
        usage_hint: Usage hint (e.g., "<ip_address>")
        examples: Example command invocations
        example_keys: I18n keys for examples
        platform: Target platform (default: "slack")
        registration_order: Registration order (lower = first)
    """
    metadata = PlatformCommandMetadata(
        command=command,
        handler=handler,
        parent_command=parent_command,
        description=description,
        description_key=description_key,
        usage_hint=usage_hint,
        examples=examples or [],
        example_keys=example_keys or [],
        platform=platform,
        registration_order=registration_order,
    )
    _PLATFORM_COMMANDS.append(metadata)

    # Log registration for debugging
    full_command = f"/{parent_command} {command}" if parent_command else f"/{command}"
    logger.debug(
        "command_registered_for_discovery",
        command=full_command,
        platform=platform,
        order=registration_order,
    )


def get_registered_commands(platform: str = "slack") -> List[PlatformCommandMetadata]:
    """Get all registered commands for a platform, sorted by registration order.

    Args:
        platform: Platform name to filter by

    Returns:
        List of command metadata sorted by registration_order
    """
    commands = [cmd for cmd in _PLATFORM_COMMANDS if cmd.platform == platform]
    return sorted(commands, key=lambda x: x.registration_order)


def clear_registry() -> None:
    """Clear the command registry.

    This is primarily useful for testing to reset state between test runs.
    """
    global _PLATFORM_COMMANDS
    _PLATFORM_COMMANDS = []
    logger.debug("command_registry_cleared")


def get_registration_stats() -> Dict[str, int]:
    """Get registration statistics by platform.

    Returns:
        Dict mapping platform name to number of registered commands
    """
    stats = {}
    for cmd in _PLATFORM_COMMANDS:
        stats[cmd.platform] = stats.get(cmd.platform, 0) + 1
    return stats
