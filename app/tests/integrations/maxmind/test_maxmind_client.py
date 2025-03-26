from unittest.mock import patch
import pytest
import geoip2

from integrations.maxmind import client as maxmind


@patch("integrations.maxmind.client.geoip2")
def test_geolocate(geiop2_mock):
    geiop2_mock.database.Reader().city.return_value.country.iso_code = "CA"
    geiop2_mock.database.Reader().city.return_value.city.name = "test_city"
    geiop2_mock.database.Reader().city.return_value.location.latitude = "test_lat"
    geiop2_mock.database.Reader().city.return_value.location.longitude = "test_long"
    assert maxmind.geolocate("test_ip") == (
        "CA",
        "test_city",
        "test_lat",
        "test_long",
    )


@patch("integrations.maxmind.client.geoip2")
def test_geolocate_not_found(geiop2_mock):
    geiop2_mock.database.Reader().city.side_effect = geoip2.errors.AddressNotFoundError(
        "IP address not found"
    )
    assert maxmind.geolocate("test_ip") == "IP address not found"


@patch("integrations.maxmind.client.geoip2")
def test_geolocate_invalid_ip(geiop2_mock):
    geiop2_mock.database.Reader().city.side_effect = ValueError
    assert maxmind.geolocate("test_ip") == "Invalid IP address"


@patch("integrations.maxmind.client.logger")
@patch("integrations.maxmind.client.geoip2")
def test_geolocate_geoip2_error(geiop2_mock, logger_mock):
    geiop2_mock.database.Reader().city.side_effect = geoip2.errors.GeoIP2Error(
        "GeoIP2 Error"
    )
    with pytest.raises(geoip2.errors.GeoIP2Error):
        maxmind.geolocate("test_ip")
    logger_mock.error.assert_called_with(
        "maxmind_geolocate_error",
        error="GeoIP2 Error",
    )


@patch.object(maxmind, "MAXMIND_DB_PATH", "some_path")
@patch("integrations.maxmind.client.logger")
@patch("integrations.maxmind.client.geoip2")
def test_geolocate_file_not_found(geiop2_mock, logger_mock):
    geiop2_mock.database.Reader.side_effect = FileNotFoundError("File not found")
    with pytest.raises(FileNotFoundError):
        maxmind.geolocate("test_ip")
    logger_mock.error.assert_called_with(
        "maxmind_infrastructure_error",
        error="File not found",
    )


@patch.object(maxmind, "MAXMIND_DB_PATH", "some_path")
@patch("integrations.maxmind.client.logger")
@patch("integrations.maxmind.client.geoip2")
def test_geolocate_io_error(geiop2_mock, logger_mock):
    geiop2_mock.database.Reader.side_effect = IOError("IO Error")
    with pytest.raises(IOError):
        maxmind.geolocate("test_ip")
    logger_mock.error.assert_called_with(
        "maxmind_infrastructure_error",
        error="IO Error",
    )


@patch("integrations.maxmind.client.logger")
@patch("integrations.maxmind.client.geoip2")
def test_healthcheck_healthy(geiop2_mock, logger_mock):
    geiop2_mock.database.Reader().city.return_value.country.iso_code = "CA"
    geiop2_mock.database.Reader().city.return_value.city.name = "test_city"
    geiop2_mock.database.Reader().city.return_value.location.latitude = "test_lat"
    geiop2_mock.database.Reader().city.return_value.location.longitude = "test_long"
    assert maxmind.healthcheck() is True
    logger_mock.info.assert_called_with(
        "maxmind_healthcheck_success",
        result=("CA", "test_city", "test_lat", "test_long"),
        status="healthy",
    )


@patch("integrations.maxmind.client.logger")
@patch("integrations.maxmind.client.geoip2")
def test_healthcheck_unhealthy(geiop2_mock, logger_mock):
    geiop2_mock.database.Reader().city.side_effect = ValueError
    assert maxmind.healthcheck() is False
    logger_mock.info.assert_called_with(
        "maxmind_healthcheck_success", result="Invalid IP address", status="unhealthy"
    )


@patch.object(maxmind, "MAXMIND_DB_PATH", "some_path")
@patch("integrations.maxmind.client.logger")
@patch("integrations.maxmind.client.geoip2")
def test_healthcheck_error(geiop2_mock, logger_mock):
    geiop2_mock.database.Reader.side_effect = FileNotFoundError("some_path")
    assert maxmind.healthcheck() is False
    logger_mock.exception.assert_called_with(
        "maxmind_healthcheck_failed", error="some_path"
    )
