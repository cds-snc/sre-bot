"""Unit tests for the next Google Service module."""

from json import JSONDecodeError
from unittest.mock import MagicMock, call, patch

import pytest
from googleapiclient.errors import Error, HttpError  # type: ignore
from integrations.google_next import service


@patch("integrations.google_next.service.SRE_BOT_EMAIL", new="default@email.com")
@patch("integrations.google_next.service.build")
@patch("integrations.google_next.service.service_account")
def test_get_google_service_returns_build_object(mock_service_account, build_mock):
    """
    Test case to verify that the function returns a build object.
    """
    creds_mock = MagicMock()
    creds_with_subject_mock = MagicMock()
    creds_with_scopes_mock = MagicMock()

    mock_service_account.Credentials.from_service_account_info.return_value = creds_mock
    creds_mock.with_subject.return_value = creds_with_subject_mock
    creds_with_subject_mock.with_scopes.return_value = creds_with_scopes_mock

    service.get_google_service("drive", "v3")
    creds_mock.with_subject.assert_called_once_with("default@email.com")
    creds_mock.with_scopes.assert_not_called()
    build_mock.assert_called_once_with(
        "drive",
        "v3",
        credentials=creds_with_subject_mock,
        cache_discovery=False,
    )


@patch("integrations.google_next.service.build")
@patch("integrations.google_next.service.service_account")
def test_get_google_service_with_delegated_user_email(mock_service_account, build_mock):
    """
    Test case to verify that the function works correctly with a delegated user email.
    """
    creds_mock = MagicMock()
    creds_with_subject_mock = MagicMock()
    creds_with_scopes_mock = MagicMock()

    mock_service_account.Credentials.from_service_account_info.return_value = creds_mock
    creds_mock.with_subject.return_value = creds_with_subject_mock
    creds_with_subject_mock.with_scopes.return_value = creds_with_scopes_mock

    service.get_google_service("drive", "v3", delegated_user_email="test@test.com")
    creds_mock.with_subject.assert_called_once_with("test@test.com")
    creds_mock.with_scopes.assert_not_called()
    build_mock.assert_called_once_with(
        "drive",
        "v3",
        credentials=creds_with_subject_mock,
        cache_discovery=False,
    )


@patch("integrations.google_next.service.SRE_BOT_EMAIL", new="default@email.com")
@patch("integrations.google_next.service.build")
@patch("integrations.google_next.service.service_account")
def test_get_google_service_with_scopes(mock_service_account, build_mock):
    """
    Test case to verify that the function works correctly with scopes.
    """
    creds_mock = MagicMock()
    creds_with_subject_mock = MagicMock()
    creds_with_scopes_mock = MagicMock()

    mock_service_account.Credentials.from_service_account_info.return_value = creds_mock
    creds_mock.with_subject.return_value = creds_with_subject_mock
    creds_with_subject_mock.with_scopes.return_value = creds_with_scopes_mock
    service.get_google_service("drive", "v3", scopes=["scope1", "scope2"])
    creds_mock.with_subject.assert_called_once_with("default@email.com")
    creds_with_subject_mock.with_scopes.assert_called_once_with(["scope1", "scope2"])
    build_mock.assert_called_once_with(
        "drive",
        "v3",
        credentials=creds_with_scopes_mock,
        cache_discovery=False,
    )


@patch.object(
    service,
    "GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
    new="",
)
def test_get_google_service_raises_exception_if_credentials_json_not_set():
    """
    Test case to verify that the function raises an exception if:
     - GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is not set.
    """
    with pytest.raises(ValueError) as e:
        service.get_google_service("drive", "v3")
    assert "Credentials JSON not set" in str(e.value)


@patch.object(
    service,
    "GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
    new="invalid",
)
@patch("integrations.google_next.service.service_account")
def test_get_google_service_raises_exception_if_credentials_json_is_invalid(
    mocked_service_account,
):
    """
    Test case to verify that the function raises an exception if:
     - GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is invalid.
    """
    # mocked_service_account = MagicMock()
    mocked_service_account.Credentials.from_service_account_info.side_effect = (
        JSONDecodeError("Invalid credentials JSON", "", 0)
    )
    with pytest.raises(JSONDecodeError) as e:
        service.get_google_service("drive", "v3")
    assert "Invalid credentials JSON" in str(e.value)


@patch("integrations.google_next.service.logger")
def test_handle_google_api_errors_catches_http_error(mocked_logger: MagicMock):
    mock_resp = MagicMock()
    mock_resp.status = "400"
    mock_resp.reason = "Bad Request"
    mock_func = MagicMock(side_effect=HttpError(resp=mock_resp, content=b""))
    mock_func.__name__ = "mock_func"
    mock_func.__module__ = "mock_module"
    decorated_func = service.handle_google_api_errors(mock_func)

    with pytest.raises(HttpError, match='<HttpError 400 "Bad Request">'):
        result = decorated_func()
        assert result is None

    mocked_logger.error.assert_called_once_with(
        "google_api_http_error",
        function="mock_func",
        module="mock_module",
        service="google_api",
        error='<HttpError 400 "Bad Request">',
    )


@patch("integrations.google_next.service.logger")
def test_handle_google_api_errors_catches_http_warning(
    mocked_logger: MagicMock,
):
    mock_resp = MagicMock()
    mock_resp.status = "404"
    mock_resp.reason = "Resource Not Found: userKey"
    mock_resp.getheaders.return_value = {}
    mock_func = MagicMock(side_effect=HttpError(resp=mock_resp, content=b""))
    mock_func.__name__ = "mock_func"
    mock_func.__module__ = "mock_module"
    decorated_func = service.handle_google_api_errors(mock_func)

    with pytest.raises(
        HttpError, match='<HttpError 404 "Resource Not Found: userKey">'
    ):
        result = decorated_func(arg="value")
        assert result is None

    mocked_logger.warning.assert_called_once_with(
        "google_api_http_warning",
        function="mock_func",
        module="mock_module",
        service="google_api",
        arguments="(arg=value)",
        error='<HttpError 404 "Resource Not Found: userKey">',
    )


@patch("integrations.google_next.service.logger")
def test_handle_google_api_errors_catches_error(mocked_logging: MagicMock):
    mock_func = MagicMock(side_effect=Error("Error message"))
    mock_func.__name__ = "mock_func"
    mock_func.__module__ = "mock_module"
    decorated_func = service.handle_google_api_errors(mock_func)

    with pytest.raises(Error, match="Error message"):
        result = decorated_func()
        assert result is None

    mock_func.assert_called_once()
    mocked_logging.error.assert_called_once_with(
        "google_api_generic_error",
        function="mock_func",
        module="mock_module",
        service="google_api",
        error="Error message",
        error_type="Error",
    )


@patch("integrations.google_next.service.logger")
def test_handle_google_api_errors_catches_exception(mocked_logging: MagicMock):
    mock_func = MagicMock(side_effect=Exception("Exception message"))
    mock_func.__name__ = "mock_func"
    mock_func.__module__ = "mock_module"
    decorated_func = service.handle_google_api_errors(mock_func)

    with pytest.raises(Exception, match="Exception message"):
        result = decorated_func()
        assert result is None

    mock_func.assert_called_once()
    mocked_logging.error.assert_called_once_with(
        "google_api_generic_error",
        function="mock_func",
        module="mock_module",
        service="google_api",
        error="Exception message",
        error_type="Exception",
    )

    mock_func = MagicMock(side_effect=Exception("timed out"))
    mock_func.__name__ = "list_groups"
    mock_func.__module__ = "mock_module"
    decorated_func = service.handle_google_api_errors(mock_func)

    with pytest.raises(Exception, match="timed out"):
        result = decorated_func()
        assert result is None

    mock_func.assert_called_once()
    mocked_logging.error.assert_called_with(
        "google_api_generic_error",
        function="list_groups",
        module="mock_module",
        service="google_api",
        error="timed out",
        error_type="Exception",
    )

    mock_func = MagicMock(side_effect=Exception("timed out"))
    mock_func.__name__ = "get_user"
    mock_func.__module__ = "mock_module"
    decorated_func = service.handle_google_api_errors(mock_func)

    with pytest.raises(Exception, match="timed out"):
        result = decorated_func("arg1", "arg2", a="b")
        assert result is None

    mock_func.assert_called_once()
    mocked_logging.error.assert_called_with(
        "google_api_generic_error",
        function="get_user",
        module="mock_module",
        service="google_api",
        error="timed out",
        error_type="Exception",
    )


def test_handle_google_api_errors_passes_through_return_value():
    mock_func = MagicMock(return_value="test")
    mock_func.__name__ = "mock_func"
    mock_func.__module__ = "mock_module"
    decorated_func = service.handle_google_api_errors(mock_func)

    result = decorated_func()

    assert result == "test"
    mock_func.assert_called_once()


def test_execute_google_api_call_raises_exception_if_service_is_none():
    with pytest.raises(ValueError) as e:
        service.execute_google_api_call(None, "resource", "method")
    assert "Service not provided" in str(e.value)


@patch("integrations.google_next.service.getattr")
def test_execute_google_api_call_calls_getattr_with_service_and_resource(
    mock_getattr: MagicMock,
):
    mock_service = MagicMock()
    mock_service.resource = MagicMock()

    service.execute_google_api_call(mock_service, "resource", "method")

    calls = [
        call(mock_service, "resource"),
        call(mock_service.resource(), "method")(),
    ]
    mock_getattr.assert_has_calls(calls)


def test_execute_google_api_call_when_paginate_is_false():

    mock_service = MagicMock()

    # Set up the MagicMock for resource
    mock_resource = MagicMock()
    mock_service.resource.return_value = mock_resource

    mock_request = MagicMock()
    mock_request.execute.return_value = {"key": "value"}

    # Set up the MagicMock for method
    mock_resource.method.return_value = mock_request

    result = service.execute_google_api_call(
        mock_service, "resource", "method", arg1="value1"
    )

    mock_resource.method.assert_called_once_with(arg1="value1")
    assert result == ({"key": "value"})


def test_execute_google_api_call_when_paginate_is_true():

    mock_service = MagicMock()

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

    result = service.execute_google_api_call(
        mock_service, "resource", "method", paginate=True, arg1="value1"
    )

    assert result == (["value1", "value2", "value3"])
    mock_resource.method.assert_called_once_with(arg1="value1")
    mock_resource.method_next.assert_any_call(
        mock_request1, {"resource": ["value1", "value2"], "nextPageToken": "token"}
    )
    assert mock_method_next.call_count == 2


def test_execute_google_api_call_with_nested_resource_path():

    mock_service = MagicMock()

    # Set up the MagicMock for resource
    mock_resource1 = MagicMock()
    mock_resource2 = MagicMock()
    mock_resource1.resource2.return_value = mock_resource2
    mock_service.resource1.return_value = mock_resource1

    # Set up the MagicMock for method
    mock_method = MagicMock()
    mock_resource2.method.return_value = mock_method

    mock_method.execute.return_value = "result"

    result = service.execute_google_api_call(
        mock_service, "resource1.resource2", "method", arg1="value1"
    )

    mock_resource2.method.assert_called_once_with(arg1="value1")
    assert result == ("result")


def test_execute_google_api_call_with_nested_resource_path_throws_error():

    mock_service = MagicMock()

    mock_resource1 = MagicMock()
    mock_resource1.resource2.side_effect = AttributeError(
        "resource2 cannot be accessed"
    )
    mock_service.resource1.return_value = mock_resource1

    with pytest.raises(AttributeError) as e:
        service.execute_google_api_call(
            mock_service, "resource1.resource2", "method", arg1="value1"
        )

    assert "Error accessing resource2 on resource object" in str(e.value)


@patch("integrations.google_next.service.getattr")
def test_execute_google_api_call_with_generic_exception_throws_attribute_error(
    mock_getattr,
):

    mock_service = MagicMock()
    mock_resource = MagicMock()
    mock_service.return_value = mock_resource

    mock_getattr.side_effect = [
        mock_resource,
        AttributeError("method cannot be accessed"),
    ]

    with pytest.raises(AttributeError) as e:
        service.execute_google_api_call(
            mock_service, "resource", "method", arg1="value1"
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

    result = service.get_google_api_command_parameters(mock_resource, "method")

    assert result == ["fields", "arg1", "arg2"]
