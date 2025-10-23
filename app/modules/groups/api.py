# modules/groups/api.py
"""API interface for groups membership management."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logging import get_module_logger
from modules.groups.base import (
    add_member_to_group,
    get_user_managed_groups,
    remove_member_from_group,
    validate_group_permissions,
)
from modules.groups.event_system import dispatch_event
from modules.groups.responses import (
    format_bulk_operation_response,
    format_error_response,
    format_group_list_response,
    format_permission_error_response,
    format_success_response,
    format_validation_error_response,
)
from modules.groups.validation import (
    sanitize_input,
    validate_bulk_operation,
    validate_group_membership_payload,
)
from modules.groups.responses import format_slack_response
from modules.groups.responses import format_webhook_response

logger = get_module_logger()


def handle_add_member_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle request to add member to group."""
    try:
        # Validate payload
        validation_result = validate_group_membership_payload(payload)
        if not validation_result["valid"]:
            return format_validation_error_response(validation_result)

        # Sanitize inputs
        group_id = sanitize_input(payload["group_id"])
        member_email = sanitize_input(payload["member_email"])
        requestor_email = sanitize_input(payload["requestor_email"])
        provider_type = sanitize_input(payload["provider_type"])
        justification = sanitize_input(payload.get("justification", ""), max_length=500)

        # Dispatch event to handle the request
        dispatch_event(
            "group.member.add_requested",
            {
                "group_id": group_id,
                "member_email": member_email,
                "requestor_email": requestor_email,
                "provider_type": provider_type,
                "justification": justification,
            },
        )

        # Perform the operation
        result = add_member_to_group(
            group_id=group_id,
            member_email=member_email,
            justification=justification,
            provider_type=provider_type,
            requestor_email=requestor_email,
        )

        # If the core flow returned an error dict (for example, mapped IntegrationError),
        # pass it through unchanged so the API surface returns a proper error.
        if isinstance(result, dict) and result.get("success") is False:
            return result

        return format_success_response(
            action="add_member",
            group_id=group_id,
            member_email=member_email,
            provider=provider_type,
            details=result,
        )

    except PermissionError:
        return format_permission_error_response(
            payload.get("requestor_email", "unknown"),
            payload.get("group_id", "unknown"),
            "add_member",
        )
    except Exception as e:
        logger.error(f"Error adding member to group: {e}")
        return format_error_response(
            action="add_member", error_message=str(e), error_code="OPERATION_FAILED"
        )


def handle_remove_member_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle request to remove member from group."""
    try:
        # Validate payload
        validation_result = validate_group_membership_payload(payload)
        if not validation_result["valid"]:
            return format_validation_error_response(validation_result)

        # Sanitize inputs
        group_id = sanitize_input(payload["group_id"])
        member_email = sanitize_input(payload["member_email"])
        requestor_email = sanitize_input(payload["requestor_email"])
        provider_type = sanitize_input(payload["provider_type"])
        justification = sanitize_input(payload.get("justification", ""), max_length=500)

        # Perform the operation
        result = remove_member_from_group(
            group_id=group_id,
            member_email=member_email,
            justification=justification,
            provider_type=provider_type,
            requestor_email=requestor_email,
        )

        if isinstance(result, dict) and result.get("success") is False:
            return result

        return format_success_response(
            action="remove_member",
            group_id=group_id,
            member_email=member_email,
            provider=provider_type,
            details=result,
        )

    except PermissionError:
        return format_permission_error_response(
            payload.get("requestor_email", "unknown"),
            payload.get("group_id", "unknown"),
            "remove_member",
        )
    except Exception as e:
        logger.error(f"Error removing member from group: {e}")
        return format_error_response(
            action="remove_member", error_message=str(e), error_code="OPERATION_FAILED"
        )


def handle_list_user_groups_request(
    user_email: str, provider_type: Optional[str] = None
) -> Dict[str, Any]:
    """Handle request to list groups user can manage."""
    try:
        # Sanitize input
        user_email = sanitize_input(user_email)
        if provider_type:
            provider_type = sanitize_input(provider_type)

        # Get user's manageable groups
        groups = get_user_managed_groups(user_email, provider_type)

        return format_group_list_response(groups, user_email)

    except Exception as e:
        logger.error(f"Error listing user groups: {e}")
        return format_error_response(
            action="list_user_groups",
            error_message=str(e),
            error_code="OPERATION_FAILED",
        )


def handle_bulk_operations_request(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Handle bulk group membership operations."""
    try:
        # Validate bulk operations
        validation_result = validate_bulk_operation(operations)
        if not validation_result["valid"]:
            return format_validation_error_response(validation_result)

        results = []

        for operation in operations:
            operation_type = operation.get("operation", "unknown")

            if operation_type == "add_member":
                result = handle_add_member_request(operation)
            elif operation_type == "remove_member":
                result = handle_remove_member_request(operation)
            else:
                result = format_error_response(
                    action=operation_type,
                    error_message=f"Unknown operation type: {operation_type}",
                    error_code="INVALID_OPERATION",
                )

            results.append(result)

        return format_bulk_operation_response(results, "bulk_operations")

    except Exception as e:
        logger.error(f"Error processing bulk operations: {e}")
        return format_error_response(
            action="bulk_operations",
            error_message=str(e),
            error_code="BULK_OPERATION_FAILED",
        )


def handle_check_permissions_request(
    user_email: str, group_id: str, action: str, provider_type: str
) -> Dict[str, Any]:
    """Handle request to check user permissions for group action."""
    try:
        # Sanitize inputs
        user_email = sanitize_input(user_email)
        group_id = sanitize_input(group_id)
        action = sanitize_input(action)
        provider_type = sanitize_input(provider_type)

        # Check permissions
        has_permission = validate_group_permissions(
            user_email, group_id, action, provider_type
        )

        return {
            "success": True,
            "user_email": user_email,
            "group_id": group_id,
            "action": action,
            "provider": provider_type,
            "has_permission": has_permission,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error checking permissions: {e}")
        return format_error_response(
            action="check_permissions",
            error_message=str(e),
            error_code="PERMISSION_CHECK_FAILED",
        )


# Convenience functions for different interfaces


def slack_add_member(payload: Dict[str, Any]) -> str:
    """Slack interface for adding member to group."""

    result = handle_add_member_request(payload)
    return format_slack_response(result)


def slack_remove_member(payload: Dict[str, Any]) -> str:
    """Slack interface for removing member from group."""

    result = handle_remove_member_request(payload)
    return format_slack_response(result)


def slack_list_groups(user_email: str, provider_type: Optional[str] = None) -> str:
    """Slack interface for listing user's groups."""

    result = handle_list_user_groups_request(user_email, provider_type)
    if result["success"]:
        groups_summary = []
        for provider, groups in result["providers"].items():
            groups_summary.append(f"• {provider.upper()}: {len(groups)} groups")

        return "📂 Your manageable groups:\n" + "\n".join(groups_summary)
    else:
        return format_slack_response(result)


def webhook_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Webhook interface for group operations."""

    operation = payload.get("operation", "unknown")

    if operation == "add_member":
        result = handle_add_member_request(payload)
    elif operation == "remove_member":
        result = handle_remove_member_request(payload)
    elif operation == "list_groups":
        result = handle_list_user_groups_request(payload.get("user_email", ""))
    else:
        result = format_error_response(
            action=operation,
            error_message=f"Unknown webhook operation: {operation}",
            error_code="INVALID_WEBHOOK_OPERATION",
        )

    return format_webhook_response(result)
