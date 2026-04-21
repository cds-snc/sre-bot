"""Access Sync package entry point.

Registers Slack platform commands via hookimpl and subscribes to the
access_request_approved domain event so approved access requests
trigger an immediate on-demand sync.

Exports the FastAPI router for registration in the main application.
"""

from pathlib import Path

from infrastructure.events import register_event_handler
from infrastructure.i18n.resources import I18nResourceSpec
from infrastructure.services import hookimpl
from packages.access.common.events import REQUEST_APPROVED
from packages.access.sync.transport import slack
from packages.access.sync.providers import (
    get_access_sync_coordinator,
    get_access_sync_settings,
)
from packages.access.sync.transport.routes import router as access_sync_router


@hookimpl
def register_slack_commands(provider) -> None:
    """Register access-sync Slack commands."""
    slack.register_commands(provider)


@register_event_handler(REQUEST_APPROVED)
def on_access_request_approved(event) -> None:
    """Trigger on-demand sync when an access request is approved."""
    get_access_sync_coordinator().sync_user(
        user_email=event.user_email,
        platform=event.metadata.get("platform", ""),
        request_id=str(getattr(event, "correlation_id", "")),
    )


@hookimpl
def startup_warmup(logger) -> None:
    """Log effective Access Sync settings at startup.

    Also eagerly initializes the coordinator and all providers when the feature
    is enabled, so the first sync request is not delayed by config loading,
    adapter construction, and directory-provider wiring. Failures are logged
    with actionable hints but do not crash the process.
    """
    settings = get_access_sync_settings()
    logger.info(
        "access_sync_settings_loaded",
        enabled=settings.enabled,
        reconciliation_enabled=settings.reconciliation_enabled,
        reconciliation_schedule=settings.reconciliation_schedule,
    )
    if not settings.enabled:
        logger.warning(
            "access_sync_disabled",
            hint="Set ACCESS_SYNC_ENABLED=true to enable the feature.",
        )
        return

    try:
        get_access_sync_coordinator()
        logger.info("access_sync_providers_warmed")
    except Exception as exc:
        logger.error(
            "access_sync_provider_warmup_failed",
            error=str(exc),
            hint="Check ACCESS_CONFIG_SOURCE and ACCESS_CONFIG_REF.",
        )


@hookimpl
def register_routes(app):
    """Register access sync HTTP routes under /api/v1."""
    app.include_router(access_sync_router, prefix="/api/v1")


@hookimpl
def register_i18n_resources(registry) -> None:
    """Register access sync translation resource locations."""
    package_root = Path(__file__).parent
    locales_path = package_root / "locales"

    registry.register(
        I18nResourceSpec(
            owner="packages.access.sync",
            path=str(locales_path),
            required=False,
            format="yaml",
            domain="access_sync",
        )
    )


__all__ = ["access_sync_router"]
