"""MaxMind GeoIP2 client for infrastructure layer.

Public API (Package Level):
- MaxMindClient: Client for GeoIP2 database operations
- GeoLocationData: Dataclass for geolocation results
"""

from infrastructure.clients.maxmind.client import (
    GeoLocationData,
    MaxMindClient,
    get_maxmind_client,
)

__all__ = [
    "MaxMindClient",
    "GeoLocationData",
    "get_maxmind_client",
]
