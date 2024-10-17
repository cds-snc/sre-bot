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
    execute_google_api_call,
    get_google_api_command_parameters,
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


@patch("integrations.google_workspace.google_service.build")
@patch.object(Credentials, "from_service_account_info")
def test_get_google_service_with_delegated_user_email(credentials_mock, build_mock):
    """
    Test case to verify that the function works correctly with a delegated user email.
    """
    credentials_mock.return_value = MagicMock()
    with patch.dict(
        "os.environ",
        {"GCP_SRE_SERVICE_ACCOUNT_KEY_FILE": json.dumps({"type": "service_account"})},
    ):
        get_google_service("drive", "v3", delegated_user_email="test@test.com")
    credentials_mock.return_value.with_subject.assert_called_once_with("test@test.com")


@patch("integrations.google_workspace.google_service.build")
@patch.object(Credentials, "from_service_account_info")
def test_get_google_service_with_scopes(credentials_mock, build_mock):
    """
    Test case to verify that the function works correctly with scopes.
    """
    credentials_mock.return_value = MagicMock()
    with patch.dict(
        "os.environ",
        {"GCP_SRE_SERVICE_ACCOUNT_KEY_FILE": json.dumps({"type": "service_account"})},
    ):
        get_google_service("drive", "v3", scopes=["scope1", "scope2"])
    credentials_mock.return_value.with_scopes.assert_called_once_with(
        ["scope1", "scope2"]
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
    mock_func.__module__ = "mock_module"
    decorated_func = handle_google_api_errors(mock_func)

    with pytest.raises(HttpError, match='<HttpError 400 "Bad Request">'):
        result = decorated_func()
        assert result is None

    mocked_logging_error.assert_called_once_with(
        "An HTTP error occurred in function 'mock_module:mock_func': <HttpError 400 \"Bad Request\">"
    )


@patch("logging.error")
def test_handle_google_api_errors_catches_value_error(mocked_logging_error):
    mock_func = MagicMock(side_effect=ValueError("ValueError message"))
    mock_func.__name__ = "mock_func"
    mock_func.__module__ = "mock_module"
    decorated_func = handle_google_api_errors(mock_func)

    with pytest.raises(ValueError, match="ValueError message"):
        result = decorated_func()
        assert result is None

    mock_func.assert_called_once()
    mocked_logging_error.assert_called_once_with(
        "A ValueError occurred in function 'mock_module:mock_func': ValueError message"
    )


@patch("logging.error")
def test_handle_google_api_errors_catches_error(mocked_logging_error):
    mock_func = MagicMock(side_effect=Error("Error message"))
    mock_func.__name__ = "mock_func"
    mock_func.__module__ = "mock_module"
    decorated_func = handle_google_api_errors(mock_func)

    with pytest.raises(Error, match="Error message"):
        result = decorated_func()
        assert result is None

    mock_func.assert_called_once()
    mocked_logging_error.assert_called_once_with(
        "An error occurred in function 'mock_module:mock_func': Error message"
    )


@patch("logging.warning")
@patch("logging.error")
def test_handle_google_api_errors_catches_exception(
    mocked_logging_error: MagicMock, mocked_logging_warning: MagicMock
):
    mock_func = MagicMock(side_effect=Exception("Exception message"))
    mock_func.__name__ = "mock_func"
    mock_func.__module__ = "mock_module"
    decorated_func = handle_google_api_errors(mock_func)

    with pytest.raises(Exception, match="Exception message"):
        result = decorated_func()
        assert result is None

    mock_func.assert_called_once()
    mocked_logging_error.assert_called_once_with(
        "An unexpected error occurred in function 'mock_module:mock_func': Exception message"
    )

    mock_func = MagicMock(side_effect=Exception("timed out"))
    mock_func.__name__ = "list_groups"
    mock_func.__module__ = "mock_module"
    decorated_func = handle_google_api_errors(mock_func)

    with pytest.raises(Exception, match="timed out"):
        result = decorated_func()
        assert result is None

    mock_func.assert_called_once()
    mocked_logging_error.assert_called_with(
        "An unexpected error occurred in function 'mock_module:list_groups': timed out"
    )

    mock_func = MagicMock(side_effect=Exception("timed out"))
    mock_func.__name__ = "get_user"
    mock_func.__module__ = "mock_module"
    decorated_func = handle_google_api_errors(mock_func)

    with pytest.raises(Exception, match="timed out"):
        result = decorated_func("arg1", "arg2", a="b")
        assert result is None

    mock_func.assert_called_once()
    mocked_logging_warning.assert_called_once_with(
        "A non critical error occurred in function 'mock_module:get_user(arg1, arg2, a=b)': timed out"
    )


@patch("logging.error")
def test_handle_google_api_errors_catches_refresh_error(mocked_logging_error):
    mock_func = MagicMock(side_effect=RefreshError("RefreshError message"))
    mock_func.__name__ = "mock_func"
    mock_func.__module__ = "mock_module"
    decorated_func = handle_google_api_errors(mock_func)

    with pytest.raises(RefreshError, match="RefreshError message"):
        decorated_func()

    mock_func.assert_called_once()
    mocked_logging_error.assert_called_once_with(
        "A RefreshError occurred in function 'mock_module:mock_func': RefreshError message"
    )


def test_handle_google_api_errors_passes_through_return_value():
    mock_func = MagicMock(return_value=("test", set()))
    decorated_func = handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result == "test"
    mock_func.assert_called_once()


@patch("logging.warning")
def test_handle_google_api_errors_processes_unsupported_params(
    mocked_logging_warning,
):
    mock_func = MagicMock(return_value=("test", {"unsupported"}))
    mock_func.__name__ = "mock_func"
    mock_func.__module__ = "mock_module"
    decorated_func = handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result == "test"
    mock_func.assert_called_once()
    mocked_logging_warning.assert_called_once_with(
        "Unknown parameters in 'mock_module:mock_func' were detected: unsupported"
    )


@patch("integrations.google_workspace.google_service.get_google_service")
def test_execute_google_api_call_calls_get_google_service(mock_get_google_service):
    execute_google_api_call("service_name", "version", "resource", "method")
    mock_get_google_service.assert_called_once_with(
        "service_name", "version", None, None
    )


@patch("integrations.google_workspace.google_service.get_google_service")
def test_execute_google_api_call_calls_get_google_service_with_delegated_user_email(
    mock_get_google_service,
):
    execute_google_api_call(
        "service_name",
        "version",
        "resource",
        "method",
        delegated_user_email="admin.user@email.com",
    )
    mock_get_google_service.assert_called_once_with(
        "service_name",
        "version",
        None,
        "admin.user@email.com",
    )


@patch("integrations.google_workspace.google_service.convert_kwargs_to_camel_case")
@patch("integrations.google_workspace.google_service.get_google_service")
@patch("integrations.google_workspace.google_service.get_google_api_command_parameters")
def test_execute_google_api_call_calls_getattr_with_service_and_resource(
    mock_get_google_api_command_parameters,
    mock_get_google_service,
    mock_convert_kwargs_to_camel_case,
):
    mock_service = MagicMock()
    mock_get_google_service.return_value = mock_service

    execute_google_api_call("service_name", "version", "resource", "method")

    mock_service.resource.assert_called_once()


@patch("integrations.google_workspace.google_service.convert_kwargs_to_camel_case")
@patch("integrations.google_workspace.google_service.get_google_service")
@patch("integrations.google_workspace.google_service.get_google_api_command_parameters")
def test_execute_google_api_call_when_paginate_is_false(
    mock_get_google_api_command_parameters,
    mock_get_google_service,
    mock_convert_kwargs_to_camel_case,
):
    mock_get_google_api_command_parameters.return_value = ["arg1"]
    mock_convert_kwargs_to_camel_case.return_value = {"arg1": "value1"}

    mock_service = MagicMock()
    mock_get_google_service.return_value = mock_service

    # Set up the MagicMock for resource
    mock_resource = MagicMock()
    mock_service.resource.return_value = mock_resource

    mock_request = MagicMock()
    mock_request.execute.return_value = {"key": "value"}

    # Set up the MagicMock for method
    mock_resource.method.return_value = mock_request

    result = execute_google_api_call(
        "service_name", "version", "resource", "method", arg1="value1"
    )

    mock_resource.method.assert_called_once_with(arg1="value1")
    assert result == ({"key": "value"}, set())


@patch("integrations.google_workspace.google_service.convert_kwargs_to_camel_case")
@patch("integrations.google_workspace.google_service.get_google_service")
@patch("integrations.google_workspace.google_service.get_google_api_command_parameters")
def test_execute_google_api_call_when_paginate_is_true(
    mock_get_google_api_command_parameters,
    mock_get_google_service,
    mock_convert_kwargs_to_camel_case,
):
    mock_get_google_api_command_parameters.return_value = ["arg1"]
    mock_convert_kwargs_to_camel_case.return_value = {"arg1": "value1"}

    mock_service = MagicMock()
    mock_get_google_service.return_value = mock_service

    # Set up the MagicMock for resource
    mock_resource = MagicMock()
    mock_service.resource.return_value = mock_resource

    # Set up the MagicMock for request
    mock_request1 = MagicMock()
    mock_request1.execute.return_value = {
        "resource": ["value1", "value2"],
        "nextPageToken": "token",
    }

    mock_request2 = MagicMock()
    mock_request2.execute.return_value = {"resource": ["value3"], "nextPageToken": None}

    # Set up the MagicMock for method
    mock_method = MagicMock()
    mock_method.return_value = mock_request1
    mock_resource.method = mock_method

    # Set up the MagicMock for method_next
    mock_method_next = MagicMock()
    mock_resource.method_next = mock_method_next

    # Create a list of mock requests for pagination
    mock_requests = [mock_request2]

    def side_effect(*args):
        if mock_requests:
            return mock_requests.pop(0)
        else:
            return None

    mock_method_next.side_effect = side_effect

    result = execute_google_api_call(
        "service_name", "version", "resource", "method", paginate=True, arg1="value1"
    )

    assert result == (["value1", "value2", "value3"], set())
    mock_resource.method.assert_called_once_with(arg1="value1")
    mock_resource.method_next.assert_any_call(
        mock_request1, {"resource": ["value1", "value2"], "nextPageToken": "token"}
    )
    assert mock_method_next.call_count == 2


@patch("integrations.google_workspace.google_service.convert_kwargs_to_camel_case")
@patch("integrations.google_workspace.google_service.get_google_service")
@patch("integrations.google_workspace.google_service.get_google_api_command_parameters")
def test_execute_google_api_call_with_nested_resource_path(
    mock_get_google_api_command_parameters,
    mock_get_google_service,
    mock_convert_kwargs_to_camel_case,
):
    mock_get_google_api_command_parameters.return_value = ["arg1"]
    mock_convert_kwargs_to_camel_case.return_value = {"arg1": "value1"}

    mock_service = MagicMock()
    mock_get_google_service.return_value = mock_service

    # Set up the MagicMock for resource
    mock_resource1 = MagicMock()
    mock_resource2 = MagicMock()
    mock_resource1.resource2.return_value = mock_resource2
    mock_service.resource1.return_value = mock_resource1

    # Set up the MagicMock for method
    mock_method = MagicMock()
    mock_resource2.method.return_value = mock_method

    mock_method.execute.return_value = "result"

    result = execute_google_api_call(
        "service_name", "version", "resource1.resource2", "method", arg1="value1"
    )

    mock_resource2.method.assert_called_once_with(arg1="value1")
    assert result == ("result", set())


@patch("integrations.google_workspace.google_service.convert_kwargs_to_camel_case")
@patch("integrations.google_workspace.google_service.get_google_service")
@patch("integrations.google_workspace.google_service.get_google_api_command_parameters")
def test_execute_google_api_call_with_nested_resource_path_throws_error(
    mock_get_google_api_command_parameters,
    mock_get_google_service,
    mock_convert_kwargs_to_camel_case,
):
    mock_get_google_api_command_parameters.return_value = ["arg1"]
    mock_convert_kwargs_to_camel_case.return_value = {"arg1": "value1"}

    mock_service = MagicMock()
    mock_get_google_service.return_value = mock_service

    mock_resource1 = MagicMock()
    mock_resource1.resource2.side_effect = AttributeError(
        "resource2 cannot be accessed"
    )
    mock_service.resource1.return_value = mock_resource1

    with pytest.raises(AttributeError) as e:
        execute_google_api_call(
            "service_name", "version", "resource1.resource2", "method", arg1="value1"
        )

    assert "Error accessing resource2 on resource object" in str(e.value)


@patch("integrations.google_workspace.google_service.convert_kwargs_to_camel_case")
@patch("integrations.google_workspace.google_service.get_google_service")
@patch("integrations.google_workspace.google_service.get_google_api_command_parameters")
@patch("integrations.google_workspace.google_service.getattr")
def test_execute_google_api_call_with_generic_exception_throws_attribute_error(
    mock_getattr,
    mock_get_google_api_command_parameters,
    mock_get_google_service,
    mock_convert_kwargs_to_camel_case,
):
    mock_get_google_api_command_parameters.return_value = ["arg1"]
    mock_convert_kwargs_to_camel_case.return_value = {"arg1": "value1"}

    mock_service = MagicMock()
    mock_get_google_service.getattr.return_value = mock_service
    mock_resource = MagicMock()
    mock_service.return_value = mock_resource

    mock_getattr.side_effect = [
        mock_resource,
        AttributeError("method cannot be accessed"),
    ]

    with pytest.raises(AttributeError) as e:
        execute_google_api_call(
            "service_name", "version", "resource", "method", arg1="value1"
        )

    assert (
        "Error executing API method method. Exception: method cannot be accessed"
        in str(e.value)
    )


def test_get_google_api_command_parameters_returns_correct_parameters():
    mock_resource = MagicMock()
    mock_method = MagicMock()
    mock_method.__doc__ = """
Args:
    arg1: Description of arg1.
    arg2: Description of arg2.

Returns:
    Some return value.
    """
    mock_resource.method = mock_method

    result = get_google_api_command_parameters(mock_resource, "method")

    assert result == ["fields", "arg1", "arg2"]
