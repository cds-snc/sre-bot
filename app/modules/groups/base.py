from typing import Dict, List, Optional

from core.logging import get_module_logger

from modules.groups.event_system import dispatch_event
from modules.groups.providers import get_active_providers
from modules.groups.errors import IntegrationError
from modules.groups.responses import format_error_response
from modules.groups.providers.base import OperationResult, OperationStatus
import asyncio

logger = get_module_logger()


def _map_integration_error_to_response(err: IntegrationError) -> Dict:
    """Convert IntegrationError to a minimal API error dict using format_error_response.

    Keep the mapping small: include the integration error message and, when present,
    surface a compact diagnostic in `details` from the wrapped IntegrationResponse.
    """
    resp = getattr(err, "response", None)
    details = None
    if resp is not None:
        # Keep only small, useful metadata for API responses
        details = {
            "integration_success": getattr(resp, "success", None),
            "integration_error": getattr(resp, "error", None),
            "integration_meta": getattr(resp, "meta", None),
        }

    return format_error_response(
        action="integration_error",
        error_message=str(err),
        error_code="INTEGRATION_ERROR",
        details=details,
    )


def get_user_managed_groups(
    user_email: str, provider_type: Optional[str] = None
) -> Dict[str, List]:
    """Get all groups user can manage across providers.

    On provider IntegrationError, map to an empty list for that provider and log the
    diagnostic — the API layer should surface a consolidated view including other
    providers' results. IntegrationError mapping for API responses is handled in
    the API layer (`modules.groups.api`) where handlers call these functions.
    """
    providers = get_active_providers(provider_type)
    result = {}

    for name, provider in providers.items():
        try:
            # Prefer async provider API
            if hasattr(provider, "list_group_members"):
                op: OperationResult = _run_provider_async(
                    provider.list_group_members(user_email)
                )
                if op.status == OperationStatus.SUCCESS:
                    data = op.data or {}
                    groups = data.get("members") or data.get("result") or []
                    result[name] = groups
                else:
                    logger.warning(
                        f"Provider {name} returned error status: {op.status}"
                    )
                    result[name] = []
            elif hasattr(provider, "get_user_managed_groups"):
                # Legacy sync method
                groups = provider.get_user_managed_groups(user_email)
                result[name] = groups
            else:
                logger.warning(
                    f"Provider {name} has no list/get_user_managed_groups method"
                )
                result[name] = []
        except IntegrationError as ie:
            logger.warning(f"Provider {name} raised IntegrationError: {ie}")
            result[name] = []
        except Exception as e:
            logger.warning(f"Failed to get groups from {name}: {e}")
            result[name] = []

    return result


def add_member_to_group(
    group_id: str,
    member_email: str,
    justification: str,
    provider_type: str,
    requestor_email: str,
) -> Dict:
    """Add member to group using appropriate provider."""
    provider = get_active_providers(provider_type)[provider_type]

    # Validate permissions using IDP as source of truth
    if not validate_group_permissions(
        requestor_email, group_id, "add_member", provider_type
    ):
        raise PermissionError(f"User {requestor_email} cannot modify group {group_id}")

    # Perform the action using async provider call
    try:
        # Prefer async API
        if hasattr(provider, "add_group_member"):
            op: OperationResult = _run_provider_async(
                provider.add_group_member(
                    group_id, member_email, justification=justification
                )
            )
            if op.status != OperationStatus.SUCCESS:
                return format_error_response(
                    action="add_member",
                    error_message=op.message,
                    error_code="PROVIDER_ERROR",
                    details=op.data,
                )
            dispatch_event(
                "group.member.added",
                {
                    "group_id": group_id,
                    "member_email": member_email,
                    "requestor_email": requestor_email,
                    "provider": provider_type,
                    "justification": justification,
                    "result": op.data,
                },
            )
            return op.data or {}
        elif hasattr(provider, "add_member"):
            # Legacy sync method - keep existing IntegrationError behaviour
            try:
                result = provider.add_member(group_id, member_email, justification)
            except IntegrationError as ie:
                logger.error(f"IntegrationError while adding member: {ie}")
                return _map_integration_error_to_response(ie)
            dispatch_event(
                "group.member.added",
                {
                    "group_id": group_id,
                    "member_email": member_email,
                    "requestor_email": requestor_email,
                    "provider": provider_type,
                    "justification": justification,
                    "result": result,
                },
            )
            return result
        else:
            return format_error_response(
                action="add_member",
                error_message="provider does not support add_member",
                error_code="PROVIDER_ERROR",
            )
    except IntegrationError as ie:
        logger.error(f"IntegrationError while adding member: {ie}")
        return _map_integration_error_to_response(ie)
    except Exception as e:
        logger.error(f"Error while adding member: {e}")
        return format_error_response(
            action="add_member", error_message=str(e), error_code="OPERATION_FAILED"
        )


def remove_member_from_group(
    group_id: str,
    member_email: str,
    justification: str,
    provider_type: str,
    requestor_email: str,
) -> Dict:
    """Remove member from group using appropriate provider."""
    provider = get_active_providers(provider_type)[provider_type]

    # Validate permissions using async API if available, else fallback to sync
    try:
        if hasattr(provider, "list_group_members"):
            perm_op: OperationResult = _run_provider_async(
                provider.list_group_members(group_id)
            )
            if perm_op.status == OperationStatus.SUCCESS:
                members = (
                    (perm_op.data or {}).get("members")
                    or (perm_op.data or {}).get("result")
                    or []
                )
                can_modify = any(
                    m.get("email") == requestor_email
                    for m in members
                    if isinstance(m, dict)
                )
                if not can_modify:
                    if hasattr(provider, "validate_permissions"):
                        if not provider.validate_permissions(
                            requestor_email, group_id, "remove_member"
                        ):
                            raise PermissionError(
                                f"User {requestor_email} cannot modify group {group_id}"
                            )
                    else:
                        raise PermissionError(
                            f"User {requestor_email} cannot modify group {group_id}"
                        )
        elif hasattr(provider, "validate_permissions"):
            if not provider.validate_permissions(
                requestor_email, group_id, "remove_member"
            ):
                raise PermissionError(
                    f"User {requestor_email} cannot modify group {group_id}"
                )
        else:
            raise PermissionError(
                f"User {requestor_email} cannot modify group {group_id}"
            )

        # Perform remove operation
        if hasattr(provider, "remove_group_member"):
            op: OperationResult = _run_provider_async(
                provider.remove_group_member(
                    group_id, member_email, justification=justification
                )
            )
            if op.status != OperationStatus.SUCCESS:
                return format_error_response(
                    action="remove_member",
                    error_message=op.message,
                    error_code="PROVIDER_ERROR",
                    details=op.data,
                )
            dispatch_event(
                "group.member.removed",
                {
                    "group_id": group_id,
                    "member_email": member_email,
                    "requestor_email": requestor_email,
                    "provider": provider_type,
                    "justification": justification,
                    "result": op.data,
                },
            )
            return op.data or {}
        elif hasattr(provider, "remove_member"):
            try:
                result = provider.remove_member(group_id, member_email, justification)
            except IntegrationError as ie:
                logger.error(f"IntegrationError while removing member: {ie}")
                return _map_integration_error_to_response(ie)
            dispatch_event(
                "group.member.removed",
                {
                    "group_id": group_id,
                    "member_email": member_email,
                    "requestor_email": requestor_email,
                    "provider": provider_type,
                    "justification": justification,
                    "result": result,
                },
            )
            return result
        else:
            return format_error_response(
                action="remove_member",
                error_message="provider does not support remove_member",
                error_code="PROVIDER_ERROR",
            )
    except IntegrationError as ie:
        logger.error(f"IntegrationError while removing member: {ie}")
        return _map_integration_error_to_response(ie)
    except Exception as e:
        logger.error(f"Error while removing member: {e}")
        return format_error_response(
            action="remove_member", error_message=str(e), error_code="OPERATION_FAILED"
        )


def validate_group_permissions(
    user_email: str, group_id: str, action: str, provider_type: str
) -> bool:
    """Validate permissions using IDP as source of truth."""
    provider = get_active_providers(provider_type)[provider_type]
    # prefer provider async validation where possible
    try:
        op: OperationResult = _run_provider_async(provider.list_group_members(group_id))
        if op.status == OperationStatus.SUCCESS:
            members = (
                (op.data or {}).get("members") or (op.data or {}).get("result") or []
            )
            return any(
                m.get("email") == user_email for m in members if isinstance(m, dict)
            )
    except Exception:
        # fall back to sync method
        try:
            return provider.validate_permissions(user_email, group_id, action)
        except AttributeError:
            return False

    return False


def _run_provider_async(coro) -> OperationResult:
    """Run an async provider coroutine from sync code and return OperationResult.

    If called within an existing event loop, uses asyncio.run_coroutine_threadsafe.
    Otherwise uses asyncio.run.
    """
    # If the coro is actually an OperationResult already (legacy adapters), return it
    if isinstance(coro, OperationResult):
        return coro

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're in an event loop (e.g., when running the app async). Run coroutine in a new thread-safe manner.
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    else:
        return asyncio.run(coro)
