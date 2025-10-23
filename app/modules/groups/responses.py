# modules/groups/responses.py
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.logging import get_module_logger

logger = get_module_logger()


def format_success_response(
    action: str,
    group_id: str,
    member_email: str,
    provider: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Format a successful operation response."""
    response = {
        "success": True,
        "action": action,
        "group_id": group_id,
        "member_email": member_email,
        "provider": provider,
        "timestamp": datetime.utcnow().isoformat(),
        "message": _get_success_message(action, member_email, group_id, provider),
    }

    if details:
        response["details"] = details

    return response


def format_error_response(
    action: str,
    error_message: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Format an error response."""
    response = {
        "success": False,
        "action": action,
        "error": error_message,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if error_code:
        response["error_code"] = error_code

    if details:
        response["details"] = details

    return response


def format_validation_error_response(
    validation_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Format a validation error response."""
    return {
        "success": False,
        "error": "Validation failed",
        "error_code": "VALIDATION_ERROR",
        "validation_errors": validation_result.get("errors", []),
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_permission_error_response(
    user_email: str, group_id: str, action: str
) -> Dict[str, Any]:
    """Format a permission denied response."""
    return {
        "success": False,
        "error": f"Permission denied: {user_email} cannot {action} on group {group_id}",
        "error_code": "PERMISSION_DENIED",
        "user_email": user_email,
        "group_id": group_id,
        "action": action,
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_group_list_response(
    groups: Dict[str, List[Dict]], user_email: str
) -> Dict[str, Any]:
    """Format response for listing user's manageable groups."""
    total_groups = sum(len(provider_groups) for provider_groups in groups.values())

    return {
        "success": True,
        "user_email": user_email,
        "total_groups": total_groups,
        "providers": groups,
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_group_members_response(
    group_id: str, provider: str, members: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Format response for listing group members."""
    return {
        "success": True,
        "group_id": group_id,
        "provider": provider,
        "member_count": len(members),
        "members": members,
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_bulk_operation_response(
    results: List[Dict[str, Any]], operation_type: str
) -> Dict[str, Any]:
    """Format response for bulk operations."""
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    return {
        "success": len(failed) == 0,
        "operation_type": operation_type,
        "total_operations": len(results),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "results": results,
        "summary": {"successful": successful, "failed": failed},
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_slack_response(
    response_data: Dict[str, Any], user_friendly: bool = True
) -> str:
    """Format response for Slack interface."""
    if not response_data.get("success"):
        error_msg = response_data.get("error", "Operation failed")
        return f"❌ {error_msg}"

    action = response_data.get("action", "operation")
    member_email = response_data.get("member_email", "user")
    group_id = response_data.get("group_id", "group")
    provider = response_data.get("provider", "provider")

    if user_friendly:
        return _get_slack_success_message(action, member_email, group_id, provider)
    else:
        return f"✅ {response_data.get('message', 'Operation completed successfully')}"


def format_webhook_response(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format response for webhook payloads."""
    # Add webhook-specific formatting
    webhook_response = response_data.copy()
    webhook_response["webhook_version"] = "1.0"
    webhook_response["source"] = "groups-membership-service"

    return webhook_response


def _get_success_message(
    action: str, member_email: str, group_id: str, provider: str
) -> str:
    """Get human-readable success message."""
    action_map = {
        "add_member": f"Successfully added {member_email} to {provider} group {group_id}",
        "remove_member": f"Successfully removed {member_email} from {provider} group {group_id}",
        "list_members": f"Successfully retrieved members for {provider} group {group_id}",
        "get_groups": f"Successfully retrieved manageable groups for {member_email}",
    }

    return action_map.get(action, f"Successfully completed {action}")


def _get_slack_success_message(
    action: str, member_email: str, group_id: str, provider: str
) -> str:
    """Get Slack-formatted success message with emojis."""
    action_map = {
        "add_member": f"✅ Added {member_email} to {provider.upper()} group `{group_id}`",
        "remove_member": f"✅ Removed {member_email} from {provider.upper()} group `{group_id}`",
        "list_members": f"📋 Retrieved members for {provider.upper()} group `{group_id}`",
        "get_groups": f"📂 Retrieved manageable groups for {member_email}",
    }

    return action_map.get(action, f"✅ Completed {action}")


def format_api_response(
    data: Any, status_code: int = 200, message: Optional[str] = None
) -> Dict[str, Any]:
    """Format response for API endpoints."""
    response = {
        "status_code": status_code,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    }

    if message:
        response["message"] = message

    return response
