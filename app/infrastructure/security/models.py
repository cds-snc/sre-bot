"""Security-layer principal models."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuthPrincipalSource(StrEnum):
    """Source of authenticated principal information."""

    SLACK = "slack"
    API_JWT = "api_jwt"
    WEBHOOK = "webhook"
    SYSTEM = "system"


class User(BaseModel):
    """Normalized authenticated principal across supported transports."""

    model_config = ConfigDict(use_enum_values=False)

    user_id: str = Field(..., description="Canonical user identifier")
    email: str = Field(..., description="User email address")
    display_name: str = Field(..., description="Human-readable principal name")
    source: AuthPrincipalSource = Field(..., description="Principal source")
    platform_id: str = Field(..., description="Source-specific identifier")
    permissions: list[str] = Field(
        default_factory=list,
        description="Permissions or roles attached to this principal",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific metadata for the authenticated principal",
    )
