import geoip2

from integrations import maxmind

from unittest.mock import patch


@patch("integrations.maxmind.geoip2")
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


@patch("integrations.maxmind.geoip2")
def test_geolocate_not_found(geiop2_mock):
    geiop2_mock.database.Reader().city.side_effect = geoip2.errors.AddressNotFoundError
    assert maxmind.geolocate("test_ip") == "IP address not found"


@patch("integrations.maxmind.geoip2")
def test_geolocate_invalid_ip(geiop2_mock):
    geiop2_mock.database.Reader().city.side_effect = ValueError
    assert maxmind.geolocate("test_ip") == "Invalid IP address"
