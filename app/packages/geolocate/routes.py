"""FastAPI routes for geolocate package."""

import structlog
from fastapi import APIRouter, HTTPException, Query

from infrastructure.operations import OperationStatus
from infrastructure.services import SettingsDep
from packages.geolocate.schemas import GeolocateResponse
from packages.geolocate.service import geolocate_ip

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/geolocate", tags=["geolocate"])


@router.get(
    "",
    response_model=GeolocateResponse,
    summary="Geolocate IP Address",
    description="Query MaxMind database for IP geolocation data",
)
def get_geolocate(
    ip: str = Query(..., description="IPv4 or IPv6 address"),
    settings: SettingsDep = None,
) -> GeolocateResponse:
    """Geolocate an IP address via HTTP GET.

    Args:
        ip: IP address to geolocate
        settings: Injected settings (unused, for consistency)

    Returns:
        GeolocateResponse with location data

    Raises:
        HTTPException: 400 for invalid IP, 404 if not found, 500 for errors
    """
    log = logger.bind(ip_address=ip, endpoint="/geolocate")
    log.info("geolocate_request")

    result = geolocate_ip(ip_address=ip)

    if result.is_success:
        return GeolocateResponse(ip_address=ip, **result.data)
    elif result.status == OperationStatus.NOT_FOUND:
        log.warning("geolocate_not_found")
        raise HTTPException(status_code=404, detail=result.message)
    elif result.status == OperationStatus.PERMANENT_ERROR:
        log.error("geolocate_validation_error", error=result.message)
        raise HTTPException(status_code=400, detail=result.message)
    else:
        log.error("geolocate_error", status=result.status, error=result.message)
        raise HTTPException(status_code=500, detail="Geolocation service error")
