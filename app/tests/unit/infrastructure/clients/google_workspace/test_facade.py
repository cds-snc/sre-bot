"""Unit tests for Google Workspace clients facade."""

from unittest.mock import Mock, patch

import pytest

from infrastructure.clients.google_workspace.facade import GoogleWorkspaceClients
from infrastructure.clients.google_workspace.session_provider import SessionProvider


@pytest.mark.unit
class TestGoogleWorkspaceClients:
    """Test suite for GoogleWorkspaceClients facade."""

    @patch("infrastructure.clients.google_workspace.facade.SessionProvider")
    def test_initialization(
        self, mock_session_provider_class, mock_google_workspace_settings
    ):
        """Test facade initialization with settings."""
        mock_provider_instance = Mock(spec=SessionProvider)
        mock_session_provider_class.return_value = mock_provider_instance

        facade = GoogleWorkspaceClients(mock_google_workspace_settings)

        # Verify SessionProvider was created with correct parameters
        mock_session_provider_class.assert_called_once_with(
            credentials_json=mock_google_workspace_settings.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE,
            default_delegated_email=mock_google_workspace_settings.SRE_BOT_EMAIL,
            default_scopes=[],
        )

        # Verify instance attributes
        assert facade._session_provider == mock_provider_instance

    @patch("infrastructure.clients.google_workspace.facade.SessionProvider")
    def test_session_provider_attribute(
        self, mock_session_provider_class, mock_google_workspace_settings
    ):
        """Test that session provider is accessible."""
        mock_provider_instance = Mock(spec=SessionProvider)
        mock_session_provider_class.return_value = mock_provider_instance

        facade = GoogleWorkspaceClients(mock_google_workspace_settings)

        assert hasattr(facade, "_session_provider")
        assert isinstance(facade._session_provider, (SessionProvider, Mock))

    @patch("infrastructure.clients.google_workspace.facade.SessionProvider")
    def test_multiple_instances_get_own_session_provider(
        self, mock_session_provider_class, mock_google_workspace_settings
    ):
        """Test that each facade instance gets its own session provider."""
        mock_provider_instance_1 = Mock(spec=SessionProvider)
        mock_provider_instance_2 = Mock(spec=SessionProvider)
        mock_session_provider_class.side_effect = [
            mock_provider_instance_1,
            mock_provider_instance_2,
        ]

        facade1 = GoogleWorkspaceClients(mock_google_workspace_settings)
        facade2 = GoogleWorkspaceClients(mock_google_workspace_settings)

        assert facade1._session_provider == mock_provider_instance_1
        assert facade2._session_provider == mock_provider_instance_2
        assert facade1._session_provider != facade2._session_provider

    @patch("infrastructure.clients.google_workspace.facade.SessionProvider")
    def test_custom_settings_values(self, mock_session_provider_class):
        """Test facade initialization with custom settings values."""
        mock_provider_instance = Mock(spec=SessionProvider)
        mock_session_provider_class.return_value = mock_provider_instance

        # Create custom settings
        custom_settings = Mock()
        custom_settings.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE = '{"custom": "credentials"}'
        custom_settings.SRE_BOT_EMAIL = "custom-bot@example.com"
        custom_settings.GOOGLE_WORKSPACE_CUSTOMER_ID = "custom_customer"

        GoogleWorkspaceClients(custom_settings)

        # Verify custom values were passed to SessionProvider
        mock_session_provider_class.assert_called_once_with(
            credentials_json='{"custom": "credentials"}',
            default_delegated_email="custom-bot@example.com",
            default_scopes=[],
        )

    @patch("infrastructure.clients.google_workspace.facade.SessionProvider")
    def test_logger_binding(
        self, mock_session_provider_class, mock_google_workspace_settings
    ):
        """Test that logger is properly bound with component name."""
        mock_provider_instance = Mock(spec=SessionProvider)
        mock_session_provider_class.return_value = mock_provider_instance

        facade = GoogleWorkspaceClients(mock_google_workspace_settings)

        # Verify logger attribute exists (structlog.bind returns a new logger)
        assert hasattr(facade, "_logger")
        assert facade._logger is not None
