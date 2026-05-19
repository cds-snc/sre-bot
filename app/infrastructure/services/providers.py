"""
Factory functions for dependency injection.

Provides application-scoped singleton providers for core infrastructure services.
"""

from functools import lru_cache
from typing import Any

from infrastructure.audit.protocol import AuditTrailService
from infrastructure.audit.service import DynamoDBAuditTrailService
from infrastructure.clients.aws import AWSClients
from infrastructure.clients.google_workspace import GoogleWorkspaceClients
from infrastructure.clients.maxmind import MaxMindClient
from infrastructure.configuration import Settings
from infrastructure.configuration.app import (
    AppSettings,
)
from infrastructure.configuration.app import (
    get_app_settings as _get_app_settings,
)
from infrastructure.configuration.infrastructure.directory import get_directory_settings
from infrastructure.configuration.infrastructure.idempotency import (
    get_idempotency_settings,
)
from infrastructure.configuration.infrastructure.retry import get_retry_settings
from infrastructure.configuration.integrations.aws import get_aws_settings
from infrastructure.configuration.integrations.google import (
    get_google_workspace_settings,
)
from infrastructure.configuration.integrations.maxmind import get_maxmind_settings
from infrastructure.directory.factory import build_google_directory_provider
from infrastructure.directory.provider import DirectoryProvider
from infrastructure.events.service import EventDispatcher
from infrastructure.i18n.models import Locale, TranslationKey
from infrastructure.i18n.service import TranslationService
from infrastructure.idempotency.dynamodb import DynamoDBCache
from infrastructure.idempotency.protocol import IdempotencyService
from infrastructure.idempotency.service import DynamoDBIdempotencyService
from infrastructure.resilience.service import ResilienceService
from infrastructure.storage.protocol import StorageService
from infrastructure.storage.service import DynamoDBStorageService


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Deprecated: get application-scoped settings singleton.

    This is the single source of truth for settings across the entire application.
    The @lru_cache decorator ensures only ONE instance is created per process,
    even if called from multiple packages.

    Infrastructure packages should use this directly to ensure singleton consistency:
        from infrastructure.services.providers import get_settings
        settings = get_settings()

    Application code should use the DI type alias for testability:
        from infrastructure.services import SettingsDep
        @router.get("/config")
        def get_config(settings: SettingsDep):
            return settings.dict()

    Returns:
        Settings: Cached settings instance loaded from environment.

    Note:
        Deprecated. Prefer domain-specific settings providers
        (for example get_slack_settings(), get_server_settings()).
    """
    return Settings()


def get_app_settings() -> AppSettings:
    """Get application-scoped app settings singleton."""
    return _get_app_settings()


@lru_cache(maxsize=1)
def get_aws_clients() -> AWSClients:
    """Provider for AWS clients facade with all service operations.

    Returns a fully-configured AWSClients facade instance with region and endpoint
    settings from application configuration. The facade composes per-service clients
    (DynamoDB, IdentityStore, Organizations, SsoAdmin) with a shared SessionProvider.

    Credentials (temporary creds from assume_role or default providers) are created
    per API call, so caching this facade is safe—it doesn't hold stale credentials.

    Returns:
        AWSClients: Configured facade instance for all AWS service calls

    Usage:
        @router.post("/items")
        def create_item(aws: AWSClientsDep):
            result = aws.dynamodb.put_item("my_table", Item={...})
            if result.is_success:
                return {"item_id": result.data}

            result = aws.identitystore.get_user(store_id, user_id)
            if result.is_success:
                return {"user": result.data}
    """
    return AWSClients(aws_settings=get_aws_settings())


@lru_cache(maxsize=1)
def get_google_workspace_clients() -> GoogleWorkspaceClients:
    """Provider for Google Workspace clients facade with all service operations.

    Returns a fully-configured GoogleWorkspaceClients facade instance with credentials
    and workspace settings from application configuration. The facade composes per-service
    clients (Directory, Drive, Docs, Sheets, Gmail) with a shared SessionProvider.

    Credentials are loaded from the service account key file specified in settings.
    The facade holds a single SessionProvider instance that manages authentication
    and delegation across all Google Workspace services.

    Returns:
        GoogleWorkspaceClients: Configured facade instance for all Google Workspace API calls.

    Usage:
        # FastAPI route handlers (dependency injection)
        from infrastructure.services import GoogleWorkspaceClientsDep

        @router.get("/groups")
        def list_groups(google_clients: GoogleWorkspaceClientsDep):
            result = google_clients.directory.list_groups()
            if result.is_success:
                return {"groups": result.data}

        # Application code (jobs, modules, utils)
        from infrastructure.services import get_google_workspace_clients

        def sync_groups():
            google_clients = get_google_workspace_clients()
            result = google_clients.directory.list_groups()
            return result

    Note:
        For Google Workspace types and data classes, import from:
        infrastructure.clients.google_workspace
    """
    return GoogleWorkspaceClients(google_settings=get_google_workspace_settings())


@lru_cache(maxsize=1)
def get_maxmind_client() -> MaxMindClient:
    """Provider for MaxMind GeoIP2 client.

    Returns a fully-configured MaxMindClient instance with database path
    from application configuration.

    Returns:
        MaxMindClient: Configured client instance for geolocation operations

    Usage:
        # FastAPI route handlers (dependency injection)
        from infrastructure.services import MaxMindClientDep

        @router.get("/geolocate")
        def geolocate(ip: str, maxmind: MaxMindClientDep):
            result = maxmind.geolocate(ip_address=ip)
            if result.is_success:
                return result.data

        # Application code (jobs, modules, utils)
        from infrastructure.services import get_maxmind_client

        def check_ip_location(ip: str):
            maxmind = get_maxmind_client()
            result = maxmind.geolocate(ip_address=ip)
            return result

    Note:
        For MaxMind types and data classes, import from:
        infrastructure.clients.maxmind
    """
    return MaxMindClient(maxmind_settings=get_maxmind_settings())


@lru_cache(maxsize=1)
def get_event_dispatcher() -> EventDispatcher:
    """Get application-scoped event dispatcher singleton.

    Returns an EventDispatcher instance for dependency injection and testing.

    Usage:
        from infrastructure.services import EventDispatcherDep

        @router.post("/action")
        def perform_action(dispatcher: EventDispatcherDep):
            event = Event(event_type="action.performed")
            dispatcher.dispatch(event)

    Returns:
        EventDispatcher: Cached event dispatcher instance
    """
    return EventDispatcher()


@lru_cache(maxsize=1)
def get_translation_service() -> TranslationService:
    """Get application-scoped translation service singleton.

    Returns a TranslationService instance with pre-configured Translator
    that has all YAML catalogs loaded from the default locales directory.

    Usage:
        from infrastructure.services import TranslationServiceDep

        @router.get("/message")
        def get_message(translation: TranslationServiceDep, locale: str):
            key = TranslationKey.from_string("groups.create.success")
            return translation.translate(key, Locale.from_string(locale))

    Returns:
        TranslationService: Cached translation service instance
    """
    # TranslationService doesn't need settings - uses factory internally
    return TranslationService()


def t(key: str, locale: str, fallback: str = "", **variables: Any) -> str:
    """Translate a key safely, designed for use in command handlers and feature packages.

    Wraps the application-scoped translation singleton with a fallback so callers
    never have to guard against uninitialized state or missing keys.

    Args:
        key: Dot-separated translation key (e.g. "geolocate.result.city_label").
        locale: Locale string such as "en-US" or "fr-FR".
        fallback: Returned as-is when the key is missing or the service is not yet ready.
        **variables: Interpolation variables for ``{{variable}}`` placeholders.

    Returns:
        Translated and interpolated string, or *fallback* on any error.
    """
    try:
        return get_translation_service().translate(
            key=TranslationKey.from_string(key),
            locale=Locale.from_string(locale),
            variables=variables or None,
        )
    except Exception:
        return fallback


@lru_cache(maxsize=1)
def get_idempotency_service() -> IdempotencyService:
    """Get application-scoped idempotency service singleton.

    Returns an IdempotencyService instance with DynamoDB-backed cache
    for distributed idempotency across ECS tasks.

    Usage:
        from infrastructure.services import IdempotencyServiceDep

        @router.post("/action")
        def perform_action(
            idempotency: IdempotencyServiceDep,
            request_id: str
        ):
            cached = idempotency.get(request_id)
            if cached:
                return cached

            result = process_request()
            idempotency.set(request_id, result, ttl_seconds=3600)
            return result

    Returns:
        IdempotencyService: Cached idempotency service instance
    """
    return DynamoDBIdempotencyService(
        cache=DynamoDBCache(idempotency_settings=get_idempotency_settings())
    )


@lru_cache(maxsize=1)
def get_resilience_service() -> ResilienceService:
    """Get application-scoped resilience service singleton.

    Returns a ResilienceService instance that provides unified access to
    circuit breakers and retry stores for fault-tolerant operations.

    Usage:
        from infrastructure.services import ResilienceServiceDep

        @router.get("/external-call")
        def make_call(resilience: ResilienceServiceDep):
            cb = resilience.get_or_create_circuit_breaker("external_api")
            try:
                return cb.call(external_api_function)
            except CircuitBreakerOpenError:
                return {"error": "Service unavailable"}

    Returns:
        ResilienceService: Cached resilience service instance
    """
    return ResilienceService(retry_settings=get_retry_settings())


@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    """Get application-scoped storage service singleton.

    Returns a ``StorageService`` backed by ``DynamoDBClient`` from the AWS
    clients facade.  Feature packages should define typed repository classes
    that take ``StorageService`` as a constructor argument instead of calling
    ``DynamoDBClient`` directly.

    Usage::

        from infrastructure.services import StorageServiceDep

        class SyncRunRepository:
            def __init__(self, storage: StorageServiceDep) -> None:
                self._storage = storage

    Returns:
        StorageService: Cached storage service instance.
    """
    aws = get_aws_clients()
    return DynamoDBStorageService(dynamodb=aws.dynamodb)


@lru_cache(maxsize=1)
def get_audit_trail_service() -> AuditTrailService:
    """Get application-scoped audit trail service singleton.

    Returns an AuditTrailService Protocol instance for writing and querying audit
    events. The implementation uses DynamoDB, but can be swapped for alternative
    audit backends that satisfy the Protocol.

    Usage:
        from infrastructure.services import AuditTrailServiceDep

        @router.post("/audit/write")
        def write_audit(
            audit_trail: AuditTrailServiceDep,
            event: AuditEvent
        ):
            success = audit_trail.write_audit_event(event)
            return {"written": success}

    Returns:
        AuditTrailService: Cached audit trail service instance (implements Protocol)
    """
    storage = get_storage_service()
    return DynamoDBAuditTrailService(storage=storage)


@lru_cache(maxsize=1)
def get_directory_provider() -> DirectoryProvider:
    """Get application-scoped directory provider singleton.

    Returns a DirectoryProvider instance backed by the IDP configured in
    settings.directory.provider.  Default is Google Workspace.

    Credentials and client facades are obtained from the centralised
    infrastructure.services singletons and injected into the provider via the
    factory — this function is the single point that knows about both.

    Returns:
        DirectoryProvider: Cached provider instance for directory operations.

    Usage:
        # FastAPI route handlers (dependency injection)
        from infrastructure.services import DirectoryProviderDep

        @router.get("/membership")
        def check_membership(
            directory: DirectoryProviderDep,
            group_key: str,
            user_email: str,
        ):
            result = directory.check_membership(group_key, user_email)
            if result.is_success:
                return result.data

        # Application code (jobs, services)
        from infrastructure.services import get_directory_provider

        def sync_access():
            directory = get_directory_provider()
            result = directory.get_group_members("sg-ops@example.com")
            return result
    """
    directory_settings = get_directory_settings()
    provider_key = directory_settings.provider
    if provider_key == "google":
        return build_google_directory_provider(
            google_clients=get_google_workspace_clients(),
            directory_settings=directory_settings,
        )
    raise ValueError(f"Unsupported directory provider: {provider_key!r}")
