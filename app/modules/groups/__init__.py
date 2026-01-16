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

from infrastructure.events import register_event_handler, dispatch_event
from infrastructure.services import hookimpl
from modules.groups.core.orchestration import (
    add_member_to_group,
    remove_member_from_group,
    list_groups_simple,
    list_groups_with_members_and_filters,
)
from modules.groups.providers import get_provider, get_active_providers
from modules.groups.platforms import slack

# Import event handlers to register them
from modules.groups import events  # noqa: F401


@hookimpl
def register_slack_commands(provider):
    """Register groups module Slack commands."""
    slack.commands.register_commands(provider)


__all__ = [
    # Orchestration
    "add_member_to_group",
    "remove_member_from_group",
    "list_groups_simple",
    "list_groups_with_members_and_filters",
    # Command framework
    "command_registry",
    # Provider management
    "get_provider",
    "get_active_providers",
    # Event system
    "register_event_handler",
    "dispatch_event",
    "events",
]
