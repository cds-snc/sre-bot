"""
Factory functions for dependency injection.

Provides application-scoped singleton providers for core infrastructure services.
"""

from functools import lru_cache
from infrastructure.configuration import Settings
from infrastructure.identity import IdentityResolver
from integrations.slack.client import SlackClientManager
from infrastructure.security.jwks import JWKSManager


@lru_cache
def get_settings() -> Settings:
    """
    Get application-scoped settings singleton.

    Returns:
        Settings: Cached settings instance loaded from environment.

    Usage:
        @app.get("/config")
        def get_config(settings: SettingsDep) -> dict:
            return settings.dict()
    """
    return Settings()


@lru_cache
def get_identity_resolver() -> IdentityResolver:
    """
    Get application-scoped identity resolver singleton.

    Returns:
        IdentityResolver: Cached identity resolver instance with injected dependencies.

    Usage:
        @router.post("/identity")
        def resolve_user(resolver: IdentityResolverDep) -> User:
            return resolver.resolve_from_jwt(jwt_payload)
    """
    return IdentityResolver(slack_client_manager=SlackClientManager)


@lru_cache
def get_jwks_manager() -> JWKSManager:
    """
    Get application-scoped JWKSManager singleton.

    Returns:
        JWKSManager: Cached JWKS manager configured from application settings.
    """
    settings = get_settings()
    issuer_config = settings.server.ISSUER_CONFIG
    if not issuer_config:
        raise ValueError("ISSUER_CONFIG is not configured in settings.server")
    return JWKSManager(issuer_config=issuer_config)
