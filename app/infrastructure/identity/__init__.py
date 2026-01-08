"""User identity resolution services.

This package provides centralized identity resolution across platforms
(Slack, JWT, webhooks, system). All services use dependency injection
and return normalized User models.

Usage (Recommended - Service Pattern with DI):
    # Via FastAPI dependency injection
    from infrastructure.services import IdentityServiceDep

    @router.post("/identity/slack")
    def resolve_slack_user(identity: IdentityServiceDep, slack_user_id: str):
        user = identity.resolve_from_slack(slack_user_id)
        return {"user": user.model_dump()}

    @router.post("/identity/jwt")
    def resolve_jwt_user(identity: IdentityServiceDep, jwt_payload: dict):
        user = identity.resolve_from_jwt(jwt_payload)
        return {"user": user.model_dump()}

    # Direct instantiation (non-route code)
    from infrastructure.services import get_settings
    from infrastructure.identity import IdentityService

    settings = get_settings()
    identity = IdentityService(settings)
    user = identity.resolve_from_slack("U12345")

Legacy Usage (Direct Resolver - Deprecated):
    # This pattern is deprecated - use IdentityService instead
    from infrastructure.identity import IdentityResolver
    from integrations.slack.client import SlackClientManager

    resolver = IdentityResolver(slack_client_manager=SlackClientManager)
    user = resolver.resolve_from_slack("U12345")
"""

from infrastructure.identity.models import IdentitySource, SlackUser, User
from infrastructure.identity.resolver import IdentityResolver
from infrastructure.identity.service import IdentityService

__all__ = [
    "IdentityService",
    "IdentityResolver",
    "User",
    "SlackUser",
    "IdentitySource",
]
