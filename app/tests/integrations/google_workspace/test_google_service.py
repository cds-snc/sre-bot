"""Unit Tests for the google_service module."""
import json
from unittest.mock import patch, MagicMock
from json import JSONDecodeError
import pytest
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError, Error  # type: ignore
from google.auth.exceptions import RefreshError  # type: ignore
from integrations.google_workspace.google_service import (
    get_google_service,
    handle_google_api_errors,
)


@patch("integrations.google_workspace.google_service.build")
@patch.object(Credentials, "from_service_account_info")
def test_get_google_service_returns_build_object(credentials_mock, build_mock):
    """
    Test case to verify that the function returns a build object.
    """
    credentials_mock.return_value = MagicMock()
    with patch.dict(
        "os.environ",
        {"GCP_SRE_SERVICE_ACCOUNT_KEY_FILE": json.dumps({"type": "service_account"})},
    ):
        get_google_service("drive", "v3")
    build_mock.assert_called_once_with(
        "drive", "v3", credentials=credentials_mock.return_value, cache_discovery=False
    )


def test_get_google_service_raises_exception_if_credentials_json_not_set():
    """
    Test case to verify that the function raises an exception if:
     - GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is not set.
    """
    with patch.dict("os.environ", clear=True):
        with pytest.raises(ValueError) as e:
            get_google_service("drive", "v3")
        assert "Credentials JSON not set" in str(e.value)


@patch("integrations.google_workspace.google_service.build")
@patch.object(Credentials, "from_service_account_info")
def test_get_google_service_raises_exception_if_credentials_json_is_invalid(
    credentials_mock, build_mock
):
    """
    Test case to verify that the function raises an exception if:
     - GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is invalid.
    """
    with patch.dict("os.environ", {"GCP_SRE_SERVICE_ACCOUNT_KEY_FILE": "invalid"}):
        with pytest.raises(JSONDecodeError) as e:
            get_google_service("drive", "v3")
        assert "Invalid credentials JSON" in str(e.value)


@patch("logging.error")
def test_handle_google_api_errors_catches_http_error(mocked_logging_error):
    mock_resp = MagicMock()
    mock_resp.status = "400"
    mock_resp.reason = "Bad Request"
    mock_func = MagicMock(side_effect=HttpError(resp=mock_resp, content=b""))
    mock_func.__name__ = "mock_func"
    decorated_func = handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result is None
    mocked_logging_error.assert_called_once_with(
        "An HTTP error occurred in function 'mock_func': <HttpError 400 \"Bad Request\">"
    )


@patch("logging.error")
def test_handle_google_api_errors_catches_value_error(mocked_logging_error):
    mock_func = MagicMock(side_effect=ValueError("ValueError message"))
    mock_func.__name__ = "mock_func"
    decorated_func = handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result is None
    mock_func.assert_called_once()
    mocked_logging_error.assert_called_once_with(
        "A ValueError occurred in function 'mock_func': ValueError message"
    )


@patch("logging.error")
def test_handle_google_api_errors_catches_error(mocked_logging_error):
    mock_func = MagicMock(side_effect=Error("Error message"))
    mock_func.__name__ = "mock_func"
    decorated_func = handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result is None
    mock_func.assert_called_once()
    mocked_logging_error.assert_called_once_with(
        "An error occurred in function 'mock_func': Error message"
    )


@patch("logging.error")
def test_handle_google_api_errors_catches_refresh_error(mocked_logging_error):
    mock_func = MagicMock(side_effect=RefreshError("RefreshError message"))
    mock_func.__name__ = "mock_func"
    decorated_func = handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result is None
    mock_func.assert_called_once()
    mocked_logging_error.assert_called_once_with(
        "A RefreshError occurred in function 'mock_func': RefreshError message"
    )


def test_handle_google_api_errors_passes_through_return_value():
    mock_func = MagicMock(return_value="test")
    decorated_func = handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result == "test"
    mock_func.assert_called_once()
