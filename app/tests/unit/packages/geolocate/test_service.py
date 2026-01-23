"""Unit tests for geolocate service."""

import pytest
from unittest.mock import Mock

from infrastructure.operations import OperationResult, OperationStatus
from packages.geolocate.service import geolocate_ip


@pytest.mark.unit
def test_geolocate_ip_success(monkeypatch):
    """Test successful IP geolocation."""
    mock_client = Mock()
    mock_result = OperationResult.success(
        data={
            "country_code": "US",
            "city": "Mountain View",
            "latitude": 37.386,
            "longitude": -122.0838,
        }
    )
    mock_client.geolocate.return_value = mock_result

    # Mock the get_maxmind_client provider
    monkeypatch.setattr(
        "packages.geolocate.service.get_maxmind_client", lambda: mock_client
    )

    result = geolocate_ip("8.8.8.8")

    assert result.is_success
    assert result.data["country_code"] == "US"
    assert result.data["city"] == "Mountain View"
    mock_client.geolocate.assert_called_once_with(ip_address="8.8.8.8")


@pytest.mark.unit
def test_geolocate_ip_invalid_format():
    """Test invalid IP address format."""
    result = geolocate_ip("not-an-ip")

    assert result.status == OperationStatus.PERMANENT_ERROR
    assert result.error_code == "INVALID_IP_FORMAT"
    assert "Invalid IP address" in result.message


@pytest.mark.unit
def test_geolocate_ip_not_found(monkeypatch):
    """Test IP not found in database."""
    mock_client = Mock()
    mock_result = OperationResult(
        status=OperationStatus.NOT_FOUND,
        message="IP address not found in database: 192.168.1.1",
        error_code="IP_NOT_FOUND",
    )
    mock_client.geolocate.return_value = mock_result

    monkeypatch.setattr(
        "packages.geolocate.service.get_maxmind_client", lambda: mock_client
    )

    result = geolocate_ip("192.168.1.1")

    assert result.status == OperationStatus.NOT_FOUND
    assert result.error_code == "IP_NOT_FOUND"
    mock_client.geolocate.assert_called_once_with(ip_address="192.168.1.1")


@pytest.mark.unit
def test_geolocate_ip_ipv6_success(monkeypatch):
    """Test successful IPv6 geolocation."""
    mock_client = Mock()
    mock_result = OperationResult.success(
        data={
            "country_code": "US",
            "city": "Mountain View",
            "latitude": 37.386,
            "longitude": -122.0838,
        }
    )
    mock_client.geolocate.return_value = mock_result

    monkeypatch.setattr(
        "packages.geolocate.service.get_maxmind_client", lambda: mock_client
    )

    result = geolocate_ip("2001:4860:4860::8888")

    assert result.is_success
    assert result.data["country_code"] == "US"
    assert result.data["city"] == "Mountain View"
    mock_client.geolocate.assert_called_once_with(ip_address="2001:4860:4860::8888")
