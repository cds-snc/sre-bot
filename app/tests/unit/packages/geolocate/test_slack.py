"""Tests for Slack platform features."""

import pytest
from unittest.mock import patch

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.platforms.models import CommandPayload, CommandResponse
from packages.geolocate.platforms.slack import handle_geolocate_command


@pytest.mark.unit
def test_handle_geolocate_command_success():
    """Test successful Slack command handling."""
    cmd = CommandPayload(text="8.8.8.8", user_id="U123", channel_id="C123")
    parsed_args = {"ip_address": "8.8.8.8"}

    mock_result = OperationResult.success(
        data={
            "city": "Mountain View",
            "country": "United States",
            "latitude": 37.386,
            "longitude": -122.0838,
        }
    )

    with patch("packages.geolocate.platforms.slack.geolocate_ip") as mock_service:
        mock_service.return_value = mock_result

        result = handle_geolocate_command(cmd, parsed_args)

        assert isinstance(result, CommandResponse)
        assert result.ephemeral is False
        assert result.blocks is not None
        mock_service.assert_called_once_with(ip_address="8.8.8.8")


@pytest.mark.unit
def test_handle_geolocate_command_not_found():
    """Test Slack command with IP not found."""
    cmd = CommandPayload(text="192.168.1.1", user_id="U123", channel_id="C123")
    parsed_args = {"ip_address": "192.168.1.1"}

    mock_result = OperationResult(
        status=OperationStatus.NOT_FOUND,
        message="Location not found",
        error_code="IP_NOT_FOUND",
    )

    with patch("packages.geolocate.platforms.slack.geolocate_ip") as mock_service:
        mock_service.return_value = mock_result

        result = handle_geolocate_command(cmd, parsed_args)

        assert isinstance(result, CommandResponse)
        assert result.ephemeral is True
        assert "❌" in result.message
        assert "not found" in result.message.lower()


@pytest.mark.unit
def test_handle_geolocate_command_invalid_ip():
    """Test Slack command with invalid IP format."""
    cmd = CommandPayload(text="not-an-ip", user_id="U123", channel_id="C123")
    parsed_args = {"ip_address": "not-an-ip"}

    mock_result = OperationResult(
        status=OperationStatus.PERMANENT_ERROR,
        message="Invalid IP address format",
        error_code="INVALID_IP",
    )

    with patch("packages.geolocate.platforms.slack.geolocate_ip") as mock_service:
        mock_service.return_value = mock_result

        result = handle_geolocate_command(cmd, parsed_args)

        assert isinstance(result, CommandResponse)
        assert result.ephemeral is True
        assert "❌" in result.message
        assert "invalid" in result.message.lower()
