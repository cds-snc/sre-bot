"""Unit tests for Google Workspace SessionProvider."""

from unittest.mock import Mock, patch

import pytest

from infrastructure.clients.google_workspace.session_provider import SessionProvider


@pytest.mark.unit
class TestSessionProvider:
    """Test suite for SessionProvider."""

    def test_init_with_defaults(self, google_credentials_json: str):
        """Test SessionProvider initialization with default values."""
        provider = SessionProvider(credentials_json=google_credentials_json)

        assert provider._credentials_json == google_credentials_json
        assert provider._default_delegated_email is None
        assert provider._default_scopes == []

    def test_init_with_custom_values(self, google_credentials_json: str):
        """Test SessionProvider initialization with custom values."""
        delegated_email = "admin@example.com"
        scopes = ["https://www.googleapis.com/auth/admin.directory.user"]

        provider = SessionProvider(
            credentials_json=google_credentials_json,
            default_delegated_email=delegated_email,
            default_scopes=scopes,
        )

        assert provider._default_delegated_email == delegated_email
        assert provider._default_scopes == scopes

    @patch("infrastructure.clients.google_workspace.session_provider.build")
    @patch("infrastructure.clients.google_workspace.session_provider.service_account")
    def test_get_service_basic(
        self,
        mock_service_account,
        mock_build,
        google_credentials_json: str,
        mock_google_service: Mock,
    ):
        """Test basic service creation without delegation or scopes."""
        mock_creds = Mock()
        mock_service_account.Credentials.from_service_account_info.return_value = (
            mock_creds
        )
        mock_build.return_value = mock_google_service

        provider = SessionProvider(credentials_json=google_credentials_json)
        result = provider.get_service("admin", "directory_v1")

        # Verify credentials were loaded
        mock_service_account.Credentials.from_service_account_info.assert_called_once()
        creds_dict = (
            mock_service_account.Credentials.from_service_account_info.call_args[0][0]
        )
        assert creds_dict["client_email"] == "test@test-project.iam.gserviceaccount.com"

        # Verify service was built
        mock_build.assert_called_once_with(
            "admin",
            "directory_v1",
            credentials=mock_creds,
            cache_discovery=False,
            static_discovery=False,
        )
        assert result == mock_google_service

    @patch("infrastructure.clients.google_workspace.session_provider.build")
    @patch("infrastructure.clients.google_workspace.session_provider.service_account")
    def test_get_service_with_delegation(
        self,
        mock_service_account,
        mock_build,
        google_credentials_json: str,
        mock_google_service: Mock,
    ):
        """Test service creation with domain-wide delegation."""
        mock_creds = Mock()
        mock_delegated_creds = Mock()
        mock_creds.with_subject.return_value = mock_delegated_creds
        mock_service_account.Credentials.from_service_account_info.return_value = (
            mock_creds
        )
        mock_build.return_value = mock_google_service

        delegated_email = "admin@example.com"
        provider = SessionProvider(credentials_json=google_credentials_json)
        provider.get_service(
            "admin", "directory_v1", delegated_user_email=delegated_email
        )

        # Verify delegation was applied
        mock_creds.with_subject.assert_called_once_with(delegated_email)
        mock_build.assert_called_once_with(
            "admin",
            "directory_v1",
            credentials=mock_delegated_creds,
            cache_discovery=False,
            static_discovery=False,
        )

    @patch("infrastructure.clients.google_workspace.session_provider.build")
    @patch("infrastructure.clients.google_workspace.session_provider.service_account")
    def test_get_service_with_default_delegation(
        self,
        mock_service_account,
        mock_build,
        google_credentials_json: str,
        mock_google_service: Mock,
    ):
        """Test service creation using default delegated email."""
        mock_creds = Mock()
        mock_delegated_creds = Mock()
        mock_creds.with_subject.return_value = mock_delegated_creds
        mock_service_account.Credentials.from_service_account_info.return_value = (
            mock_creds
        )
        mock_build.return_value = mock_google_service

        default_email = "sre-bot@example.com"
        provider = SessionProvider(
            credentials_json=google_credentials_json,
            default_delegated_email=default_email,
        )
        provider.get_service("admin", "directory_v1")

        # Verify default delegation was used
        mock_creds.with_subject.assert_called_once_with(default_email)

    @patch("infrastructure.clients.google_workspace.session_provider.build")
    @patch("infrastructure.clients.google_workspace.session_provider.service_account")
    def test_get_service_with_scopes(
        self,
        mock_service_account,
        mock_build,
        google_credentials_json: str,
        mock_google_service: Mock,
    ):
        """Test service creation with OAuth scopes."""
        mock_creds = Mock()
        mock_scoped_creds = Mock()
        mock_creds.with_scopes.return_value = mock_scoped_creds
        mock_service_account.Credentials.from_service_account_info.return_value = (
            mock_creds
        )
        mock_build.return_value = mock_google_service

        scopes = ["https://www.googleapis.com/auth/admin.directory.user"]
        provider = SessionProvider(credentials_json=google_credentials_json)
        provider.get_service("admin", "directory_v1", scopes=scopes)

        # Verify scopes were applied
        mock_creds.with_scopes.assert_called_once_with(scopes)
        mock_build.assert_called_once_with(
            "admin",
            "directory_v1",
            credentials=mock_scoped_creds,
            cache_discovery=False,
            static_discovery=False,
        )

    @patch("infrastructure.clients.google_workspace.session_provider.build")
    @patch("infrastructure.clients.google_workspace.session_provider.service_account")
    def test_get_service_with_default_scopes(
        self,
        mock_service_account,
        mock_build,
        google_credentials_json: str,
        mock_google_service: Mock,
    ):
        """Test service creation using default scopes."""
        mock_creds = Mock()
        mock_scoped_creds = Mock()
        mock_creds.with_scopes.return_value = mock_scoped_creds
        mock_service_account.Credentials.from_service_account_info.return_value = (
            mock_creds
        )
        mock_build.return_value = mock_google_service

        default_scopes = ["https://www.googleapis.com/auth/admin.directory.user"]
        provider = SessionProvider(
            credentials_json=google_credentials_json, default_scopes=default_scopes
        )
        provider.get_service("admin", "directory_v1")

        # Verify default scopes were used
        mock_creds.with_scopes.assert_called_once_with(default_scopes)

    @patch("infrastructure.clients.google_workspace.session_provider.build")
    @patch("infrastructure.clients.google_workspace.session_provider.service_account")
    def test_get_service_scopes_override_default(
        self,
        mock_service_account,
        mock_build,
        google_credentials_json: str,
        mock_google_service: Mock,
    ):
        """Test that provided scopes override default scopes."""
        mock_creds = Mock()
        mock_scoped_creds = Mock()
        mock_creds.with_scopes.return_value = mock_scoped_creds
        mock_service_account.Credentials.from_service_account_info.return_value = (
            mock_creds
        )
        mock_build.return_value = mock_google_service

        default_scopes = ["https://www.googleapis.com/auth/admin.directory.user"]
        override_scopes = ["https://www.googleapis.com/auth/admin.directory.group"]

        provider = SessionProvider(
            credentials_json=google_credentials_json, default_scopes=default_scopes
        )
        provider.get_service("admin", "directory_v1", scopes=override_scopes)

        # Verify override scopes were used, not defaults
        mock_creds.with_scopes.assert_called_once_with(override_scopes)

    def test_get_service_invalid_json(self):
        """Test service creation with invalid credentials JSON."""
        provider = SessionProvider(credentials_json="invalid json")

        with pytest.raises(ValueError, match="Invalid credentials JSON"):
            provider.get_service("admin", "directory_v1")

    @patch("infrastructure.clients.google_workspace.session_provider.build")
    @patch("infrastructure.clients.google_workspace.session_provider.service_account")
    def test_get_service_delegation_and_scopes(
        self,
        mock_service_account,
        mock_build,
        google_credentials_json: str,
        mock_google_service: Mock,
    ):
        """Test service creation with both delegation and scopes."""
        mock_creds = Mock()
        mock_delegated_creds = Mock()
        mock_scoped_creds = Mock()
        mock_creds.with_subject.return_value = mock_delegated_creds
        mock_delegated_creds.with_scopes.return_value = mock_scoped_creds
        mock_service_account.Credentials.from_service_account_info.return_value = (
            mock_creds
        )
        mock_build.return_value = mock_google_service

        delegated_email = "admin@example.com"
        scopes = ["https://www.googleapis.com/auth/admin.directory.user"]

        provider = SessionProvider(credentials_json=google_credentials_json)
        provider.get_service(
            "admin", "directory_v1", scopes=scopes, delegated_user_email=delegated_email
        )

        # Verify both delegation and scopes were applied in correct order
        mock_creds.with_subject.assert_called_once_with(delegated_email)
        mock_delegated_creds.with_scopes.assert_called_once_with(scopes)
        mock_build.assert_called_once_with(
            "admin",
            "directory_v1",
            credentials=mock_scoped_creds,
            cache_discovery=False,
            static_discovery=False,
        )
