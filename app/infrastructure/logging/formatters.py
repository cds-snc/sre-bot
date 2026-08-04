"""Custom log formatters for structured logging.

This module provides formatters that can be used as structlog processors
to customize log output format.

Usage:
    from infrastructure.logging.formatters import add_app_info, mask_sensitive_data

Dependencies:
    - structlog processors
"""

from typing import Any


def add_app_info(app_name: str, app_version: str = "unknown"):
    """Create a processor that adds application info to log entries.

    Args:
        app_name: Name of the application.
        app_version: Version string for the application.

    Returns:
        A structlog processor function.

    Example:
        configure_logging(
            extra_processors=[add_app_info("sre-bot", "1.2.3")]
        )
    """

    def processor(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        event_dict["app_name"] = app_name
        event_dict["app_version"] = app_version
        return event_dict

    return processor


# Sensitive field patterns that should be masked in logs
SENSITIVE_PATTERNS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "passphrase",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "credential",
        "signature",
        "session",
        "private_key",
        "access_token",
        "refresh_token",
        "session_id",
        "cookie",
        "jwt",
        "bearer",
    }
)


def _is_sensitive_key(key: str, patterns: frozenset[str]) -> bool:
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in patterns)


def _redact_recursive(value: Any, patterns: frozenset[str], mask_value: str) -> Any:
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, nested_value in value.items():
            if isinstance(key, str) and _is_sensitive_key(key, patterns) and nested_value is not None:
                redacted[key] = mask_value
            else:
                redacted[key] = _redact_recursive(nested_value, patterns, mask_value)
        return redacted

    if isinstance(value, list):
        return [_redact_recursive(item, patterns, mask_value) for item in value]

    return value


def mask_sensitive_data(
    mask_value: str = "***REDACTED***",
    additional_patterns: frozenset[str] | None = None,
):
    """Create a processor that masks sensitive data in log entries.

    Automatically detects and masks values for keys that contain
    sensitive patterns (case-insensitive matching).

    Args:
        mask_value: The string to replace sensitive values with.
        additional_patterns: Extra patterns to consider sensitive.

    Returns:
        A structlog processor function.

    Example:
        configure_logging(
            extra_processors=[mask_sensitive_data(additional_patterns={"ssn", "credit_card"})]
        )
    """
    patterns = SENSITIVE_PATTERNS
    if additional_patterns:
        patterns = patterns | additional_patterns

    def processor(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        masked_dict = {}
        for key, value in event_dict.items():
            if _is_sensitive_key(key, patterns) and value is not None:
                masked_dict[key] = mask_value
            else:
                masked_dict[key] = _redact_recursive(value, patterns, mask_value)
        return masked_dict

    return processor


def truncate_large_values(max_length: int = 500):
    """Create a processor that truncates overly large string values.

    Prevents log explosion from large data being logged accidentally.

    Args:
        max_length: Maximum string length before truncation.

    Returns:
        A structlog processor function.

    Example:
        configure_logging(
            extra_processors=[truncate_large_values(max_length=1000)]
        )
    """

    def processor(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        for key, value in event_dict.items():
            if isinstance(value, str) and len(value) > max_length:
                event_dict[key] = value[:max_length] + f"...[truncated, {len(value)} chars total]"
        return event_dict

    return processor


def add_environment_info(environment: str):
    """Create a processor that adds environment info to log entries.

    Args:
        environment: Environment name (e.g., "production", "staging", "development").

    Returns:
        A structlog processor function.

    Example:
        configure_logging(
            extra_processors=[add_environment_info(settings.ENVIRONMENT)]
        )
    """

    def processor(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        event_dict["environment"] = environment
        return event_dict

    return processor
