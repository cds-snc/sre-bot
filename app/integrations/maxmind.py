import logging
import geoip2.database
from geoip2.errors import AddressNotFoundError


def geolocate(ip):
    reader = geoip2.database.Reader("./geodb/GeoLite2-City.mmdb")
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


def healthcheck():
    """Check if the bot can interact with Maxmind."""
    healthy = False
    try:
        result = geolocate("8.8.8.8")
        healthy = isinstance(result, tuple)
        logging.info(f"Maxmind healthcheck result: {result}")
    except Exception as error:
        logging.error(f"Maxmind healthcheck failed: {error}")
    return healthy
