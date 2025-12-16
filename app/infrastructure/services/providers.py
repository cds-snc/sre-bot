"""
Factory functions for dependency injection.

Provides application-scoped singleton providers for core infrastructure services.
"""

from functools import lru_cache
from infrastructure.configuration import Settings
from infrastructure.identity import IdentityResolver
from integrations.slack.client import SlackClientManager
from infrastructure.security.jwks import JWKSManager
from infrastructure.clients.aws import (
    get_boto3_client as _get_boto3_client,
)
from infrastructure.clients.aws import dynamodb as dynamodb_client
from typing import Any, Dict, Optional


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
    service_name: str = "",
    session_config: Optional[Dict[str, Any]] = None,
    client_config: Optional[Dict[str, Any]] = None,
    role_arn: Optional[str] = None,
) -> Any:
    """Provider for creating a boto3 client for a given service.

    Note: This provider returns a boto3 client instance. Prefer higher-level
    wrappers (e.g., get_dynamodb_client) for typed OperationResult returns.
    """
    if not service_name:
        raise ValueError("service_name must be provided to get_aws_client")
    return _get_boto3_client(
        service_name,
        session_config=session_config,
        client_config=client_config,
        role_arn=role_arn,
    )


@lru_cache
def get_dynamodb_client() -> Any:
    """Provider that returns the DynamoDB client wrapper module.

    This returns the `dynamodb` module which exposes OperationResult-returning
    helper functions (get_item, put_item, query, etc.).
    """
    return dynamodb_client
