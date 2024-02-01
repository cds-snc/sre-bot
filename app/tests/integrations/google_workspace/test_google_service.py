"""Unit Tests for the google_service module."""
import json
from unittest.mock import patch, MagicMock
from json import JSONDecodeError
import pytest
from google.oauth2.service_account import Credentials
from integrations.google_workspace.google_service import (
    get_google_service,
    handle_google_api_errors,
)
from googleapiclient.errors import HttpError, Error  # type: ignore


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


def test_handle_google_api_errors_catches_http_error(capfd):
    mock_resp = MagicMock()
    mock_resp.status = "400"
    mock_func = MagicMock(side_effect=HttpError(resp=mock_resp, content=b""))
    mock_func.__name__ = "mock_func"
    decorated_func = handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result is None
    mock_func.assert_called_once()
    out, err = capfd.readouterr()
    assert "An HTTP error occurred in function 'mock_func':" in out


def test_handle_google_api_errors_catches_error(capfd):
    mock_func = MagicMock(side_effect=Error())
    mock_func.__name__ = "mock_func"
    decorated_func = handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result is None
    mock_func.assert_called_once()
    out, err = capfd.readouterr()
    assert "An error occurred in function 'mock_func':" in out


def test_handle_google_api_errors_passes_through_return_value():
    mock_func = MagicMock(return_value="test")
    decorated_func = handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result == "test"
    mock_func.assert_called_once()
