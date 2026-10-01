"""Geolocate package - IP geolocation via MaxMind."""

from pathlib import Path

from contracts.i18n.resources import I18nResourceRegistrar, I18nResourceSpec
from contracts.slack.registrar import SlackCommandRegistrar
from infrastructure.plugins import hookimpl
from packages.geolocate.platforms import slack
from packages.geolocate.routes import router as geolocate_router
from packages.geolocate.schemas import GeolocateRequest, GeolocateResponse
from packages.geolocate.service import geolocate_ip


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register geolocate Slack commands.

    Args:
        registrar: Slack command registrar.
    """
    slack.register_commands(registrar)


@hookimpl
def register_routes(app):
    """Register geolocate HTTP routes.

    Args:
        app: FastAPI application instance.
    """
    app.include_router(geolocate_router)


@hookimpl
def register_i18n_resources(registry: I18nResourceRegistrar) -> None:
    """Register geolocate translation resource locations.

    Args:
        registry: Registrar for translation resource specifications.
    """
    package_root = Path(__file__).parent
    locales_path = package_root / "locales"

    registry.register(
        I18nResourceSpec(
            owner="packages.geolocate",
            path=str(locales_path),
            required=False,
            format="yaml",
            domain="geolocate",
        )
    )


# Discord provider not implemented - out of scope


__all__ = [
    "geolocate_router",
    "geolocate_ip",
    "GeolocateRequest",
    "GeolocateResponse",
]
