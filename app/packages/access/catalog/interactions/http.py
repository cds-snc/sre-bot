"""Access Catalog FastAPI route handlers — HTTP transport layer only.

Two endpoints:
    GET /api/v1/access/catalog           — list all configured platforms.
    GET /api/v1/access/catalog/{platform} — list entitlements for one platform,
                                           annotated with the requester's membership.

Handlers validate, delegate to the service, and map OperationResult to HTTP.
No business logic lives here.
"""

from typing import Annotated, Protocol

import structlog
from fastapi import APIRouter, Depends, HTTPException, Security

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.security import get_current_user
from infrastructure.security.models import User
from packages.access.catalog.domain import EntitlementEntry, PlatformSummary
from packages.access.catalog.providers import get_catalog_service, get_catalog_settings
from packages.access.catalog.schemas import (
    EntitlementEntryResponse,
    EntitlementListResponse,
    ParsedTokenResponse,
    PlatformListResponse,
    PlatformSummaryResponse,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/access/catalog", tags=["Access Catalog"])


class _CatalogSettingsPort(Protocol):
    """Structural contract for settings consumed by route handlers."""

    enabled: bool


class _CatalogServicePort(Protocol):
    """Structural contract for catalog service consumed by route handlers."""

    def list_platforms(self) -> OperationResult[list[PlatformSummary]]: ...

    def list_entitlements(
        self,
        platform: str,
        user_email: str,
    ) -> OperationResult[list[EntitlementEntry]]: ...


def _map_status(status: OperationStatus) -> int:
    """Map OperationStatus to stable HTTP status codes."""
    if status == OperationStatus.NOT_FOUND:
        return 404
    if status == OperationStatus.PERMANENT_ERROR:
        return 400
    if status == OperationStatus.TRANSIENT_ERROR:
        return 503
    if status == OperationStatus.UNAUTHORIZED:
        return 401
    return 500


def _resolve_catalog_service(
    service: _CatalogServicePort | None,
) -> _CatalogServicePort:
    """Resolve catalog service lazily after feature-gate checks."""
    return service if service is not None else get_catalog_service()


def _noop_catalog_service() -> _CatalogServicePort | None:
    """No-op dependency used to defer heavy service assembly until after gating."""
    return None


@router.get(
    "",
    response_model=PlatformListResponse,
    summary="List configured platforms",
    description="Return all platforms enrolled in the access management system.",
    status_code=200,
    responses={
        503: {"description": "Access Catalog feature is disabled."},
    },
)
def list_platforms(
    settings: Annotated[_CatalogSettingsPort, Depends(get_catalog_settings)],
    current_user: Annotated[User, Security(get_current_user, scopes=["sre-bot:access-catalog"])],
    service: Annotated[_CatalogServicePort | None, Depends(_noop_catalog_service)] = None,
) -> PlatformListResponse:
    """List all configured platforms."""
    log = logger.bind(
        endpoint="GET /api/v1/access/catalog",
        requested_by=current_user.email,
    )
    log.info("catalog_list_platforms_request")

    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Catalog is not enabled")
    service_dep = _resolve_catalog_service(service)

    result = service_dep.list_platforms()
    if not result.is_success:
        raise HTTPException(
            status_code=_map_status(result.status),
            detail=result.message or "Failed to retrieve platforms",
        )
    if result.data is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve platforms")

    return PlatformListResponse(platforms=[_platform_to_response(p) for p in result.data])


@router.get(
    "/{platform}",
    response_model=EntitlementListResponse,
    summary="List entitlements for a platform",
    description=(
        "Return all entitlements available on the platform, annotated with the authenticated user's current membership status."
    ),
    status_code=200,
    responses={
        404: {"description": "Platform not found."},
        503: {"description": "Access Catalog feature is disabled."},
    },
)
def list_entitlements(
    platform: str,
    settings: Annotated[_CatalogSettingsPort, Depends(get_catalog_settings)],
    current_user: Annotated[User, Security(get_current_user, scopes=["sre-bot:access-catalog"])],
    service: Annotated[_CatalogServicePort | None, Depends(_noop_catalog_service)] = None,
) -> EntitlementListResponse:
    """List entitlements for a platform with membership annotation."""
    log = logger.bind(
        endpoint=f"GET /api/v1/access/catalog/{platform}",
        platform=platform,
        requested_by=current_user.email,
    )
    log.info("catalog_list_entitlements_request")

    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Catalog is not enabled")
    service_dep = _resolve_catalog_service(service)

    result = service_dep.list_entitlements(
        platform=platform.strip().lower(),
        user_email=current_user.email,
    )

    if not result.is_success:
        raise HTTPException(
            status_code=_map_status(result.status),
            detail=result.message or "Failed to retrieve entitlements",
        )

    entries: list[EntitlementEntry] = result.data or []
    return EntitlementListResponse(
        platform=platform.strip().lower(),
        entitlements=[_entry_to_response(e) for e in entries],
    )


# ------------------------------------------------------------------
# Private serialisation helpers
# ------------------------------------------------------------------


def _platform_to_response(summary: PlatformSummary) -> PlatformSummaryResponse:
    return PlatformSummaryResponse(
        key=summary.key,
        display_name=summary.display_name,
        authn_group_slug=summary.authn_group_slug,
        entitlement_count=summary.entitlement_count,
    )


def _entry_to_response(entry: EntitlementEntry) -> EntitlementEntryResponse:
    pt = entry.parsed_token
    return EntitlementEntryResponse(
        token=entry.token,
        group_slug=entry.group_slug,
        group_email=entry.group_email,
        mode=entry.mode,
        requestable=entry.requestable,
        already_provisioned=entry.already_provisioned,
        parsed=ParsedTokenResponse(
            raw=pt.raw,
            product=pt.product,
            env=pt.env,
            role=pt.role,
            service=pt.service,
            resource=pt.resource,
            parsed=pt.parsed,
        ),
    )
