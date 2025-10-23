"""Groups Membership Events"""

from modules.groups.event_system import register_event_handler
from modules.groups.audit import log_group_action
from modules.groups.notifications import send_group_notifications
from modules.groups.base import add_member_to_group, remove_member_from_group


@register_event_handler("group.member.add_requested")
def handle_member_add_request(payload):
    """Handle member addition from any interface."""

    result = add_member_to_group(
        group_id=payload["group_id"],
        member_email=payload["member_email"],
        justification=payload["justification"],
        provider_type=payload["provider_type"],
        requestor_email=payload["requestor_email"],
    )
    return result


@register_event_handler("group.member.remove_requested")
def handle_member_remove_request(payload):
    """Handle member removal from any interface."""

    result = remove_member_from_group(
        group_id=payload["group_id"],
        member_email=payload["member_email"],
        justification=payload["justification"],
        provider_type=payload["provider_type"],
        requestor_email=payload["requestor_email"],
    )
    return result


@register_event_handler("group.member.added")
def handle_member_added(payload):
    """Handle post-addition tasks."""

    # Log to Sentinel for audit
    log_group_action(payload)

    # Send notifications
    send_group_notifications(payload)


@register_event_handler("group.member.removed")
def handle_member_removed(payload):
    """Handle post-removal tasks."""

    # Log to Sentinel for audit
    log_group_action(payload)

    # Send notifications
    send_group_notifications(payload)
