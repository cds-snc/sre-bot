"""Integration tests for the api/v1 geolocate route."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from api.v1.routes import geolocate as geolocate_route
from infrastructure.operations import OperationResult, OperationStatus
from utils.tests import create_test_app


@pytest.fixture
def client():
    """Provide a test client for an app exposing only the geolocate route."""
    with TestClient(create_test_app(geolocate_route.router)) as test_client:
        yield test_client


@pytest.fixture
def maxmind_client(monkeypatch):
    """Substitute the MaxMind client factory at its direct-call seam."""
    fake_client = Mock()
    monkeypatch.setattr(
        geolocate_route.maxmind,
        "get_maxmind_client",
        lambda: fake_client,
    )
    return fake_client


@pytest.mark.integration
def test_geolocate_success_returns_location_and_map_links(client, maxmind_client):
    """A successful OperationResult is rendered as the geolocation payload."""
    maxmind_client.geolocate.return_value = OperationResult.success(
        data={
            "country_code": "country",
            "city": "city",
            "latitude": 0,
            "longitude": 0,
            "postal_code": "postal",
            "time_zone": "tz",
        },
        message="IP geolocated successfully",
    )

    response = client.get("/geolocate/111.111.111.111")

    assert response.status_code == 200
    assert response.json() == {
        "country": "country",
        "city": "city",
        "latitude": 0,
        "longitude": 0,
        "map_links": {
            "openstreetmap": "https://www.openstreetmap.org/?mlat=0&mlon=0#map=12/0/0",
            "opentopomap": "https://opentopomap.org/#map=12/0/0",
        },
    }
    maxmind_client.geolocate.assert_called_once_with(ip_address="111.111.111.111")


@pytest.mark.integration
def test_geolocate_not_found_maps_to_404(client, maxmind_client):
    """NOT_FOUND maps to 404 with the operation message as detail."""
    maxmind_client.geolocate.return_value = OperationResult(
        status=OperationStatus.NOT_FOUND,
        message="IP address not found in database: 111.111.111.111",
        error_code="IP_NOT_FOUND",
    )

    response = client.get("/geolocate/111.111.111.111")

    assert response.status_code == 404
    assert response.json() == {"detail": "IP address not found in database: 111.111.111.111"}


@pytest.mark.integration
def test_geolocate_invalid_ip_maps_to_400(client, maxmind_client):
    """PERMANENT_ERROR maps to 400 rather than the legacy blanket 404."""
    maxmind_client.geolocate.return_value = OperationResult.permanent_error(
        message="Invalid IP address format: 111",
        error_code="INVALID_IP_FORMAT",
    )

    response = client.get("/geolocate/111")

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid IP address format: 111"}


@pytest.mark.integration
def test_geolocate_transient_error_maps_to_503(client, maxmind_client):
    """TRANSIENT_ERROR maps to 503."""
    maxmind_client.geolocate.return_value = OperationResult.transient_error(
        message="GeoIP2 database error: db down",
        error_code="GEOIP2_ERROR",
    )

    response = client.get("/geolocate/111.111.111.111")

    assert response.status_code == 503
    assert response.json() == {"detail": "GeoIP2 database error: db down"}
