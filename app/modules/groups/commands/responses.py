"""Response formatting utilities for groups commands.

Standardizes response formatting across all command handlers to reduce
duplication and ensure consistent presentation to users.
"""

from typing import Any, Dict, Optional, List
from core.logging import get_module_logger
from infrastructure.commands import CommandContext

logger = get_module_logger()


def format_action_response(
    ctx: CommandContext, result: Any, operation: Optional[str] = None
) -> str:
    """Format action response (add/remove/etc.) for display.

    Args:
        ctx: Command context with translator
        result: Response from service layer (dict or model)
        operation: Operation name for translation key (default: infer from type)

    Returns:
        Formatted response string for user
    """
    # Convert model to dict if needed
    if hasattr(result, "model_dump"):
        result_dict = result.model_dump()
    elif hasattr(result, "dict"):
        result_dict = result.dict()
    else:
        result_dict = result if isinstance(result, dict) else {}

    # Check if operation was successful
    success = result_dict.get("success", True)
    if not success:
        error_msg = result_dict.get("error_message", "Operation failed")
        return f"❌ {error_msg}"

    # Get operation type from result or parameter
    op_type = operation or result_dict.get("operation", "unknown")

    # Build translation key
    translation_key = f"groups.success.{op_type}"

    # Extract relevant metadata for translation
    metadata = result_dict.get("metadata", {})

    try:
        return ctx.translate(translation_key, **metadata)
    except Exception as e:
        logger.warning("translation_failed", key=translation_key, error=str(e))
        return "✅ Operation completed successfully"


def format_groups_list(
    groups: List[Dict[str, Any]], ctx: CommandContext, show_details: bool = False
) -> str:
    """Format a list of groups for display.

    Args:
        groups: List of group dicts from service
        ctx: Command context with translator
        show_details: Include detailed member information

    Returns:
        Formatted list string for user
    """
    if not groups:
        return ctx.translate("groups.success.no_groups")

    group_lines = []
    for group in groups:
        group_name = group.get("name", "Unnamed Group")
        group_id = group.get("id", "N/A")
        member_count = len(group.get("members", []))

        if show_details:
            members = group.get("members", [])
            roles = {}
            for member in members:
                role = member.get("role", "MEMBER")
                roles[role] = roles.get(role, 0) + 1

            role_summary = ", ".join(
                f"{count} {role.lower()}" for role, count in sorted(roles.items())
            )
            group_lines.append(f"• {group_name} (ID: {group_id}) - {role_summary}")
        else:
            group_lines.append(
                f"• {group_name} (ID: {group_id}) - {member_count} members"
            )

    count = len(groups)
    plural = "s" if count != 1 else ""

    summary = ctx.translate(
        "groups.success.list_summary",
        count=count,
        plural=plural,
    )

    return f"{summary}:\n" + "\n".join(group_lines)


def format_group_details(group: Dict[str, Any], ctx: CommandContext) -> str:
    """Format detailed group information.

    Args:
        group: Group dict from service
        ctx: Command context with translator

    Returns:
        Formatted group details string
    """
    lines = []

    name = group.get("name", "Unnamed")
    group_id = group.get("id", "N/A")
    lines.append(f"📋 {name}")
    lines.append(f"   ID: {group_id}")

    members = group.get("members", [])
    if members:
        lines.append(f"   Members: {len(members)}")
        for member in members[:5]:  # Show first 5
            email = member.get("email", "unknown")
            role = member.get("role", "MEMBER").upper()
            lines.append(f"     • {email} ({role})")
        if len(members) > 5:
            lines.append(f"     ... and {len(members) - 5} more")

    description = group.get("description")
    if description:
        lines.append(f"   Description: {description}")

    return "\n".join(lines)


def format_error_response(ctx: CommandContext, error: str) -> str:
    """Format an error response for display.

    Args:
        ctx: Command context with translator
        error: Error message or translation key

    Returns:
        Formatted error string
    """
    if error.startswith("groups.errors."):
        try:
            return f"❌ {ctx.translate(error)}"
        except Exception:
            pass
    return f"❌ {error}"


def format_validation_error(ctx: CommandContext, field: str, message: str) -> str:
    """Format a field validation error.

    Args:
        ctx: Command context with translator
        field: Field name
        message: Validation error message

    Returns:
        Formatted validation error string
    """
    return f"❌ {field}: {message}"
