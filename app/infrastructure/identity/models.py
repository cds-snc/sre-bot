"""User identity models and enums.

Defines normalized user identity representations across platforms
(Slack, JWT, webhooks, system).
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class IdentitySource(str, Enum):
    """Source of identity information."""

    SLACK = "slack"
    API_JWT = "api_jwt"
    WEBHOOK = "webhook"
    SYSTEM = "system"


class User(BaseModel):
    """Normalized user identity across platforms.

    Represents a unified user identity regardless of source (Slack, JWT, webhook).
    All user information is normalized to this model for consistent handling
    throughout the application.
    """

    model_config = ConfigDict(use_enum_values=False)

    user_id: str = Field(..., description="Canonical user identifier (typically email)")
    email: str = Field(..., description="User's email address")
    display_name: str = Field(..., description="User's display name")
    source: IdentitySource = Field(..., description="Source of identity information")
    platform_id: str = Field(
        ..., description="Platform-specific ID (Slack user ID, JWT sub, etc.)"
    )
    permissions: List[str] = Field(
        default_factory=list, description="User's permissions/roles"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Platform-specific metadata"
    )


class SlackUser(User):
    """Slack-specific user with additional Slack metadata.

    Extends User with Slack-specific fields extracted from Slack API responses.
    """

    slack_user_id: str = Field(..., description="Slack user ID")
    slack_team_id: str = Field(default="", description="Slack workspace/team ID")
    slack_user_name: str = Field(default="", description="Slack username")
