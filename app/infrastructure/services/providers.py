"""
Factory functions for dependency injection.

Provides application-scoped singleton providers for core infrastructure services.
"""

from functools import lru_cache
from typing import Any

from infrastructure.clients.maxmind import MaxMindClient
from infrastructure.configuration import Settings
from infrastructure.configuration.app import (
    AppSettings,
)
from infrastructure.configuration.app import (
    get_app_settings as _get_app_settings,
)
from infrastructure.configuration.infrastructure.idempotency import (
    get_idempotency_settings,
)
from infrastructure.configuration.infrastructure.retry import get_retry_settings
from infrastructure.configuration.integrations.maxmind import get_maxmind_settings
from infrastructure.events.service import EventDispatcher
from infrastructure.i18n.models import Locale, TranslationKey
from infrastructure.i18n.service import TranslationService
from infrastructure.idempotency.dynamodb import DynamoDBCache
from infrastructure.idempotency.protocol import IdempotencyService
from infrastructure.idempotency.service import DynamoDBIdempotencyService
from infrastructure.resilience.service import ResilienceService


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
