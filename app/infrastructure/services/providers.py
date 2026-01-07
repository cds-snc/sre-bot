"""
Factory functions for dependency injection.

Provides application-scoped singleton providers for core infrastructure services.
"""

from functools import lru_cache

from infrastructure.configuration import Settings
from infrastructure.identity import IdentityResolver
from integrations.slack.client import SlackClientManager
from infrastructure.security.jwks import JWKSManager
from infrastructure.clients.aws import AWSClients
from infrastructure.i18n.service import TranslationService
from infrastructure.events.service import EventDispatcher
from infrastructure.idempotency.service import IdempotencyService
from infrastructure.resilience.service import ResilienceService


@lru_cache
def get_settings() -> Settings:
    """
    Get application-scoped settings singleton.

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
    settings = get_settings()
    return AWSClients(aws_settings=settings.aws)


@lru_cache
def get_event_dispatcher() -> EventDispatcher:
    """Get application-scoped event dispatcher singleton.

    Returns an EventDispatcher instance that wraps the module-level event
    functions for dependency injection and testing.

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


@lru_cache
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


@lru_cache
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
    settings = get_settings()
    return IdempotencyService(settings=settings)


@lru_cache
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
    settings = get_settings()
    return ResilienceService(settings=settings)
