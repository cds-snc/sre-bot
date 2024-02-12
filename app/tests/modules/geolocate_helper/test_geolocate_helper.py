from modules.geolocate_helper import geolocate_helper

from unittest.mock import MagicMock, patch


@patch("modules.geolocate.geolocate.maxmind")
def test_geolocate_command_with_no_ip(maxmind_mock):
    maxmind_mock.geolocate.return_value = "Please provide an IP address."
    respond = MagicMock()
    geolocate_helper([""], respond)
    respond.assert_called_once_with("Please provide an IP address.")


@patch("modules.geolocate.geolocate.maxmind")
def test_geolocate_command_with_ip(maxmind_mock):
    maxmind_mock.geolocate.return_value = ("CA", "Iqaluit", "0", "0")
    respond = MagicMock()
    geolocate_helper(["111.111.111.111"], respond)
    respond.assert_called_once_with(
        "111.111.111.111 is located in Iqaluit, CA :flag-CA: - <https://www.google.com/maps/@0,0,12z|View on map>"
    )
