"""Identity service for dependency injection.

Provides a class-based interface to the identity resolution system for easier DI and testing.
"""

from typing import Any, Dict, Optional, TYPE_CHECKING

from infrastructure.identity.models import User

if TYPE_CHECKING:
    from infrastructure.identity.resolver import IdentityResolver
    from infrastructure.configuration import Settings
    from integrations.slack.client import SlackClientManager


class IdentityService:
    """Class-based identity service.

    Wraps the IdentityResolver with a service interface to support
    dependency injection and easier testing with mocks.

    This is a thin facade - all actual work is delegated to the underlying
    IdentityResolver instance.

    Usage:
        # Via dependency injection
        from infrastructure.services import IdentityServiceDep

        @router.post("/identity/slack")
        def resolve_slack_user(identity: IdentityServiceDep, slack_user_id: str):
            user = identity.resolve_from_slack(slack_user_id)
            return {"user": user.model_dump()}

        @router.post("/identity/jwt")
        def resolve_jwt_user(identity: IdentityServiceDep, token: dict):
            user = identity.resolve_from_jwt(token)
            return {"user": user.model_dump()}

        # Direct instantiation
        from infrastructure.services import get_settings
        from infrastructure.identity import IdentityService

        settings = get_settings()
        service = IdentityService(settings)
        user = service.resolve_from_slack("U12345")
    """

    def __init__(
        self,
        settings: "Settings",
        resolver: Optional["IdentityResolver"] = None,
        slack_client_manager: Optional["SlackClientManager"] = None,
    ):
        """Initialize identity service.

        Args:
            settings: Settings instance (required, passed from provider).
            resolver: Optional pre-configured IdentityResolver instance.
                     If not provided, creates one with slack_client_manager.
            slack_client_manager: Optional SlackClientManager for Slack identity resolution.
                                 Used only if resolver is not provided.
        """
        if resolver is None:
            # Import here to avoid circular dependency
            from infrastructure.identity.resolver import IdentityResolver

            # If slack_client_manager not provided, import it
            if slack_client_manager is None:
                from integrations.slack.client import SlackClientManager

                slack_client_manager = SlackClientManager

            resolver = IdentityResolver(slack_client_manager=slack_client_manager)

        self._resolver = resolver

    def resolve_from_slack(
        self, slack_user_id: str, slack_team_id: Optional[str] = None
    ) -> User:
        """Resolve Slack user ID to normalized identity.

        Args:
            slack_user_id: Slack user ID (e.g., 'U12345')
            slack_team_id: Optional Slack team/workspace ID

        Returns:
            User with resolved information from Slack

        Raises:
            ValueError: If Slack client not configured
            Exception: If Slack API call fails
        """
        return self._resolver.resolve_from_slack(slack_user_id, slack_team_id)

    def resolve_from_jwt(self, jwt_payload: Dict[str, Any]) -> User:
        """Resolve JWT token to normalized identity.

        Args:
            jwt_payload: Decoded JWT payload with standard claims

        Returns:
            User with resolved information from JWT claims
        """
        return self._resolver.resolve_from_jwt(jwt_payload)

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
        return self._resolver.resolve_from_webhook(webhook_payload, webhook_source)

    def resolve_system_identity(self) -> User:
        """Create system identity for internal operations.

        Returns:
            User with system identity
        """
        return self._resolver.resolve_system_identity()

    @property
    def resolver(self) -> "IdentityResolver":
        """Access underlying IdentityResolver instance.

        Provided for advanced use cases that need direct access
        to the IdentityResolver API.

        Returns:
            The underlying IdentityResolver instance
        """
        return self._resolver
