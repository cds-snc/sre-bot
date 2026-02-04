"""Client for interacting with Maxmind's GeoIP2 database."""

import geoip2.database
import structlog
from geoip2.errors import AddressNotFoundError, GeoIP2Error
from core.config import settings

logger = structlog.get_logger()
MAXMIND_DB_PATH = settings.maxmind.MAXMIND_DB_PATH


def geolocate(ip) -> tuple | str:
    """Geolocate an IP address using Maxmind.

    Args:
        ip (str): The IP address to geolocate.

    Returns:
        tuple | str: A tuple containing the country code, city name, latitude, and longitude of the IP address. A string if the IP address is not found or invalid.
    """
    log = logger.bind(ip=ip)
    try:
        reader = geoip2.database.Reader(MAXMIND_DB_PATH)
        try:
            response = reader.city(ip)
            return (
                response.country.iso_code,
                response.city.name,
                response.location.latitude,
                response.location.longitude,
            )
        except AddressNotFoundError:
            return "IP address not found"
        except ValueError:
            return "Invalid IP address"
        except GeoIP2Error as e:
            log.error("maxmind_geolocate_error", error=str(e))
            raise
        finally:
            reader.close()
    except (FileNotFoundError, IOError) as e:
        log.error("maxmind_infrastructure_error", error=str(e))
        raise


def healthcheck():
    """Check if the bot can interact with Maxmind."""
    healthy = False
    try:
        result = geolocate("8.8.8.8")
        healthy = isinstance(result, tuple)
        logger.info(
            "maxmind_healthcheck_success",
            result=result,
            status="healthy" if healthy else "unhealthy",
        )
    except Exception as error:
        logger.exception("maxmind_healthcheck_failed", error=str(error))
    return healthy
