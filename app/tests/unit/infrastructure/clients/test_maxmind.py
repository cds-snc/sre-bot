"""Unit tests for MaxMind infrastructure client."""

import pytest
from unittest.mock import Mock, MagicMock
from geoip2.errors import AddressNotFoundError, GeoIP2Error

from infrastructure.clients.maxmind import MaxMindClient, GeoLocationData
from infrastructure.operations import OperationStatus


@pytest.fixture
def mock_settings():
    """Create mock settings for MaxMind client."""
    settings = MagicMock()
    settings.maxmind.MAXMIND_DB_PATH = "/path/to/GeoLite2-City.mmdb"
    return settings


@pytest.mark.unit
def test_maxmind_client_success(mock_settings, monkeypatch):
    """Test successful geolocation with MaxMind client."""
    # Mock geoip2.database.Reader
    mock_response = Mock()
    mock_response.country.iso_code = "US"
    mock_response.city.name = "Mountain View"
    mock_response.location.latitude = 37.386
    mock_response.location.longitude = -122.0838
    mock_response.postal.code = "94035"
    mock_response.location.time_zone = "America/Los_Angeles"

    mock_reader = Mock()
    mock_reader.city.return_value = mock_response
    mock_reader_class = Mock(return_value=mock_reader)

    monkeypatch.setattr("geoip2.database.Reader", mock_reader_class)

    client = MaxMindClient(settings=mock_settings)
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
def test_maxmind_client_not_found(mock_settings, monkeypatch):
    """Test IP not found in database."""
    mock_reader = Mock()
    mock_reader.city.side_effect = AddressNotFoundError("Not found")
    mock_reader_class = Mock(return_value=mock_reader)

    monkeypatch.setattr("geoip2.database.Reader", mock_reader_class)

    client = MaxMindClient(settings=mock_settings)
    result = client.geolocate(ip_address="192.168.1.1")

    assert result.status == OperationStatus.NOT_FOUND
    assert result.error_code == "IP_NOT_FOUND"
    assert "not found" in result.message.lower()
    mock_reader.close.assert_called_once()


@pytest.mark.unit
def test_maxmind_client_invalid_ip(mock_settings, monkeypatch):
    """Test invalid IP address format."""
    mock_reader = Mock()
    mock_reader.city.side_effect = ValueError("Invalid IP")
    mock_reader_class = Mock(return_value=mock_reader)

    monkeypatch.setattr("geoip2.database.Reader", mock_reader_class)

    client = MaxMindClient(settings=mock_settings)
    result = client.geolocate(ip_address="not-an-ip")

    assert result.status == OperationStatus.PERMANENT_ERROR
    assert result.error_code == "INVALID_IP_FORMAT"
    mock_reader.close.assert_called_once()


@pytest.mark.unit
def test_maxmind_client_geoip2_error(mock_settings, monkeypatch):
    """Test GeoIP2 database error."""
    mock_reader = Mock()
    mock_reader.city.side_effect = GeoIP2Error("Database error")
    mock_reader_class = Mock(return_value=mock_reader)

    monkeypatch.setattr("geoip2.database.Reader", mock_reader_class)

    client = MaxMindClient(settings=mock_settings)
    result = client.geolocate(ip_address="8.8.8.8")

    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "GEOIP2_ERROR"
    mock_reader.close.assert_called_once()


@pytest.mark.unit
def test_maxmind_client_db_file_error(mock_settings, monkeypatch):
    """Test database file not found."""
    mock_reader_class = Mock(side_effect=FileNotFoundError("DB not found"))
    monkeypatch.setattr("geoip2.database.Reader", mock_reader_class)

    client = MaxMindClient(settings=mock_settings)
    result = client.geolocate(ip_address="8.8.8.8")

    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "DB_FILE_ERROR"
    assert "database file error" in result.message.lower()


@pytest.mark.unit
def test_maxmind_client_healthcheck_success(mock_settings, monkeypatch):
    """Test successful healthcheck."""
    mock_response = Mock()
    mock_response.country.iso_code = "US"
    mock_response.city.name = "Mountain View"
    mock_response.location.latitude = 37.386
    mock_response.location.longitude = -122.0838
    mock_response.postal.code = "94035"
    mock_response.location.time_zone = "America/Los_Angeles"

    mock_reader = Mock()
    mock_reader.city.return_value = mock_response
    mock_reader_class = Mock(return_value=mock_reader)

    monkeypatch.setattr("geoip2.database.Reader", mock_reader_class)

    client = MaxMindClient(settings=mock_settings)
    result = client.healthcheck()

    assert result.is_success
    assert result.data["status"] == "healthy"
    assert result.data["test_ip"] == "8.8.8.8"


@pytest.mark.unit
def test_maxmind_client_healthcheck_failed(mock_settings, monkeypatch):
    """Test failed healthcheck."""
    mock_reader_class = Mock(side_effect=FileNotFoundError("DB not found"))
    monkeypatch.setattr("geoip2.database.Reader", mock_reader_class)

    client = MaxMindClient(settings=mock_settings)
    result = client.healthcheck()

    assert result.status == OperationStatus.PERMANENT_ERROR
    assert result.error_code == "HEALTHCHECK_FAILED"


@pytest.mark.unit
def test_geolocation_data_to_dict():
    """Test GeoLocationData to_dict conversion."""
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
