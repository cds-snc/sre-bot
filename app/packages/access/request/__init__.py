"""Access Requests package entry point.

Registers HTTP routes and subscribes to Access Sync result events so that
approved requests are advanced to ``completed`` or ``failed`` once the sync
provider reports back.

Slack command and interaction registration are deferred to a later iteration
pending a ``register_slack_interactions(bot)`` hookspec addition.
"""

from infrastructure.events import register_event_handler
from infrastructure.services import hookimpl
from packages.access.common.events import SYNC_COMPLETED, SYNC_FAILED
from packages.access.request.providers import (
    get_access_request_service,
    get_access_request_settings,
)
from packages.access.request.transport.routes import router as access_requests_router


@hookimpl
def register_routes(app) -> None:
    """Register Access Requests HTTP routes under /api/v1."""
    app.include_router(access_requests_router, prefix="/api/v1")


@register_event_handler(SYNC_COMPLETED)
def on_sync_completed(event) -> None:
    """Advance the originating access request to 'completed' after a successful sync."""
    get_access_request_service().advance_from_sync_result(event)


@register_event_handler(SYNC_FAILED)
def on_sync_failed(event) -> None:
    """Advance the originating access request to 'failed' after a sync failure."""
    get_access_request_service().advance_from_sync_result(event)


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

    try:
        get_access_request_service()
        logger.info("access_requests_providers_warmed")
    except Exception as exc:
        logger.error(
            "access_requests_provider_warmup_failed",
            error=str(exc),
            hint=(
                "Check ACCESS_CONFIG_SOURCE / ACCESS_CONFIG_REF "
                "and ACCESS_REQUESTS_* env vars."
            ),
        )


__all__ = ["access_requests_router"]
