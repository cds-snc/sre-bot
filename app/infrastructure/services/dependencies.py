"""
Type aliases for FastAPI dependency injection.

Provides annotated type hints for common infrastructure dependencies.
"""

from typing import Annotated
from fastapi import Depends
from infrastructure.configuration import Settings
from infrastructure.identity.service import IdentityService
from infrastructure.security.jwks import JWKSManager
from infrastructure.clients.aws import AWSClients
from infrastructure.clients.google_workspace import GoogleWorkspaceClients
from infrastructure.events.service import EventDispatcher
from infrastructure.i18n.service import TranslationService
from infrastructure.idempotency.service import IdempotencyService
from infrastructure.resilience.service import ResilienceService
from infrastructure.notifications.service import NotificationService
from infrastructure.commands.service import CommandService
from infrastructure.persistence.service import PersistenceService
from infrastructure.services.providers import (
    get_settings,
    get_identity_service,
    get_jwks_manager,
    get_aws_clients,
    get_google_workspace_clients,
    get_event_dispatcher,
    get_translation_service,
    get_idempotency_service,
    get_resilience_service,
    get_notification_service,
    get_command_service,
    get_persistence_service,
)

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Identity service dependency
IdentityServiceDep = Annotated[IdentityService, Depends(get_identity_service)]

# JWKS manager dependency
JWKSManagerDep = Annotated[JWKSManager, Depends(get_jwks_manager)]

# AWS clients facade dependency - provides attribute-based access to all AWS services
# Usage: aws.dynamodb.get_item(...), aws.identitystore.list_users(...), etc.
AWSClientsDep = Annotated[AWSClients, Depends(get_aws_clients)]

# Google Workspace clients facade dependency - provides attribute-based access to all Google services
# Usage: google.directory.list_groups(), google.drive.create_file(...), etc.
# For types and data classes: from infrastructure.clients.google_workspace import ...
GoogleWorkspaceClientsDep = Annotated[
    GoogleWorkspaceClients, Depends(get_google_workspace_clients)
]

# Events dispatcher dependency
EventDispatcherDep = Annotated[EventDispatcher, Depends(get_event_dispatcher)]

# Translation service dependency
TranslationServiceDep = Annotated[TranslationService, Depends(get_translation_service)]

# Idempotency service dependency
IdempotencyServiceDep = Annotated[IdempotencyService, Depends(get_idempotency_service)]

# Resilience service dependency
ResilienceServiceDep = Annotated[ResilienceService, Depends(get_resilience_service)]

# Notification service dependency
NotificationServiceDep = Annotated[
    NotificationService, Depends(get_notification_service)
]

# Command service dependency
CommandServiceDep = Annotated[CommandService, Depends(get_command_service)]

# Persistence service dependency
PersistenceServiceDep = Annotated[PersistenceService, Depends(get_persistence_service)]

__all__ = [
    "SettingsDep",
    "IdentityServiceDep",
    "JWKSManagerDep",
    "AWSClientsDep",
    "GoogleWorkspaceClientsDep",
    "EventDispatcherDep",
    "TranslationServiceDep",
    "IdempotencyServiceDep",
    "ResilienceServiceDep",
    "NotificationServiceDep",
    "CommandServiceDep",
    "PersistenceServiceDep",
]
