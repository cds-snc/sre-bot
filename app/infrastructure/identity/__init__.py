"""User identity resolution services.

This package provides centralized identity resolution across platforms
(Slack, JWT, webhooks, system). All services use dependency injection
and return normalized User models.

Usage:
    from infrastructure.identity import IdentityResolver, User, IdentitySource
    from infrastructure.services import IdentityResolverDep

    # Via dependency injection (recommended for FastAPI routes)
    @router.post("/process")
    def process(user: IdentityResolverDep):
        slack_user = user.resolve_from_slack("U123ABC")

    # Direct instantiation (for tests or non-route code)
    resolver = IdentityResolver(slack_client_manager=client_manager)
    user = resolver.resolve_from_slack("U123ABC")
"""

from infrastructure.identity.models import IdentitySource, SlackUser, User
from infrastructure.identity.resolver import IdentityResolver

__all__ = ["IdentityResolver", "User", "SlackUser", "IdentitySource"]
