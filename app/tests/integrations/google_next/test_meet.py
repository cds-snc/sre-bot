""""Unit tests for the Google Meet API."""

from unittest.mock import MagicMock, patch

import pytest
from integrations.google_next.meet import GoogleMeet


@pytest.fixture(scope="class")
@patch("integrations.google_next.meet.get_google_service")
def google_meet(mock_get_google_service) -> GoogleMeet:
    scopes = ["https://www.googleapis.com/auth/meetings.space.created"]
    delegated_email = "email@test.com"
    mock_get_google_service.return_value = MagicMock()
    return GoogleMeet(scopes, delegated_email)


class TestGoogleMeet:
    @pytest.fixture(autouse=True)
    def setup(self, google_meet: GoogleMeet):
        self.google_meet = google_meet

    def test_init_without_scopes_and_service(self):
        """Test initialization without scopes and service raises ValueError."""
        with pytest.raises(
            ValueError, match="Either scopes or a service must be provided."
        ):
            GoogleMeet(delegated_email="email@test.com")

    @patch(
        "integrations.google_next.meet.GOOGLE_DELEGATED_ADMIN_EMAIL",
        new="default@test.com",
    )
    @patch("integrations.google_next.meet.get_google_service")
    def test_init_without_delegated_email_and_service(self, mock_get_google_service):
        """Test initialization without delegated email and service uses default email."""
        mock_get_google_service.return_value = MagicMock()
        google_meet = GoogleMeet(
            scopes=["https://www.googleapis.com/auth/meetings.space.created"]
        )
        assert google_meet.scopes == [
            "https://www.googleapis.com/auth/meetings.space.created"
        ]
        assert google_meet.delegated_email == "default@test.com"

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

    @patch("integrations.google_next.meet.execute_google_api_call")
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
