"""Access Sync package entry point.

Registers Slack platform commands via hookimpl and subscribes to the
access_request_approved domain event so approved access requests
trigger an immediate on-demand sync.

Exports the FastAPI router for registration in the main application.
"""

from pathlib import Path

from infrastructure.i18n.resources import I18nResourceSpec
from infrastructure.plugins import hookimpl
from infrastructure.services import get_event_dispatcher
from packages.access.common.events import REQUEST_APPROVED
from packages.access.common.providers import get_access_runtime_config
from packages.access.sync.interactions import slack
from packages.access.sync.interactions.http import router as access_sync_router
from packages.access.sync.providers import (
    get_access_sync_coordinator,
    get_access_sync_settings,
)


@hookimpl
def register_slack_commands(provider) -> None:
    """Register access-sync Slack commands."""
    slack.register_commands(provider)


def on_access_request_approved(event) -> None:
    """Trigger on-demand sync when an access request is approved."""
    get_access_sync_coordinator().sync_user(
        user_email=event.user_email,
        platform=event.metadata.get("platform", ""),
        request_id=str(getattr(event, "correlation_id", "")),
    )


def _register_request_handlers() -> None:
    """Register request-approved handler once during startup warmup."""
    dispatcher = get_event_dispatcher()
    if dispatcher.get_handler_count(REQUEST_APPROVED) == 0:
        dispatcher.register_handler(REQUEST_APPROVED, on_access_request_approved)


def _run_reconciliation_job() -> None:
    """Run full-platform Access Sync reconciliation."""
    coordinator = get_access_sync_coordinator()
    runtime_config = get_access_runtime_config()
    for platform in runtime_config.platforms:
        coordinator.sync_platform(platform=platform, dry_run=False)


@hookimpl
def startup_warmup(logger) -> None:
    """Log effective Access Sync settings at startup.

    Also eagerly initializes the coordinator and all providers when the feature
    is enabled, so the first sync request is not delayed by config loading,
    adapter construction, and directory-provider wiring.

    For enabled paths, startup failures are fatal and must propagate so
    misconfiguration is detected before traffic.
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

    # Validate runtime config and provider assembly before serving traffic.
    get_access_runtime_config()
    _register_request_handlers()
    get_access_sync_coordinator()
    logger.info("access_sync_providers_warmed")


@hookimpl
def register_routes(app):
    """Register access sync HTTP routes under /api/v1."""
    app.include_router(access_sync_router, prefix="/api/v1")


@hookimpl
def register_background_job(registry) -> None:
    """Register reconciliation schedule through the feature job registry."""
    settings = get_access_sync_settings()
    if not settings.enabled or not settings.reconciliation_enabled:
        return

    registry.register(
        job_name="access_sync_reconciliation",
        schedule=settings.reconciliation_schedule,
        job=_run_reconciliation_job,
    )


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
