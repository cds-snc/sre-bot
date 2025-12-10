# modules/groups/__init__.py
"""Groups membership management module.

This module provides a flexible, event-driven system for managing group memberships
across multiple providers (AWS, Google Workspace, Azure, etc.).

Features:
- Multi-provider support through a plugin architecture
- Event-driven operations for audit trails and notifications
- Validation and sanitization of inputs
- Multiple interfaces (API, Slack commands, webhooks)
- Comprehensive audit logging
"""

from pathlib import Path
from typing import Optional

from infrastructure.commands.providers.slack import SlackCommandProvider
from infrastructure.events import register_event_handler, dispatch_event
from infrastructure.i18n import Translator, LocaleResolver, YAMLTranslationLoader
from modules.groups.core.orchestration import (
    add_member_to_group,
    remove_member_from_group,
    list_groups_simple,
    list_groups_with_members_and_filters,
)
from modules.groups.commands.registry import registry as command_registry
from modules.groups.providers import get_provider, get_active_providers

# Import event handlers to register them
from modules.groups import events  # noqa: F401


def create_slack_provider(
    parent_command: Optional[str] = None,
):
    """Create Slack provider configured for groups commands.

    Factory function that wires infrastructure components with groups-specific config:
    - Infrastructure: SlackCommandProvider (generic, reusable)
    - Feature: groups registry (groups-specific commands)
    - Config: i18n with groups translations

    This pattern allows:
    - CommandRouter (infrastructure) remains feature-agnostic
    - SlackCommandProvider (infrastructure) remains feature-agnostic
    - groups module (feature) configures everything for its needs

    Args:
        parent_command: Parent command namespace (e.g., "sre")

    Returns:
        Configured SlackCommandProvider instance ready for router registration

    Example:
        # In sre.py
        from modules.groups import create_slack_provider

        groups_provider = create_slack_provider(parent_command="sre")
        router.register_subcommand("groups", groups_provider, platform="slack")
    """
    # Load i18n (groups-specific translation files)
    loader = YAMLTranslationLoader(translations_dir=Path("locales"))
    translator = Translator(loader=loader)
    translator.load_all()
    locale_resolver = LocaleResolver()

    # Create provider (generic infrastructure component)
    provider = SlackCommandProvider(config={"enabled": True})

    # Wire with groups-specific config
    provider.registry = command_registry  # groups command definitions
    provider.translator = translator  # i18n with groups translations
    provider.locale_resolver = locale_resolver  # locale resolution
    provider.parent_command = parent_command  # set by caller (e.g., "sre")

    return provider


__all__ = [
    # Orchestration
    "add_member_to_group",
    "remove_member_from_group",
    "list_groups_simple",
    "list_groups_with_members_and_filters",
    # Command framework
    "command_registry",
    # Factory for router registration
    "create_slack_provider",
    # Provider management
    "get_provider",
    "get_active_providers",
    # Event system
    "register_event_handler",
    "dispatch_event",
    "events",
]
