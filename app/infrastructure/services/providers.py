"""
Factory functions for dependency injection.

Provides application-scoped singleton providers for core infrastructure services.
"""

from functools import lru_cache
from typing import Annotated, Optional
from fastapi import Depends
from infrastructure.configuration import Settings
from infrastructure.identity import IdentityResolver
from integrations.slack.client import SlackClientManager
from infrastructure.security.jwks import JWKSManager
from infrastructure.clients.aws import AWSClientFactory, AWSHelpers


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


@lru_cache
def get_aws_client(
    settings: Optional[Annotated[Settings, Depends(get_settings)]] = None,
) -> AWSClientFactory:
    """Provider for AWS client factory with all service operations.

    Returns a fully-configured AWSClientFactory instance with region, role,
    and endpoint settings from the application settings.

    Args:
        settings: Application settings (injected)

    Returns:
        AWSClientFactory: Configured factory instance for all AWS service calls

    Usage:
        @router.post("/groups")
        def create_group(aws: AWSClientDep):
            result = aws.create_account_assignment(...)
            if result.is_success:
                return {"assignment_id": result.data}
    """
    if settings is None:
        settings = get_settings()
    return AWSClientFactory(
        aws_region=settings.aws.AWS_REGION,
        endpoint_url=getattr(settings.aws, "ENDPOINT_URL", None),
        role_arn=getattr(settings.aws, "ROLE_ARN", None),
        default_identity_store_id=getattr(settings.aws, "INSTANCE_ID", None),
        treat_conflict_as_success=getattr(
            settings.aws, "TREAT_CONFLICT_AS_SUCCESS", False
        ),
    )


@lru_cache
def get_aws_helpers(
    aws: Annotated[AWSClientFactory, Depends(get_aws_client)],
) -> AWSHelpers:
    """Provider for AWS helpers factory.

    Returns:
        AWSHelpers: Helper operations wrapper configured with the AWS client factory

    Usage:
        @router.get("/groups")
        def list_groups(helpers: AWSHelpersDep):
            result = helpers.list_groups_with_memberships(store_id)
    """
    return AWSHelpers(aws)
