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

from modules.groups.events.event_system import register_event_handler, dispatch_event
from modules.groups.core.orchestration import (
    add_member_to_group,
    remove_member_from_group,
    list_groups_for_user,
)
from modules.groups.api.commands import handle_groups_command, register_groups_commands
from modules.groups.domain.validation import (
    validate_email,
    validate_group_id,
    validate_provider_type,
    validate_group_membership_payload,
)
from modules.groups.api.responses import (
    format_success_response,
    format_error_response,
    format_slack_response,
)
from modules.groups.providers import get_provider, get_active_providers

# Import event handlers to register them
from modules.groups import events  # noqa: F401


__all__ = [
    # Orchestration
    "add_member_to_group",
    "remove_member_from_group",
    "list_groups_for_user",
    # Slack interfaces
    "handle_groups_command",
    "register_groups_commands",
    # Validation
    "validate_email",
    "validate_group_id",
    "validate_provider_type",
    "validate_group_membership_payload",
    # Response formatting
    "format_success_response",
    "format_error_response",
    "format_slack_response",
    # Provider management
    "get_provider",
    "get_active_providers",
    # Event system
    "register_event_handler",
    "dispatch_event",
    "events",
]
