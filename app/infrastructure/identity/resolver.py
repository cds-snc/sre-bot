"""User identity resolution with dependency injection.

Resolves user identity from various sources (Slack, JWT, webhooks)
to a normalized User representation.

All dependencies are injected via constructor - no global state.
"""

import structlog
from typing import Any, Dict

from infrastructure.identity.models import IdentitySource, SlackUser, User


logger = structlog.get_logger()


class IdentityResolver:
    """Resolve user identity across platforms.

    Centralizes identity resolution logic for Slack, JWT, webhooks,
    and system identities. All dependencies are injected, making it
    testable and composable.

    Example:
        from infrastructure.identity import IdentityResolver
        from integrations.slack.client import SlackClientManager

        resolver = IdentityResolver(slack_client_manager=SlackClientManager)
        user = resolver.resolve_from_slack("U123ABC")
    """

    def __init__(self, slack_client_manager=None):
        """Initialize identity resolver.

        Args:
            slack_client_manager: Slack client manager for API calls.
                                 If None, Slack resolution will fail gracefully.
        """
        self._slack_client_manager = slack_client_manager
        self._logger = logger.bind(component="identity_resolver")

    def resolve_from_slack(self, slack_user_id: str) -> SlackUser:
        """Resolve Slack user to normalized identity.

        Args:
            slack_user_id: Slack user ID to resolve

        Returns:
            SlackUser with resolved information

        Raises:
            ValueError: If Slack client is not available or user cannot be fetched
        """
        if not self._slack_client_manager:
            raise ValueError("Slack client manager not configured")

        log = self._logger.bind(
            slack_user_id=slack_user_id, method="resolve_from_slack"
        )
        log.info("resolving_slack_user")

        try:
            client = self._slack_client_manager.get_client()
            response = client.users_info(user=slack_user_id)

            if not response.get("ok"):
                error_msg = f"Failed to fetch Slack user info: {response.get('error', 'unknown')}"
                log.error("slack_user_fetch_failed", error=response.get("error"))
                raise ValueError(error_msg)

            user = response["user"]
            email = user.get("profile", {}).get("email", "")
            display_name = user.get("profile", {}).get("display_name", "")

            identity = SlackUser(
                user_id=email,
                email=email,
                display_name=display_name,
                source=IdentitySource.SLACK,
                platform_id=slack_user_id,
                slack_user_id=slack_user_id,
                slack_team_id=response.get("team_id", ""),
                slack_user_name=user.get("name", ""),
                permissions=[],
                metadata={
                    "slack_team": response.get("team_id"),
                    "slack_user_name": user.get("name", ""),
                    "slack_user_id": slack_user_id,
                },
            )
            log.info("slack_user_resolved", user_id=identity.user_id)
            return identity

        except Exception as exc:
            log.error("slack_resolution_error", error=str(exc), exc_info=True)
            raise

    def resolve_from_jwt(self, jwt_payload: Dict[str, Any]) -> User:
        """Resolve JWT token to normalized identity.

        Args:
            jwt_payload: Decoded JWT payload with standard claims

        Returns:
            User with resolved information from JWT claims
        """
        log = self._logger.bind(method="resolve_from_jwt")
        log.info("resolving_jwt_user", sub=jwt_payload.get("sub"))

        user_id = jwt_payload.get("sub", "unknown")
        email = jwt_payload.get("email", "unknown")
        display_name = jwt_payload.get("name", user_id)

        identity = User(
            user_id=user_id,
            email=email,
            display_name=display_name,
            source=IdentitySource.API_JWT,
            platform_id=user_id,
            permissions=jwt_payload.get("permissions", []),
            metadata={"jwt_iss": jwt_payload.get("iss", "")},
        )
        log.info("jwt_user_resolved", user_id=identity.user_id)
        return identity

    def resolve_from_webhook(
        self,
        webhook_payload: Dict[str, Any],
        webhook_source: str = "unknown",
    ) -> User:
        """Resolve webhook authentication to system identity.

        Args:
            webhook_payload: Webhook payload data
            webhook_source: Source of the webhook (e.g., 'github', 'gitlab')

        Returns:
            User with webhook identity
        """
        log = self._logger.bind(
            method="resolve_from_webhook", webhook_source=webhook_source
        )
        log.info("resolving_webhook_identity")

        user_id = webhook_payload.get("user_id", "system")
        email = webhook_payload.get("email", "system@sre-bot.local")
        display_name = webhook_payload.get("name", user_id)

        identity = User(
            user_id=user_id,
            email=email,
            display_name=display_name,
            source=IdentitySource.WEBHOOK,
            platform_id=webhook_payload.get("client_id", "unknown"),
            permissions=["webhook"],
            metadata={**webhook_payload, "webhook_source": webhook_source},
        )
        log.info("webhook_identity_resolved", user_id=identity.user_id)
        return identity

    def resolve_system_identity(self) -> User:
        """Create system identity for internal operations.

        Returns:
            User with system identity
        """
        log = self._logger.bind(method="resolve_system_identity")
        log.info("creating_system_identity")

        identity = User(
            user_id="system",
            email="system@sre-bot.local",
            display_name="SRE Bot System",
            source=IdentitySource.SYSTEM,
            platform_id="system",
            permissions=["system"],
            metadata={"system": True},
        )
        return identity
