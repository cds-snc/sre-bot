"""MaxMind GeoIP2 client for geolocation operations.

Provides type-safe access to MaxMind GeoIP2 database with consistent error handling
and OperationResult return types.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import geoip2.database
import structlog
from geoip2.errors import AddressNotFoundError, GeoIP2Error

from infrastructure.operations import OperationResult, OperationStatus

if TYPE_CHECKING:
    from infrastructure.configuration import Settings

logger = structlog.get_logger()


@dataclass
class GeoLocationData:
    """Geolocation data for an IP address."""

    country_code: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    postal_code: Optional[str] = None
    time_zone: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "country_code": self.country_code,
            "city": self.city,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "postal_code": self.postal_code,
            "time_zone": self.time_zone,
        }


class MaxMindClient:
    """Client for MaxMind GeoIP2 database operations.

    All methods return OperationResult for consistent error handling.

    Args:
        settings: Settings instance with maxmind.MAXMIND_DB_PATH
    """

    def __init__(self, settings: "Settings") -> None:
        self._db_path = settings.maxmind.MAXMIND_DB_PATH
        self._logger = logger.bind(component="maxmind_client")

    def geolocate(self, ip_address: str) -> OperationResult:
        """Geolocate an IP address using MaxMind GeoIP2 database.

        Args:
            ip_address: IPv4 or IPv6 address to geolocate

        Returns:
            OperationResult with GeoLocationData or error
        """
        log = self._logger.bind(ip_address=ip_address)
        log.debug("geolocating_ip")

        try:
            reader = geoip2.database.Reader(self._db_path)
            try:
                response = reader.city(ip_address)

                location = GeoLocationData(
                    country_code=response.country.iso_code,
                    city=response.city.name,
                    latitude=response.location.latitude,
                    longitude=response.location.longitude,
                    postal_code=response.postal.code,
                    time_zone=response.location.time_zone,
                )

                log.debug(
                    "geolocation_success",
                    country=location.country_code,
                    city=location.city,
                )
                return OperationResult.success(
                    data=location.to_dict(), message="IP geolocated successfully"
                )

            except AddressNotFoundError:
                log.warning("ip_not_found")
                return OperationResult(
                    status=OperationStatus.NOT_FOUND,
                    message=f"IP address not found in database: {ip_address}",
                    error_code="IP_NOT_FOUND",
                )

            except ValueError as e:
                log.warning("invalid_ip_format", error=str(e))
                return OperationResult.permanent_error(
                    message=f"Invalid IP address format: {ip_address}",
                    error_code="INVALID_IP_FORMAT",
                )

            except GeoIP2Error as e:
                log.error("geoip2_error", error=str(e))
                return OperationResult.transient_error(
                    message=f"GeoIP2 database error: {str(e)}",
                    error_code="GEOIP2_ERROR",
                )

            finally:
                reader.close()

        except (FileNotFoundError, IOError) as e:
            log.error("database_file_error", error=str(e), db_path=self._db_path)
            return OperationResult.transient_error(
                message=f"MaxMind database file error: {str(e)}",
                error_code="DB_FILE_ERROR",
            )

        except Exception as e:
            log.exception("unexpected_error", error=str(e))
            return OperationResult.transient_error(
                message=f"Unexpected error during geolocation: {str(e)}",
                error_code="UNEXPECTED_ERROR",
            )

    def healthcheck(self) -> OperationResult:
        """Check if MaxMind database is accessible.

        Returns:
            OperationResult indicating health status
        """
        log = self._logger.bind(operation="healthcheck")
        log.debug("performing_healthcheck")

        # Test with Google DNS IP
        result = self.geolocate("8.8.8.8")

        if result.is_success:
            log.info("healthcheck_success")
            return OperationResult.success(
                data={"status": "healthy", "test_ip": "8.8.8.8"},
                message="MaxMind database is accessible",
            )
        else:
            log.error("healthcheck_failed", error=result.message)
            return OperationResult.permanent_error(
                message=f"MaxMind healthcheck failed: {result.message}",
                error_code="HEALTHCHECK_FAILED",
            )
