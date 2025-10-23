# modules/groups/validation.py
import re
from typing import Dict, Any, Optional

from core.logging import get_module_logger

logger = get_module_logger()

# Email validation regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Valid group actions
VALID_ACTIONS = {"add_member", "remove_member", "list_members", "get_details"}

# Valid providers
VALID_PROVIDERS = {"aws", "google", "azure"}  # Add more as needed


def validate_email(email: str) -> bool:
    """Validate email format."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_group_id(group_id: str, provider_type: str) -> bool:
    """Validate group ID format based on provider."""
    if not group_id or not isinstance(group_id, str):
        return False

    group_id = group_id.strip()

    if provider_type == "aws":
        # AWS group IDs are typically UUIDs or ARNs
        return len(group_id) > 10 and (
            group_id.startswith("arn:aws:") or re.match(r"^[a-zA-Z0-9\-_]+$", group_id)
        )
    elif provider_type == "google":
        # Google group IDs are typically email addresses or IDs
        return validate_email(group_id) or re.match(r"^[a-zA-Z0-9\-_]+$", group_id)
    elif provider_type == "azure":
        # Azure group IDs are typically GUIDs
        return re.match(r"^[a-fA-F0-9\-]{36}$", group_id) is not None

    # Generic validation for unknown providers
    return len(group_id.strip()) > 3


def validate_provider_type(provider_type: str) -> bool:
    """Validate provider type."""
    if not provider_type or not isinstance(provider_type, str):
        return False
    return provider_type.lower() in VALID_PROVIDERS


def validate_action(action: str) -> bool:
    """Validate action type."""
    if not action or not isinstance(action, str):
        return False
    return action.lower() in VALID_ACTIONS


def validate_justification(justification: str, min_length: int = 10) -> bool:
    """Validate justification text."""
    if not justification or not isinstance(justification, str):
        return False
    return len(justification.strip()) >= min_length


def validate_group_membership_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a complete group membership operation payload."""
    errors = []

    # Required fields
    required_fields = ["group_id", "member_email", "provider_type", "requestor_email"]
    for field in required_fields:
        if field not in payload:
            errors.append(f"Missing required field: {field}")

    if errors:
        return {"valid": False, "errors": errors}

    # Validate individual fields
    if not validate_email(payload.get("member_email", "")):
        errors.append("Invalid member email format")

    if not validate_email(payload.get("requestor_email", "")):
        errors.append("Invalid requestor email format")

    if not validate_provider_type(payload.get("provider_type", "")):
        errors.append(
            f"Invalid provider type. Must be one of: {', '.join(VALID_PROVIDERS)}"
        )

    if not validate_group_id(
        payload.get("group_id", ""), payload.get("provider_type", "")
    ):
        errors.append("Invalid group ID format")

    # Validate justification if provided
    justification = payload.get("justification")
    if justification and not validate_justification(justification):
        errors.append("Justification must be at least 10 characters long")

    # Validate action if provided
    action = payload.get("action")
    if action and not validate_action(action):
        errors.append(f"Invalid action. Must be one of: {', '.join(VALID_ACTIONS)}")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": []}


def sanitize_input(input_string: str, max_length: Optional[int] = None) -> str:
    """Sanitize user input by removing potentially harmful characters."""
    if not input_string or not isinstance(input_string, str):
        return ""

    # Remove control characters and normalize whitespace
    sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", input_string)
    sanitized = re.sub(r"\s+", " ", sanitized.strip())

    # Truncate if max_length specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized


def validate_bulk_operation(payloads: list) -> Dict[str, Any]:
    """Validate multiple group membership operations."""
    if not isinstance(payloads, list):
        return {"valid": False, "errors": ["Payloads must be a list"]}

    if len(payloads) == 0:
        return {"valid": False, "errors": ["No payloads provided"]}

    if len(payloads) > 100:  # Reasonable limit for bulk operations
        return {
            "valid": False,
            "errors": ["Too many operations in bulk request (max 100)"],
        }

    all_errors = []
    valid_count = 0

    for i, payload in enumerate(payloads):
        validation_result = validate_group_membership_payload(payload)
        if validation_result["valid"]:
            valid_count += 1
        else:
            for error in validation_result["errors"]:
                all_errors.append(f"Item {i + 1}: {error}")

    return {
        "valid": len(all_errors) == 0,
        "errors": all_errors,
        "valid_count": valid_count,
        "total_count": len(payloads),
    }
