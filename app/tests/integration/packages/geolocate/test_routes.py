"""Integration tests for geolocate HTTP routes."""

import pytest
from unittest.mock import patch

from infrastructure.operations import OperationResult, OperationStatus


@pytest.mark.integration
def test_get_geolocate_success(client):
    """Test successful geolocation via HTTP."""
    mock_result = OperationResult.success(
        data={
            "city": "Mountain View",
            "country": "United States",
            "country_code": "US",
            "latitude": 37.386,
            "longitude": -122.0838,
        }
    )

    with patch("packages.geolocate.routes.geolocate_ip") as mock_geolocate:
        mock_geolocate.return_value = mock_result

        response = client.get("/geolocate?ip_address=8.8.8.8")

        assert response.status_code == 200
        data = response.json()
        assert data["ip_address"] == "8.8.8.8"
        assert data["city"] == "Mountain View"


@pytest.mark.integration
def test_get_geolocate_not_found(client):
    """Test IP not found via HTTP."""
    mock_result = OperationResult(
        status=OperationStatus.NOT_FOUND,
        message="Location not found",
        error_code="IP_NOT_FOUND",
    )

    with patch("packages.geolocate.routes.geolocate_ip") as mock_geolocate:
        mock_geolocate.return_value = mock_result

        response = client.get("/geolocate?ip_address=192.168.1.1")

        assert response.status_code == 404


@pytest.mark.integration
def test_get_geolocate_invalid_ip(client):
    """Test invalid IP format via HTTP."""
    mock_result = OperationResult(
        status=OperationStatus.PERMANENT_ERROR,
        message="Invalid IP address",
        error_code="INVALID_IP",
    )

    with patch("packages.geolocate.routes.geolocate_ip") as mock_geolocate:
        mock_geolocate.return_value = mock_result

        response = client.get("/geolocate?ip_address=not-an-ip")

        assert response.status_code == 422


@pytest.mark.integration
def test_get_geolocate_missing_ip(client):
    """Test missing IP parameter."""
    response = client.get("/geolocate")

    assert response.status_code == 422  # FastAPI validation error
