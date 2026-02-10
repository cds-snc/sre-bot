"""Integration tests for SRE command providers.

Tests cover provider initialization, delegation to helper functions,
and command payload handling through the provider interface.
"""

from unittest.mock import MagicMock, patch
from modules.sre.sre import (
    VersionProvider,
    LegacyWebhooksProvider,
    LegacyIncidentProvider,
)


class TestVersionProvider:
    """Tests for version command provider integration."""

    def test_version_provider_initialization(self):
        """Version provider should initialize without errors."""
        provider = VersionProvider()
        assert provider is not None
        assert provider.registry is None

    def test_version_provider_responds_to_version_command(self, mock_ack, mock_respond):
        """Version provider should respond to version command."""
        provider = VersionProvider()

        payload = {
            "command": {"text": ""},
            "respond": mock_respond,
            "ack": mock_ack,
            "client": MagicMock(),
        }

        provider.handle(payload)

        mock_ack.assert_called_once()
        mock_respond.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "SRE Bot version:" in call_args


class TestLegacyWebhooksProvider:
    """Tests for legacy webhooks command provider integration."""

    def test_webhooks_provider_initialization(self):
        """Webhooks provider should initialize without errors."""
        provider = LegacyWebhooksProvider()
        assert provider is not None
        assert provider.registry is None

    @patch("modules.sre.webhook_helper.handle_webhook_command")
    def test_webhooks_provider_delegates_to_helper(
        self, mock_handle, mock_ack, mock_respond, mock_client
    ):
        """Webhooks provider should delegate to webhook helper."""
        provider = LegacyWebhooksProvider()

        payload = {
            "command": {"text": "list"},
            "respond": mock_respond,
            "ack": mock_ack,
            "client": mock_client,
        }

        provider.handle(payload)

        mock_ack.assert_called_once()
        mock_handle.assert_called_once_with(
            ["list"], mock_client, payload["command"], mock_respond
        )


class TestLegacyIncidentProvider:
    """Tests for legacy incident command provider integration."""

    def test_incident_provider_initialization(self):
        """Incident provider should initialize without errors."""
        provider = LegacyIncidentProvider()
        assert provider is not None
        assert provider.registry is None

    @patch("modules.incident.incident_helper.handle_incident_command")
    def test_incident_provider_delegates_to_helper(
        self, mock_handle, mock_ack, mock_respond, mock_client
    ):
        """Incident provider should delegate to incident helper."""
        provider = LegacyIncidentProvider()

        payload = {
            "command": {"text": "list"},
            "respond": mock_respond,
            "ack": mock_ack,
            "client": mock_client,
        }

        provider.handle(payload)

        mock_ack.assert_called_once()
        mock_handle.assert_called_once_with(
            ["list"], mock_client, payload["command"], mock_respond, mock_ack
        )
