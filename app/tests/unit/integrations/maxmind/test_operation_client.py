"""Unit tests for the OperationResult MaxMind integration client."""

from unittest.mock import MagicMock, Mock

import pytest
from geoip2.errors import AddressNotFoundError, GeoIP2Error

from infrastructure.operations import OperationStatus
from integrations.maxmind.client import GeoLocationData, MaxMindClient


@pytest.fixture
def mock_settings() -> MagicMock:
    """Provide MaxMind settings with a deterministic DB path."""
    settings = MagicMock()
    settings.MAXMIND_DB_PATH = "/path/to/GeoLite2-City.mmdb"
    return settings


@pytest.mark.unit
def test_maxmind_client_geolocate_success(mock_settings: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful lookup returns OperationResult success with location data."""
    mock_response = Mock()
    mock_response.country.iso_code = "US"
    mock_response.city.name = "Mountain View"
    mock_response.location.latitude = 37.386
    mock_response.location.longitude = -122.0838
    mock_response.postal.code = "94035"
    mock_response.location.time_zone = "America/Los_Angeles"

    mock_reader = Mock()
    mock_reader.city.return_value = mock_response
    monkeypatch.setattr("geoip2.database.Reader", Mock(return_value=mock_reader))

    client = MaxMindClient(maxmind_settings=mock_settings)
    result = client.geolocate(ip_address="8.8.8.8")

    assert result.is_success
    assert result.data["country_code"] == "US"
    assert result.data["city"] == "Mountain View"
    assert result.data["latitude"] == 37.386
    assert result.data["longitude"] == -122.0838
    assert result.data["postal_code"] == "94035"
    assert result.data["time_zone"] == "America/Los_Angeles"
    mock_reader.city.assert_called_once_with("8.8.8.8")
    mock_reader.close.assert_called_once()


@pytest.mark.unit
def test_maxmind_client_geolocate_not_found(mock_settings: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Address-not-found maps to NOT_FOUND with a stable error code."""
    mock_reader = Mock()
    mock_reader.city.side_effect = AddressNotFoundError("Not found")
    monkeypatch.setattr("geoip2.database.Reader", Mock(return_value=mock_reader))

    client = MaxMindClient(maxmind_settings=mock_settings)
    result = client.geolocate(ip_address="192.168.1.1")

    assert result.status == OperationStatus.NOT_FOUND
    assert result.error_code == "IP_NOT_FOUND"
    mock_reader.close.assert_called_once()


@pytest.mark.unit
def test_maxmind_client_geolocate_invalid_ip(mock_settings: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid input maps to PERMANENT_ERROR with INVALID_IP_FORMAT."""
    mock_reader = Mock()
    mock_reader.city.side_effect = ValueError("invalid")
    monkeypatch.setattr("geoip2.database.Reader", Mock(return_value=mock_reader))

    client = MaxMindClient(maxmind_settings=mock_settings)
    result = client.geolocate(ip_address="not-an-ip")

    assert result.status == OperationStatus.PERMANENT_ERROR
    assert result.error_code == "INVALID_IP_FORMAT"
    mock_reader.close.assert_called_once()


@pytest.mark.unit
def test_maxmind_client_geolocate_geoip2_error(mock_settings: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """GeoIP2 errors map to TRANSIENT_ERROR with GEOIP2_ERROR."""
    mock_reader = Mock()
    mock_reader.city.side_effect = GeoIP2Error("db error")
    monkeypatch.setattr("geoip2.database.Reader", Mock(return_value=mock_reader))

    client = MaxMindClient(maxmind_settings=mock_settings)
    result = client.geolocate(ip_address="8.8.8.8")

    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "GEOIP2_ERROR"
    mock_reader.close.assert_called_once()


@pytest.mark.unit
def test_maxmind_client_healthcheck_success(mock_settings: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Healthcheck reports healthy when test geolocation succeeds."""
    mock_response = Mock()
    mock_response.country.iso_code = "US"
    mock_response.city.name = "Mountain View"
    mock_response.location.latitude = 37.386
    mock_response.location.longitude = -122.0838
    mock_response.postal.code = "94035"
    mock_response.location.time_zone = "America/Los_Angeles"

    mock_reader = Mock()
    mock_reader.city.return_value = mock_response
    monkeypatch.setattr("geoip2.database.Reader", Mock(return_value=mock_reader))

    client = MaxMindClient(maxmind_settings=mock_settings)
    result = client.healthcheck()

    assert result.is_success
    assert result.data["status"] == "healthy"
    assert result.data["test_ip"] == "8.8.8.8"


@pytest.mark.unit
def test_geolocation_data_to_dict() -> None:
    """GeoLocationData serializes all expected fields to dict keys."""
    location = GeoLocationData(
        country_code="US",
        city="Mountain View",
        latitude=37.386,
        longitude=-122.0838,
        postal_code="94035",
        time_zone="America/Los_Angeles",
    )

    data = location.to_dict()

    assert data["country_code"] == "US"
    assert data["city"] == "Mountain View"
    assert data["latitude"] == 37.386
    assert data["longitude"] == -122.0838
    assert data["postal_code"] == "94035"
    assert data["time_zone"] == "America/Los_Angeles"
