"""Infrastructure auth module - identity resolution across platforms.

Centralized identity resolution for Slack, JWT, webhooks, and system identities.
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from integrations.slack.client import SlackClientManager


class IdentitySource(Enum):
    """Source of identity information."""

    SLACK = "slack"
    API_JWT = "api_jwt"
    WEBHOOK = "webhook"
    SYSTEM = "system"


@dataclass
class UserIdentity:
    """Normalized user identity across platforms."""

    user_id: str
    email: str
    display_name: str
    source: IdentitySource
    platform_id: str  # Slack user ID, JWT sub, etc.
    permissions: List[str]
    metadata: Dict[str, Any]


class IdentityResolver:
    """Centralized identity resolution across platforms."""

    def resolve_from_slack(
        self,
        slack_user_id: str,
    ) -> UserIdentity:
        """Resolve Slack user to normalized identity.

        Args:
            slack_user_id: Slack user ID to resolve

        Returns:
            UserIdentity with resolved information

        Raises:
            ValueError: If Slack user info cannot be fetched
        """
        client = SlackClientManager.get_client()
        response = client.users_info(user=slack_user_id)
        if not response["ok"]:
            raise ValueError(f"Failed to fetch Slack user info for {slack_user_id}")
        user = response["user"]

        return UserIdentity(
            user_id=user["profile"]["email"],  # Use email as canonical ID
            email=user["profile"]["email"],
            display_name=user["profile"]["display_name"],
            source=IdentitySource.SLACK,
            platform_id=slack_user_id,
            permissions=[],
            # permissions=await self._get_user_permissions(user["profile"]["email"]),
            metadata={
                "slack_team": response.get("team_id"),
                "slack_user_name": user["name"],
                "slack_user_id": slack_user_id,
            },
        )

    def resolve_from_jwt(self, jwt_payload: Dict[str, Any]) -> UserIdentity:
        """Resolve JWT token to normalized identity.

        Args:
            jwt_payload: Decoded JWT payload

        Returns:
            UserIdentity with resolved information
        """
        user_id = jwt_payload.get("sub", "unknown")
        email = jwt_payload.get("email", "unknown")
        display_name = jwt_payload.get("name", user_id)

        return UserIdentity(
            user_id=user_id,
            email=email,
            display_name=display_name,
            source=IdentitySource.API_JWT,
            platform_id=user_id,
            permissions=jwt_payload.get("permissions", []),
            metadata={"jwt_iss": jwt_payload.get("iss")},
        )

    def resolve_from_webhook(
        self, webhook_payload: Dict[str, Any], webhook_source: str = "unknown"
    ) -> UserIdentity:
        """Resolve webhook authentication to identity.

        Args:
            webhook_payload: Webhook payload data
            webhook_source: Source of the webhook (e.g., 'github', 'gitlab')

        Returns:
            UserIdentity with webhook identity
        """
        user_id = webhook_payload.get("user_id", "system")
        email = webhook_payload.get("email", "system@sre-bot.local")
        display_name = webhook_payload.get("name", user_id)

        return UserIdentity(
            user_id=user_id,
            email=email,
            display_name=display_name,
            source=IdentitySource.WEBHOOK,
            platform_id=webhook_payload.get("client_id", "unknown"),
            permissions=["webhook"],
            metadata={**webhook_payload, "webhook_source": webhook_source},
        )


# Singleton instance
identity_resolver = IdentityResolver()
