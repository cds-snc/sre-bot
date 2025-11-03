from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from core.logging import get_module_logger
from modules.groups import service, schemas, models
from modules.groups.providers import get_active_providers
from modules.groups.circuit_breaker import get_open_circuit_breakers

logger = get_module_logger()

# Controllers are thin adapters: they accept Pydantic request models, call the
# service boundary, and return Pydantic response models. We intentionally do
# NOT keep any legacy compatibility shims.
router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


@router.post("/add", response_model=schemas.ActionResponse)
def add_member_endpoint(request: schemas.AddMemberRequest):
    """Add member endpoint.

    Delegates to the `service.add_member` function and returns the
    Pydantic `ActionResponse` model directly.

    **Idempotency:**
    - Each request includes an `idempotency_key` field (auto-generated UUID if not provided)
    - Requests with the same `idempotency_key` within 1 hour return the cached response
    - Failed operations are NOT cached to preserve retry semantics
    - Use the same `idempotency_key` for retries to avoid duplicate group additions
    """
    return service.add_member(request)


@router.post("/remove", response_model=schemas.ActionResponse)
def remove_member_endpoint(request: schemas.RemoveMemberRequest):
    """Remove member endpoint.

    Delegates to the `service.remove_member` function and returns the
    Pydantic `ActionResponse` model directly.

    **Idempotency:**
    - Each request includes an `idempotency_key` field (auto-generated UUID if not provided)
    - Requests with the same `idempotency_key` within 1 hour return the cached response
    - Failed operations are NOT cached to preserve retry semantics
    - Use the same `idempotency_key` for retries to avoid duplicate group removals
    """
    return service.remove_member(request)


@router.get("/", response_model=List[schemas.GroupResponse])
def list_groups_endpoint(request: schemas.ListGroupsRequest = Depends()):
    """List groups for a user.

    Accepts query parameters that map to `schemas.ListGroupsRequest` so OpenAPI
    documents the expected parameters (`user_email`, optional `provider`).
    """
    groups = service.list_groups(request)
    # Convert dataclasses to Pydantic response models
    return [
        schemas.GroupResponse.model_validate(models.as_canonical_dict(g))
        for g in groups
    ]


@router.post("/bulk", response_model=schemas.BulkOperationResponse)
def bulk_operations_endpoint(request: schemas.BulkOperationsRequest):
    return service.bulk_operations(request)


# Admin endpoints for circuit breaker management
@router.get("/admin/circuit-breakers", tags=["admin"])
def get_circuit_breaker_status():
    """Get circuit breaker status for all group providers.

    Returns the current state of circuit breakers for each active provider.
    Useful for monitoring and debugging provider health.

    **Admin only**: This endpoint should be protected by admin authentication.

    Returns:
        Dictionary with timestamp and per-provider circuit breaker statistics.
        Each provider shows state (CLOSED, OPEN, HALF_OPEN) and failure counts.
    """
    try:
        providers = get_active_providers()
        status = {}

        for provider_name, provider in providers.items():
            status[provider_name] = provider.get_circuit_breaker_stats()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "providers": status,
        }
    except Exception as e:
        logger.error("circuit_breaker_status_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to get circuit breaker status: {str(e)}"
        )


@router.post("/admin/circuit-breakers/{provider_name}/reset", tags=["admin"])
def reset_circuit_breaker(provider_name: str):
    """Manually reset a provider's circuit breaker to CLOSED state.

    Forces a circuit breaker back to CLOSED state. Use this when you know
    a provider has recovered but the circuit is still open.

    **Admin only**: This endpoint should be protected by admin authentication.

    Args:
        provider_name: Name of the provider (e.g., 'google', 'aws')

    Returns:
        Dictionary confirming the reset with new circuit breaker state.

    Raises:
        HTTPException: 404 if provider not found, 500 on other errors.
    """
    try:
        providers = get_active_providers()

        if provider_name not in providers:
            raise HTTPException(
                status_code=404,
                detail=f"Provider '{provider_name}' not found. Available: {list(providers.keys())}",
            )

        provider = providers[provider_name]
        provider.reset_circuit_breaker()

        logger.info(
            "circuit_breaker_manually_reset",
            provider=provider_name,
        )

        return {
            "success": True,
            "message": f"Circuit breaker for '{provider_name}' has been reset to CLOSED",
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider_name,
            "new_state": provider.get_circuit_breaker_stats(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "circuit_breaker_reset_error", provider=provider_name, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to reset circuit breaker: {str(e)}"
        )


# Health check endpoints
@router.get("/health/circuit-breakers", tags=["health"])
def circuit_breaker_health():
    """Health check endpoint that reports circuit breaker status.

    Returns an overall health status based on circuit breaker states.
    If any circuit breakers are OPEN, the status is 'degraded'.
    Otherwise, the status is 'healthy'.

    Returns:
        Dictionary with status (healthy/degraded) and details per provider.
    """
    try:
        providers = get_active_providers()
        open_circuits = get_open_circuit_breakers()
        all_stats = {}

        for provider_name, provider in providers.items():
            all_stats[provider_name] = provider.get_circuit_breaker_stats()

        if open_circuits:
            return {
                "status": "degraded",
                "open_circuits": open_circuits,
                "message": f"{len(open_circuits)} circuit breaker(s) are OPEN",
                "timestamp": datetime.utcnow().isoformat(),
                "details": all_stats,
            }
        else:
            return {
                "status": "healthy",
                "open_circuits": [],
                "message": "All circuit breakers are CLOSED or HALF_OPEN",
                "timestamp": datetime.utcnow().isoformat(),
                "details": all_stats,
            }
    except Exception as e:
        logger.error("circuit_breaker_health_check_error", error=str(e))
        return {
            "status": "unknown",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
