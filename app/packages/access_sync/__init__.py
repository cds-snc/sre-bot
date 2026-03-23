"""Access Sync package entry point.

Registers Slack platform commands via hookimpl and subscribes to the
access_request_approved domain event so approved access requests
trigger an immediate on-demand sync.

Exports the FastAPI router for registration in the main application.
"""

from infrastructure.events import register_event_handler
from infrastructure.services import hookimpl
from packages.access_sync.platforms import slack
from packages.access_sync.providers import (
    get_access_sync_settings,
    get_user_sync_service,
)
from packages.access_sync.routes import router as access_sync_router


@hookimpl
def register_slack_commands(provider) -> None:
    """Register access-sync Slack commands."""
    slack.register_commands(provider)


@register_event_handler("access_request_approved")
def on_access_request_approved(event) -> None:
    """Trigger on-demand sync when an access request is approved."""
    get_user_sync_service().sync_user(
        user_email=event.user_email,
        platform=event.metadata.get("platform", ""),
        request_id=str(getattr(event, "correlation_id", "")),
    )


@hookimpl
def startup_warmup(logger) -> None:
    """Log effective Access Sync settings at startup."""
    settings = get_access_sync_settings()
    logger.info(
        "access_sync_settings_loaded",
        enabled=settings.enabled,
        config_source=settings.config_source,
        config_ref=settings.config_ref,
        reconciliation_enabled=settings.reconciliation_enabled,
        reconciliation_schedule=settings.reconciliation_schedule,
    )
    if not settings.enabled:
        logger.warning(
            "access_sync_disabled",
            hint="Set ACCESS_SYNC_ENABLED=true to enable the feature.",
        )


@hookimpl
def register_routes(app):
    """Register access sync HTTP routes.

    Args:
        app: FastAPI application instance.
    """
    app.include_router(access_sync_router)


__all__ = ["access_sync_router"]
