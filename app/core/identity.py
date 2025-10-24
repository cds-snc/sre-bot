# core/identity.py
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from integrations.slack.client import SlackClientManager


class IdentitySource(Enum):
    SLACK = "slack"
    API_JWT = "api_jwt"
    WEBHOOK = "webhook"
    SYSTEM = "system"


@dataclass
class UserIdentity:
    user_id: str
    email: str
    display_name: str
    source: IdentitySource
    platform_id: str  # Slack user ID, JWT sub, etc.
    permissions: List[str]
    metadata: Dict[str, Any]


class IdentityResolver:
    """Centralized identity resolution across platforms"""

    def resolve_from_slack(
        self,
        slack_user_id: str,
    ) -> UserIdentity:
        """Resolve Slack user to normalized identity"""
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
        """Resolve JWT token to normalized identity"""
        return UserIdentity(
            user_id=jwt_payload["email"],
            email=jwt_payload["email"],
            display_name=jwt_payload.get("name", jwt_payload["email"]),
            source=IdentitySource.API_JWT,
            platform_id=jwt_payload["sub"],
            permissions=jwt_payload.get("permissions", []),
            metadata={"jwt_iss": jwt_payload.get("iss")},
        )

    def resolve_from_webhook(self, webhook_auth: Dict[str, Any]) -> UserIdentity:
        """Resolve webhook authentication to system identity"""
        return UserIdentity(
            user_id="system",
            email="system@sre-bot.local",
            display_name="SRE Bot System",
            source=IdentitySource.WEBHOOK,
            platform_id=webhook_auth.get("client_id", "unknown"),
            permissions=["webhook"],
            metadata=webhook_auth,
        )


# Singleton instance
identity_resolver = IdentityResolver()
