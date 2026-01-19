"""MaxMind GeoIP2 client for infrastructure layer.

Public API (Package Level):
- MaxMindClient: Client for GeoIP2 database operations
- GeoLocationData: Dataclass for geolocation results

Note: Application code should import from infrastructure.services, not directly from this package.

Developer Usage (Recommended):
    from infrastructure.services import MaxMindClientDep

    @router.get("/geolocate")
    def geolocate(ip: str, maxmind: MaxMindClientDep):
        result = maxmind.geolocate(ip_address=ip)
        if result.is_success:
            return result.data
"""

from infrastructure.clients.maxmind.client import GeoLocationData, MaxMindClient

__all__ = [
    "MaxMindClient",
    "GeoLocationData",
]
