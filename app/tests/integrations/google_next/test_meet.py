""" "Unit tests for the Google Meet API."""

from unittest.mock import MagicMock, patch

import pytest
from integrations.google_next.meet import GoogleMeet


@pytest.fixture
def mock_service():
    with patch(
        "integrations.google_next.meet.get_google_service"
    ) as mock_get_google_service:
        mock_get_google_service.return_value = MagicMock()
        yield mock_get_google_service


@pytest.fixture
def mock_execute_google_api_call():
    with patch("integrations.google_next.meet.execute_google_api_call") as mock_execute:
        mock_execute.return_value = MagicMock()
        yield mock_execute


@pytest.fixture
@patch("integrations.google_next.meet.DEFAULT_SCOPES", ["tests", "scopes"])
def google_meet(mock_service):
    return GoogleMeet()


class TestGoogleMeet:
    """Unit tests for the Google Meet API integration."""

    @pytest.fixture(autouse=True)
    # pylint: disable=redefined-outer-name
    def setup(self, google_meet: GoogleMeet):
        # pylint: disable=attribute-defined-outside-init
        self.google_meet = google_meet

    def test_init_uses_defaults(self):
        """Test initialization with default scopes and no delegated email."""
        assert self.google_meet.scopes == ["tests", "scopes"]
        assert self.google_meet.delegated_email is None

    def test_init_without_delegated_email_and_service(self, mock_service):
        """Test initialization without delegated email and service uses default email."""
        google_meet = GoogleMeet(
            scopes=["new", "scopes"],
            delegated_email="user@test.com",
            service=mock_service.return_value,
        )
        assert google_meet.scopes == ["new", "scopes"]
        assert google_meet.delegated_email == "user@test.com"
        assert google_meet.service is not None

    @patch("integrations.google_next.meet.get_google_service")
    def test_get_google_service(self, mock_get_google_service):
        """Test get_docs_service returns a service."""
        mock_get_google_service.return_value = MagicMock()
        service = self.google_meet._get_google_service()
        assert service is not None
        mock_get_google_service.assert_called_once_with(
            "meet",
            "v2",
            self.google_meet.scopes,
            self.google_meet.delegated_email,
        )

    def test_create_space(self, mock_execute_google_api_call):
        """Test create_space returns a response."""
        mock_execute_google_api_call.return_value = {
            "name": "spaces/asdfasdf",
            "meetingUri": "https://meet.google.com/aaa-bbbb-ccc",
            "meetingCode": "aaa-bbbb-ccc",
            "config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"},
        }
        response = self.google_meet.create_space()
        assert response is not None
        mock_execute_google_api_call.assert_called_once_with(
            self.google_meet.service,
            "spaces",
            "create",
            body={"config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"}},
        )
