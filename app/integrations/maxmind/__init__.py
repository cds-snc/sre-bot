"""MaxMind integration package."""

from .client import GeoLocationData, MaxMindClient, classify_maxmind_error, get_maxmind_client

__all__ = [
    "MaxMindClient",
    "GeoLocationData",
    "get_maxmind_client",
    "classify_maxmind_error",
]
