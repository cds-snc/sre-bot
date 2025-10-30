"""Response formatting utilities for orchestration results.

Lightweight helpers to format the orchestration response structure expected by
API and Slack handlers. Designed to be import-safe during phased rollout.
"""

from typing import Dict, Any, Optional, cast
from datetime import datetime, timezone

from core.logging import get_module_logger

from modules.groups.types import (
    PrimaryDataTypedDict,
    ReadResponseTypedDict,
    OrchestrationResponseTypedDict,
    OperationResultLike,
)

logger = get_module_logger()


def serialize_primary(op: OperationResultLike) -> PrimaryDataTypedDict:
    """Serialize an OperationResult-like object to a dict."""
    return {
        "status": getattr(op, "status", None),
        "message": getattr(op, "message", ""),
        "data": getattr(op, "data", None),
        "error_code": getattr(op, "error_code", None),
        "retry_after": getattr(op, "retry_after", None),
    }


def format_orchestration_response(
    primary: OperationResultLike,
    propagation: Dict[str, OperationResultLike],
    partial_failures: bool,
    correlation_id: str,
    action: str = "operation",
    group_id: Optional[str] = None,
    member_email: Optional[str] = None,
) -> OrchestrationResponseTypedDict:
    """Format orchestration response with primary and propagation results.

    `primary` is expected to be an OperationResult-like object. We avoid
    importing OperationResult at module import time to keep this module
    lightweight.
    """
    try:
        overall_success = getattr(primary, "status").name == "SUCCESS"
    except Exception:
        overall_success = False

    primary_data = {
        "status": (
            getattr(primary, "status").name
            if hasattr(primary, "status") and getattr(primary, "status") is not None
            else None
        ),
        "message": getattr(primary, "message", ""),
    }
    if getattr(primary, "data", None):
        primary_data["data"] = getattr(primary, "data")
    if getattr(primary, "error_code", None):
        primary_data["error_code"] = getattr(primary, "error_code")
    if getattr(primary, "retry_after", None):
        primary_data["retry_after"] = getattr(primary, "retry_after")

    propagation_data: Dict[str, Any] = {}
    for provider_name, result in (propagation or {}).items():
        propagation_data[provider_name] = {
            "status": (
                getattr(result, "status").name
                if hasattr(result, "status") and getattr(result, "status") is not None
                else None
            ),
            "message": getattr(result, "message", ""),
        }
        if getattr(result, "data", None):
            propagation_data[provider_name]["data"] = getattr(result, "data")
        if getattr(result, "error_code", None):
            propagation_data[provider_name]["error_code"] = getattr(
                result, "error_code"
            )
        if getattr(result, "retry_after", None):
            propagation_data[provider_name]["retry_after"] = getattr(
                result, "retry_after"
            )

    response = {
        "success": overall_success,
        "correlation_id": correlation_id,
        "action": action,
        "primary": primary_data,
        "propagation": propagation_data,
        "partial_failures": partial_failures,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if group_id:
        response["group_id"] = group_id
    if member_email:
        response["member_email"] = member_email

    return cast(OrchestrationResponseTypedDict, response)


def format_read_response(
    primary: OperationResultLike,
    action: str = "read",
    group_id: Optional[str] = None,
    member_email: Optional[str] = None,
) -> ReadResponseTypedDict:
    """Format response for read-only provider operations.

    Read operations do not perform propagation, do not require a
    correlation id or justification, and should return a compact
    response containing only the primary result and metadata.

    This helper mirrors the primary formatting portion of
    `format_orchestration_response` but omits propagation-related fields.
    """
    try:
        overall_success = getattr(primary, "status").name == "SUCCESS"
    except Exception:
        overall_success = False

    primary_data = {
        "status": (
            getattr(primary, "status").name
            if hasattr(primary, "status") and getattr(primary, "status") is not None
            else None
        ),
        "message": getattr(primary, "message", ""),
    }
    if getattr(primary, "data", None):
        primary_data["data"] = getattr(primary, "data")
    if getattr(primary, "error_code", None):
        primary_data["error_code"] = getattr(primary, "error_code")
    if getattr(primary, "retry_after", None):
        primary_data["retry_after"] = getattr(primary, "retry_after")

    response: Dict[str, Any] = {
        "success": overall_success,
        "action": action,
        "primary": primary_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if group_id:
        response["group_id"] = group_id
    if member_email:
        response["member_email"] = member_email

    return cast(ReadResponseTypedDict, response)


def extract_orchestration_response_for_slack(orch_response: Dict[str, Any]) -> str:
    """Convert orchestration response to Slack-friendly message.

    Emphasizes primary success and reports partial failures.
    """
    if not orch_response.get("success"):
        primary = orch_response.get("primary", {})
        error_msg = primary.get("message", "Operation failed")
        return f"❌ {error_msg}"

    action = orch_response.get("action", "operation")
    member = orch_response.get("member_email", "user")
    group = orch_response.get("group_id", "group")
    partial = orch_response.get("partial_failures", False)
    propagation = orch_response.get("propagation", {})

    action_emoji = {"add_member": "➕", "remove_member": "➖"}.get(action, "✅")

    msg = f"{action_emoji} {member} in group `{group}`"

    if partial and propagation:
        failed_providers = [
            name
            for name, result in propagation.items()
            if (result or {}).get("status") != "SUCCESS"
        ]
        if failed_providers:
            msg += f"\n⚠️ Sync pending for: {', '.join(failed_providers)}"

    return msg


def extract_orchestration_response_for_api(
    orch_response: Dict[str, Any], status_code: int = 200
) -> tuple[Dict[str, Any], int]:
    """Return orchestration response tuple for API handlers.

    Currently passthrough; future logic may map status codes based on primary
    and propagation results.
    """
    # If orchestration marked the overall result as failure, return 500 to
    # surface the error to API clients; otherwise use the provided status_code.
    try:
        success = bool(orch_response.get("success", False))
    except Exception:  # pylint: disable=broad-except
        success = False

    return orch_response, (status_code if success else 500)
