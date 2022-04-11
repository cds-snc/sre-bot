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
