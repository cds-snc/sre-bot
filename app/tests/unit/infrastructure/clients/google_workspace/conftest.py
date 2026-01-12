"""Shared fixtures for Google Workspace client tests."""

import json
from typing import Any, Callable
from unittest.mock import MagicMock, Mock

import pytest
from googleapiclient.errors import HttpError


@pytest.fixture
def google_service_account_credentials() -> dict[str, Any]:
    """Mock Google service account credentials JSON."""
    return {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "key123",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC\n-----END PRIVATE KEY-----\n",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "123456789",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test%40test-project.iam.gserviceaccount.com",
    }


@pytest.fixture
def google_credentials_json(google_service_account_credentials: dict[str, Any]) -> str:
    """Mock Google credentials as JSON string."""
    return json.dumps(google_service_account_credentials)


@pytest.fixture
def mock_batch_with_callback():
    """Create a mock batch object that properly captures and uses callback.

    Returns a function that creates a configured mock batch for testing.
    """

    def create_mock_batch(responses_dict: dict[str, Any]):
        """Create mock batch with pre-configured responses.

        Args:
            responses_dict: Dict mapping request_id -> (response_data, exception)

        Example:
            mock_batch = create_mock_batch({
                "group1@example.com": ({"email": "group1@example.com"}, None),
                "group2@example.com": (None, Exception("Not found"))
            })
        """
        mock_batch = Mock()
        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        def batch_execute():
            cb = callback_holder["callback"]
            for request_id, (response, exception) in responses_dict.items():
                cb(request_id, response, exception)

        mock_batch.execute = batch_execute
        mock_batch.add = Mock()

        return capture_callback, mock_batch

    return create_mock_batch


@pytest.fixture
def mock_google_service() -> Mock:
    """Mock Google API service resource.

    Returns a mock that can be configured for different API operations.
    Use this to mock the return value of build() or SessionProvider.get_service().

    Example:
        def test_something(mock_google_service):
            mock_google_service.users().list().execute.return_value = {"users": []}
    """
    service = Mock()
    return service


@pytest.fixture
def mock_google_workspace_settings(google_credentials_json: str) -> Mock:
    """Mock GoogleWorkspaceSettings for testing.

    Returns a mock with common Google Workspace configuration.
    Customize in tests as needed:
        settings = mock_google_workspace_settings
        settings.GOOGLE_WORKSPACE_CUSTOMER_ID = "custom_customer"
    """
    settings = Mock()
    settings.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE = google_credentials_json
    settings.SRE_BOT_EMAIL = "sre-bot@example.com"
    settings.GOOGLE_WORKSPACE_CUSTOMER_ID = "my_customer"
    return settings


@pytest.fixture
def mock_session_provider():
    """Mock SessionProvider that prevents actual API calls.

    Returns a Mock that provides a properly configured mock service.
    This ensures no real Google API calls are made during tests.

    Usage:
        def test_something(mock_session_provider):
            # Configure mock service behavior
            mock_service = mock_session_provider.get_service.return_value
            mock_service.files().get().execute.return_value = {"id": "123"}
    """
    provider = Mock()
    # Return a MagicMock for the service to support arbitrary chaining
    provider.get_service.return_value = MagicMock()
    return provider


@pytest.fixture
def make_mock_request() -> Callable:
    """Factory fixture for creating mock Google API requests.

    Returns:
        Callable that creates a configured mock request object

    Example:
        def test_api_call(make_mock_request):
            request = make_mock_request(return_value={"id": "123"})
            result = request.execute()
            assert result["id"] == "123"
    """

    def _make(
        return_value: Any = None,
        side_effect: Any = None,
        raise_error: Exception | None = None,
    ) -> Mock:
        """Create a mock request with configurable behavior.

        Args:
            return_value: Value to return from execute()
            side_effect: Side effect for execute() (e.g., list of values)
            raise_error: Exception to raise from execute()

        Returns:
            Mock request object
        """
        request = Mock()
        if raise_error:
            request.execute.side_effect = raise_error
        elif side_effect:
            request.execute.side_effect = side_effect
        else:
            request.execute.return_value = return_value
        return request

    return _make


@pytest.fixture
def mock_google_api_error():
    """Factory fixture for creating mock Google API HttpError.

    Example:
        def test_error_handling(mock_google_api_error):
            error = mock_google_api_error(status=404, reason="Not Found")
            # Use error in test
    """

    def _make(status: int = 500, reason: str = "Internal Server Error") -> HttpError:
        """Create a mock HttpError.

        Args:
            status: HTTP status code
            reason: Error reason text

        Returns:
            HttpError instance
        """
        resp = Mock()
        resp.status = status
        resp.reason = reason
        content = json.dumps(
            {
                "error": {
                    "code": status,
                    "message": reason,
                    "errors": [
                        {"message": reason, "reason": reason.lower().replace(" ", "_")}
                    ],
                }
            }
        ).encode()
        return HttpError(resp=resp, content=content)

    return _make
