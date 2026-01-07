"""
Type aliases for FastAPI dependency injection.

Provides annotated type hints for common infrastructure dependencies.
"""

from typing import Annotated
from fastapi import Depends
from infrastructure.configuration import Settings
from infrastructure.identity import IdentityResolver
from infrastructure.security.jwks import JWKSManager
from infrastructure.clients.aws import AWSClients
from infrastructure.events.service import EventDispatcher
from infrastructure.i18n.service import TranslationService
from infrastructure.idempotency.service import IdempotencyService
from infrastructure.resilience.service import ResilienceService
from infrastructure.services.providers import (
    get_settings,
    get_identity_resolver,
    get_jwks_manager,
    get_aws_clients,
    get_event_dispatcher,
    get_translation_service,
    get_idempotency_service,
    get_resilience_service,
)

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Identity resolver dependency
IdentityResolverDep = Annotated[IdentityResolver, Depends(get_identity_resolver)]

# JWKS manager dependency
JWKSManagerDep = Annotated[JWKSManager, Depends(get_jwks_manager)]

# AWS clients facade dependency - provides attribute-based access to all AWS services
# Usage: aws.dynamodb.get_item(...), aws.identitystore.list_users(...), etc.
AWSClientsDep = Annotated[AWSClients, Depends(get_aws_clients)]

# Events dispatcher dependency
EventDispatcherDep = Annotated[EventDispatcher, Depends(get_event_dispatcher)]

# Translation service dependency
TranslationServiceDep = Annotated[TranslationService, Depends(get_translation_service)]

# Idempotency service dependency
IdempotencyServiceDep = Annotated[IdempotencyService, Depends(get_idempotency_service)]

# Resilience service dependency
ResilienceServiceDep = Annotated[ResilienceService, Depends(get_resilience_service)]

__all__ = [
    "SettingsDep",
    "IdentityResolverDep",
    "JWKSManagerDep",
    "AWSClientsDep",
    "EventDispatcherDep",
    "TranslationServiceDep",
    "IdempotencyServiceDep",
    "ResilienceServiceDep",
]
