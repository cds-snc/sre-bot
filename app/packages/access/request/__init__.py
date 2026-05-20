"""Access Requests package entry point.

Registers HTTP routes and subscribes to Access Sync result events so that
approved requests are advanced to ``completed`` or ``failed`` once the sync
provider reports back.

Slack command and interaction registration are deferred to a later iteration
pending implementation of a ``register_slack_commands(provider)`` hookimpl
per ADR-0059 Standard 3.
"""

from infrastructure.events import get_event_dispatcher
from infrastructure.plugins import hookimpl
from packages.access.common.events import SYNC_COMPLETED, SYNC_FAILED
from packages.access.common.providers import get_access_runtime_config
from packages.access.request.interactions.http import router as access_requests_router
from packages.access.request.providers import (
    get_access_request_service,
    get_access_request_settings,
)


@hookimpl
def register_routes(app) -> None:
    """Register Access Requests HTTP routes under /api/v1."""
    app.include_router(access_requests_router, prefix="/api/v1")


def on_sync_completed(event) -> None:
    """Advance the originating access request to 'completed' after a successful sync."""
    get_access_request_service().advance_from_sync_result(event)


def on_sync_failed(event) -> None:
    """Advance the originating access request to 'failed' after a sync failure."""
    get_access_request_service().advance_from_sync_result(event)


def _register_sync_event_handlers() -> None:
    """Register sync result handlers once during startup warmup."""
    dispatcher = get_event_dispatcher()
    if dispatcher.get_handler_count(SYNC_COMPLETED) == 0:
        dispatcher.register_handler(SYNC_COMPLETED, on_sync_completed)
    if dispatcher.get_handler_count(SYNC_FAILED) == 0:
        dispatcher.register_handler(SYNC_FAILED, on_sync_failed)


@hookimpl
def startup_warmup(logger) -> None:
    """Log effective Access Requests settings and warm singletons at startup."""
    settings = get_access_request_settings()
    logger.info(
        "access_requests_settings_loaded",
        enabled=settings.enabled,
        manager_group_slug=settings.manager_group_slug,
        fallback_approver_slug=settings.fallback_approver_slug,
        min_approver_count=settings.min_approver_count,
        request_ttl_hours=settings.request_ttl_hours,
    )
    if not settings.enabled:
        logger.warning(
            "access_requests_disabled",
            hint="Set ACCESS_REQUESTS_ENABLED=true to enable the feature.",
        )
        return

    # Fail fast on misconfigured runtime config or provider wiring.
    get_access_runtime_config()
    _register_sync_event_handlers()
    get_access_request_service()
    logger.info("access_requests_providers_warmed")


__all__ = ["access_requests_router"]
