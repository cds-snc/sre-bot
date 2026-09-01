from fastapi import APIRouter, HTTPException

from infrastructure.operations import OperationStatus
from infrastructure.security import get_limiter
from integrations import maxmind
from packages.geolocate.schemas import build_open_source_map_links

router = APIRouter(tags=["Geolocation"])
limiter = get_limiter()


# Geolocate route. Returns the country, city, latitude, and longitude of the IP address.
@router.get("/geolocate/{ip}")
def geolocate(ip):
    result = maxmind.get_maxmind_client().geolocate(ip_address=ip)

    if result.status == OperationStatus.NOT_FOUND:
        raise HTTPException(status_code=404, detail=result.message)
    if result.status == OperationStatus.PERMANENT_ERROR:
        raise HTTPException(status_code=400, detail=result.message)
    if result.status == OperationStatus.TRANSIENT_ERROR:
        raise HTTPException(status_code=503, detail=result.message)

    if result.data is None:
        raise HTTPException(status_code=503, detail=result.message)

    country = result.data["country_code"]
    city = result.data["city"]
    latitude = result.data["latitude"]
    longitude = result.data["longitude"]

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
