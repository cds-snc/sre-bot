from fastapi import APIRouter, HTTPException

from infrastructure.security import get_limiter
from integrations import maxmind
from packages.geolocate.schemas import build_open_source_map_links

router = APIRouter(tags=["Geolocation"])
limiter = get_limiter()


# Geolocate route. Returns the country, city, latitude, and longitude of the IP address.
@router.get("/geolocate/{ip}")
def geolocate(ip):
    reader = maxmind.geolocate(ip)
    if isinstance(reader, str):
        raise HTTPException(status_code=404, detail=reader)
    else:
        country, city, latitude, longitude = reader
        return {
            "country": country,
            "city": city,
            "latitude": latitude,
            "longitude": longitude,
            "map_links": build_open_source_map_links(
                latitude=latitude,
                longitude=longitude,
            ).model_dump(),
        }
