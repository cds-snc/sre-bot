"""Access Catalog FastAPI route handlers — HTTP transport layer only.

Two endpoints:
    GET /api/v1/access/catalog           — list all configured platforms.
    GET /api/v1/access/catalog/{platform} — list entitlements for one platform,
                                           annotated with the requester's membership.

Handlers validate, delegate to the service, and map OperationResult to HTTP.
No business logic lives here.
"""

from typing import Annotated, List, Protocol

import structlog
from fastapi import APIRouter, Depends, HTTPException, Security

from infrastructure.identity.models import User
from infrastructure.operations import OperationStatus
from infrastructure.services import get_current_user
from packages.access_catalog.domain import EntitlementEntry, PlatformSummary
from packages.access_catalog.providers import get_catalog_service, get_catalog_settings
from packages.access_catalog.schemas import (
    EntitlementEntryResponse,
    EntitlementListResponse,
    ParsedTokenResponse,
    PlatformListResponse,
    PlatformSummaryResponse,
)
from packages.access_catalog.service import CatalogServicePort

logger = structlog.get_logger()
router = APIRouter(prefix="/access/catalog", tags=["Access Catalog"])


class _CatalogSettingsPort(Protocol):
    """Structural contract for settings consumed by route handlers."""

    enabled: bool


@router.get(
    "",
    response_model=PlatformListResponse,
    summary="List configured platforms",
    description="Return all platforms enrolled in the access management system.",
)
def list_platforms(
    service: Annotated[CatalogServicePort, Depends(get_catalog_service)],
    settings: Annotated[_CatalogSettingsPort, Depends(get_catalog_settings)],
    current_user: Annotated[
        User, Security(get_current_user, scopes=["sre-bot:access-catalog"])
    ],
) -> PlatformListResponse:
    """List all configured platforms."""
    log = logger.bind(
        endpoint="GET /api/v1/access/catalog",
        requested_by=current_user.email,
    )
    log.info("catalog_list_platforms_request")

    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Catalog is not enabled")

    result = service.list_platforms()
    if not result.is_success or result.data is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve platforms")

    return PlatformListResponse(
        platforms=[_platform_to_response(p) for p in result.data]
    )


@router.get(
    "/{platform}",
    response_model=EntitlementListResponse,
    summary="List entitlements for a platform",
    description=(
        "Return all entitlements available on the platform, annotated with "
        "the authenticated user's current membership status."
    ),
)
def list_entitlements(
    platform: str,
    service: Annotated[CatalogServicePort, Depends(get_catalog_service)],
    settings: Annotated[_CatalogSettingsPort, Depends(get_catalog_settings)],
    current_user: Annotated[
        User, Security(get_current_user, scopes=["sre-bot:access-catalog"])
    ],
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

    result = service.list_entitlements(
        platform=platform.strip().lower(),
        user_email=current_user.email,
    )

    if not result.is_success:
        if result.status == OperationStatus.NOT_FOUND:
            raise HTTPException(
                status_code=404,
                detail=result.message or f"Platform '{platform}' not found",
            )
        raise HTTPException(
            status_code=500,
            detail=result.message or "Failed to retrieve entitlements",
        )

    entries: List[EntitlementEntry] = result.data or []
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
