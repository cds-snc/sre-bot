"""Validation functions for group operations.

Provides validation for:
- Justification content (length, format, required/optional)
- Email validation
- Group ID format validation
- Other input validation as needed

All validation raises ValidationError with descriptive messages for API responses.
Returns boolean True on success or raises ValidationError on failure.
"""

import re
from typing import Optional

from core.config import settings
from core.logging import get_module_logger
from email_validator import (
    validate_email as email_validator_validate,
    EmailNotValidError,
)

logger = get_module_logger()

# Email validation regex (kept for group_id validation only)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# TODO: refactor to use the core.settings configuration for valid providers/actions
# Valid group actions
VALID_ACTIONS = {"add_member", "remove_member", "list_members", "get_details"}

# Valid providers
VALID_PROVIDERS = {"aws", "google", "azure"}  # Add more as needed


class ValidationError(Exception):
    """Raised when validation fails.

    Provides descriptive error messages suitable for returning to API clients.
    """

    pass


def validate_justification(
    justification: Optional[str],
    required: Optional[bool] = None,
    min_length: Optional[int] = None,
) -> bool:
    """Validate justification meets requirements.

    Validates that justification is provided if required, has minimum length,
    and contains meaningful content.

    Args:
        justification: Justification string to validate (can be None)
        required: Whether justification is required (overrides config if provided)
        min_length: Minimum length in characters (overrides config if provided)

    Returns:
        True if validation passes

    Raises:
        ValidationError: If validation fails with descriptive message

    Examples:
        >>> validate_justification("User joining team", required=True)
        True

        >>> validate_justification(None, required=True)
        Traceback (most recent call last):
            ...
        ValidationError: Justification is required...

        >>> validate_justification("short", required=True, min_length=10)
        Traceback (most recent call last):
            ...
        ValidationError: Justification must be at least 10 characters...
    """
    # Use config defaults if not overridden
    if required is None:
        required = settings.groups.require_justification
    if min_length is None:
        min_length = settings.groups.min_justification_length

    # Check if justification is required
    if required and not justification:
        logger.warning(
            "validation_failed_justification_required",
            min_length=min_length,
        )
        raise ValidationError(
            "Justification is required for this operation. "
            f"Please provide a justification of at least {min_length} characters."
        )

    # If justification is provided, validate content
    if justification:
        stripped = justification.strip()

        # Check length
        if len(stripped) < min_length:
            logger.warning(
                "validation_failed_justification_too_short",
                provided_length=len(stripped),
                required_length=min_length,
            )
            raise ValidationError(
                f"Justification must be at least {min_length} characters. "
                f"Provided: {len(stripped)} characters."
            )

        # Check for meaningless content (all same character)
        if len(set(stripped)) == 1:
            logger.warning(
                "validation_failed_justification_invalid",
                justification_length=len(stripped),
            )
            raise ValidationError("Justification must contain meaningful content.")

    return True


def validate_email(email: str) -> bool:
    """Validate email format using email-validator library.

    Uses the email-validator library (same as Pydantic) for comprehensive
    email validation including RFC 5321 compliance checks.

    Args:
        email: Email address to validate

    Returns:
        True if validation passes

    Raises:
        ValidationError: If email format is invalid

    Examples:
        >>> validate_email("user@example.com")
        True

        >>> validate_email("invalid-email")
        Traceback (most recent call last):
            ...
        ValidationError: Invalid email format: invalid-email
    """
    if not email or not isinstance(email, str):
        logger.warning("validation_failed_invalid_email", email=email)
        raise ValidationError(f"Invalid email format: {email}")

    try:
        # Strip whitespace and validate - email-validator is strict about whitespace
        email_validator_validate(email.strip(), check_deliverability=False)
        return True
    except EmailNotValidError as e:
        logger.warning("validation_failed_invalid_email", email=email, error=str(e))
        raise ValidationError(f"Invalid email format: {email}") from e


def validate_group_id(group_id: str, provider_type: Optional[str] = None) -> bool:
    """Validate group identifier format.

    Group IDs can be email addresses (Google Workspace), names, or ARNs (AWS).
    This function performs validation appropriate to the provider type.

    Args:
        group_id: Group identifier to validate
        provider_type: Provider type (aws, google, azure) for specific validation

    Returns:
        True if validation passes

    Raises:
        ValidationError: If group_id format is invalid

    Examples:
        >>> validate_group_id("engineering@company.com")
        True

        >>> validate_group_id("")
        Traceback (most recent call last):
            ...
        ValidationError: Group ID cannot be empty
    """
    if not group_id or not isinstance(group_id, str):
        logger.warning("validation_failed_empty_group_id", group_id=group_id)
        raise ValidationError("Group ID cannot be empty")

    group_id = group_id.strip()

    if not group_id:
        logger.warning(
            "validation_failed_empty_group_id",
            group_id="(whitespace-only)",
        )
        raise ValidationError("Group ID cannot be empty")

    if provider_type == "aws":
        # AWS group IDs are typically UUIDs or ARNs
        if not (
            len(group_id) > 10
            and (
                group_id.startswith("arn:aws:")
                or re.match(r"^[a-zA-Z0-9\-_]+$", group_id)
            )
        ):
            logger.warning("validation_failed_invalid_group_id", group_id=group_id)
            raise ValidationError(f"Invalid AWS group ID format: {group_id}")
    elif provider_type == "google":
        # Google group IDs are typically email addresses or IDs
        is_email = EMAIL_REGEX.match(group_id)
        is_valid_id = re.match(r"^[a-zA-Z0-9\-_]+$", group_id)
        if not (is_email or is_valid_id):
            logger.warning("validation_failed_invalid_group_id", group_id=group_id)
            raise ValidationError(f"Invalid Google group ID format: {group_id}")
    elif provider_type == "azure":
        # Azure group IDs are typically GUIDs
        if not re.match(r"^[a-fA-F0-9\-]{36}$", group_id):
            logger.warning("validation_failed_invalid_group_id", group_id=group_id)
            raise ValidationError(f"Invalid Azure group ID format: {group_id}")
    else:
        # Generic validation for unknown providers or when provider not specified
        if len(group_id) > 256:
            logger.warning(
                "validation_failed_group_id_too_long",
                length=len(group_id),
            )
            raise ValidationError("Group ID is too long (max 256 characters)")

    return True


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


# Legacy validation functions (used by api.py layer)
# These return dicts rather than raising ValidationError
def validate_group_membership_payload(payload: dict) -> dict:
    """Validate a complete group membership operation payload.

    Returns dict with 'valid' boolean and 'errors' list (legacy format).
    This is used by the api.py layer before delegating to service layer.
    """
    errors = []

    # Required fields
    required_fields = ["group_id", "member_email", "provider_type", "requestor_email"]
    for field in required_fields:
        if field not in payload:
            errors.append(f"Missing required field: {field}")

    if errors:
        return {"valid": False, "errors": errors}

    # Validate individual fields using try/catch for ValidationError
    try:
        validate_email(payload.get("member_email", ""))
    except ValidationError as e:
        errors.append(f"Invalid member email: {str(e)}")

    try:
        validate_email(payload.get("requestor_email", ""))
    except ValidationError as e:
        errors.append(f"Invalid requestor email: {str(e)}")

    if not validate_provider_type(payload.get("provider_type", "")):
        errors.append(
            f"Invalid provider type. Must be one of: {', '.join(VALID_PROVIDERS)}"
        )

    try:
        validate_group_id(payload.get("group_id", ""), payload.get("provider_type", ""))
    except ValidationError as e:
        errors.append(f"Invalid group ID: {str(e)}")

    # Validate justification if provided
    justification = payload.get("justification")
    if justification:
        try:
            validate_justification(justification, required=False)
        except ValidationError as e:
            errors.append(f"Invalid justification: {str(e)}")

    # Validate action if provided
    action = payload.get("action")
    if action and not validate_action(action):
        errors.append(f"Invalid action. Must be one of: {', '.join(VALID_ACTIONS)}")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": []}


def validate_bulk_operation(payloads: list) -> dict:
    """Validate multiple group membership operations (legacy format)."""
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
