"""Geolocate package - IP geolocation via MaxMind."""

from infrastructure.services import hookimpl
from packages.geolocate.routes import router as geolocate_router
from packages.geolocate.schemas import GeolocateRequest, GeolocateResponse
from packages.geolocate.service import geolocate_ip
from packages.geolocate.platforms import slack, teams


@hookimpl
def register_slack_commands(provider):
    """Register geolocate Slack commands.

    Args:
        provider: Slack platform provider instance.
    """
    slack.register_commands(provider)


@hookimpl
def register_teams_commands(provider):
    """Register geolocate Teams commands (experimental).

    Args:
        provider: Teams platform provider instance.
    """
    teams.register_commands(provider)


# Discord provider not implemented - out of scope


__all__ = [
    "geolocate_router",
    "geolocate_ip",
    "GeolocateRequest",
    "GeolocateResponse",
]
