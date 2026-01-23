"""
Business logic for geolocating IP addresses.

This module contains platform-agnostic business logic for IP geolocation.
All platform-specific implementations should use this service.
"""

import ipaddress

import structlog

from infrastructure.operations import OperationResult
from infrastructure.services import get_maxmind_client

logger = structlog.get_logger()


def geolocate_ip(ip_address: str) -> OperationResult:
    """
    Geolocate an IP address using MaxMind GeoIP.

    Args:
        ip_address: IP address to geolocate

    Returns:
        OperationResult with location data or error
    """
    log = logger.bind(ip_address=ip_address, operation="geolocate_ip")
    log.info("geolocating_ip")

    # Validate IP address format
    try:
        ipaddress.ip_address(ip_address)
    except ValueError:
        log.warning("invalid_ip_format")
        return OperationResult.permanent_error(
            message=f"Invalid IP address format: {ip_address}",
            error_code="INVALID_IP_FORMAT",
        )

    # Use MaxMind client (infrastructure layer)
    maxmind = get_maxmind_client()
    result = maxmind.geolocate(ip_address=ip_address)

    if result.is_success:
        log.info("geolocation_success", location=result.data)
    else:
        log.warning("geolocation_failed", status=result.status, error=result.message)

    return result
