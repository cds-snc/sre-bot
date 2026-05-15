"""
Type aliases for FastAPI dependency injection.

Provides annotated type hints for common infrastructure dependencies.
"""

from typing import Annotated

from fastapi import Depends

from infrastructure.audit.protocol import AuditTrailService
from infrastructure.clients.aws import AWSClients
from infrastructure.clients.google_workspace import GoogleWorkspaceClients
from infrastructure.clients.maxmind import MaxMindClient
from infrastructure.configuration import AppSettings, Settings
from infrastructure.directory.provider import DirectoryProvider
from infrastructure.events.service import EventDispatcher
from infrastructure.i18n.service import TranslationService
from infrastructure.idempotency.protocol import IdempotencyService
from infrastructure.resilience.service import ResilienceService
from infrastructure.security.jwks import JWKSManager
from infrastructure.services.providers import (
    get_app_settings,
    get_audit_trail_service,
    get_aws_clients,
    get_directory_provider,
    get_event_dispatcher,
    get_google_workspace_clients,
    get_idempotency_service,
    get_jwks_manager,
    get_maxmind_client,
    get_resilience_service,
    get_settings,
    get_storage_service,
    get_translation_service,
)
from infrastructure.storage.protocol import StorageService

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]
AppSettingsDep = Annotated[AppSettings, Depends(get_app_settings)]

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

# MaxMind client dependency - provides IP geolocation operations
# Usage: maxmind.geolocate(ip_address="8.8.8.8")
# For types and data classes: from infrastructure.clients.maxmind import GeoLocationData
MaxMindClientDep = Annotated[MaxMindClient, Depends(get_maxmind_client)]

# Events dispatcher dependency
EventDispatcherDep = Annotated[EventDispatcher, Depends(get_event_dispatcher)]

# Translation service dependency
TranslationServiceDep = Annotated[TranslationService, Depends(get_translation_service)]

# Idempotency service dependency
IdempotencyServiceDep = Annotated[IdempotencyService, Depends(get_idempotency_service)]

# Resilience service dependency
ResilienceServiceDep = Annotated[ResilienceService, Depends(get_resilience_service)]

# Storage service dependency
StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]

# Audit trail service dependency
AuditTrailServiceDep = Annotated[AuditTrailService, Depends(get_audit_trail_service)]


# Directory provider dependency — IDP-agnostic group membership and listing
DirectoryProviderDep = Annotated[DirectoryProvider, Depends(get_directory_provider)]

__all__ = [
    "SettingsDep",
    "AppSettingsDep",
    "JWKSManagerDep",
    "AWSClientsDep",
    "GoogleWorkspaceClientsDep",
    "EventDispatcherDep",
    "TranslationServiceDep",
    "IdempotencyServiceDep",
    "ResilienceServiceDep",
    "StorageServiceDep",
    "DirectoryProviderDep",
]
