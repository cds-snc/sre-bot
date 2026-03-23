"""Access Sync package entry point.

Registers Slack platform commands via hookimpl and subscribes to the
access_request_approved domain event so approved access requests
trigger an immediate on-demand sync.

Exports the FastAPI router for registration in the main application.
"""

from infrastructure.events import register_event_handler
from infrastructure.services import hookimpl
from packages.access_sync.platforms import slack
from packages.access_sync.providers import get_user_sync_service
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
def register_routes(app):
    """Register geolocate HTTP routes.

    Args:
        app: FastAPI application instance.
    """
    app.include_router(access_sync_router)


__all__ = ["access_sync_router"]
