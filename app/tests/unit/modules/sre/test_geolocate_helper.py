"""Unit tests for geolocate_helper module.

Tests cover:
- Geolocate functionality with and without IP addresses
- Response formatting for geolocation data
"""

from unittest.mock import patch
from modules.sre import geolocate_helper


class TestGeolocateHelper:
    """Tests for geolocate helper functions."""

    @patch("modules.sre.geolocate_helper.maxmind")
    def test_geolocate_with_no_ip(self, mock_maxmind, mock_respond):
        """Should handle missing IP address gracefully."""
        mock_maxmind.geolocate.return_value = "Please provide an IP address."

        geolocate_helper.geolocate([""], mock_respond)

        mock_respond.assert_called_once_with("Please provide an IP address.")

    @patch("modules.sre.geolocate_helper.maxmind")
    def test_geolocate_with_valid_ip(self, mock_maxmind, mock_respond):
        """Should format geolocation response with coordinates and map link."""
        mock_maxmind.geolocate.return_value = ("CA", "Iqaluit", "0", "0")

        geolocate_helper.geolocate(["111.111.111.111"], mock_respond)

        expected_message = (
            "111.111.111.111 is located in Iqaluit, CA :flag-CA: - "
            "<https://www.google.com/maps/@0,0,12z|View on map>\n"
            "L'adresse IP 111.111.111.111 est située à Iqaluit, CA :flag-CA: - "
            "<https://www.google.com/maps/@0,0,12z|Voir sur la carte>"
        )
        mock_respond.assert_called_once_with(expected_message)

    @patch("modules.sre.geolocate_helper.maxmind")
    def test_geolocate_with_different_coordinates(self, mock_maxmind, mock_respond):
        """Should correctly format coordinates in map link."""
        mock_maxmind.geolocate.return_value = ("US", "New York", "40.7128", "-74.0060")

        geolocate_helper.geolocate(["192.168.1.1"], mock_respond)

        mock_respond.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "192.168.1.1" in call_args
        assert "New York" in call_args
        assert "40.7128,-74.0060" in call_args
        assert ":flag-US:" in call_args
