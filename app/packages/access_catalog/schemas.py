"""Access Catalog Pydantic HTTP response models.

These models are the only types that cross the HTTP boundary.
They are never used inside the service layer.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel


class ParsedTokenResponse(BaseModel):
    """Structured breakdown of an entitlement token."""

    raw: str
    product: str = ""
    env: Optional[str] = None
    role: str = ""
    service: Optional[str] = None
    resource: Optional[str] = None
    parsed: bool = False


class PlatformSummaryResponse(BaseModel):
    """One configured platform."""

    key: str
    display_name: str
    authn_group_slug: str
    entitlement_count: Optional[int] = None


class PlatformListResponse(BaseModel):
    """Response for GET /api/v1/access/catalog."""

    platforms: List[PlatformSummaryResponse]


class EntitlementEntryResponse(BaseModel):
    """One entitlement for a platform, annotated with membership status."""

    token: str
    group_slug: str
    group_email: str
    mode: Literal["sync_managed", "ephemeral", "deactivated"]
    requestable: bool
    already_provisioned: Optional[bool] = None
    parsed: ParsedTokenResponse


class EntitlementListResponse(BaseModel):
    """Response for GET /api/v1/access/catalog/{platform}."""

    platform: str
    entitlements: List[EntitlementEntryResponse]
