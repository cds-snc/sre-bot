import os
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
from unittest.mock import MagicMock, patch
from integrations.aws import client as aws_client
import pytest

ROLE_ARN = "test_role_arn"


@patch("logging.error")
def test_handle_aws_api_errors_catches_botocore_error(mocked_logging_error):
    mock_func = MagicMock(side_effect=BotoCoreError())
    mock_func.__name__ = "mock_func"
    decorated_func = aws_client.handle_aws_api_errors(mock_func)

    result = decorated_func()

    assert result is None
    mock_func.assert_called_once()
    mocked_logging_error.assert_called_once_with(
        "A BotoCore error occurred in function 'mock_func': An unspecified error occurred"
    )


@patch("logging.error")
def test_handle_aws_api_errors_catches_client_error(mocked_logging_error):
    mock_func = MagicMock(side_effect=ClientError({"Error": {}}, "operation_name"))
    mock_func.__name__ = "mock_func"
    decorated_func = aws_client.handle_aws_api_errors(mock_func)

    result = decorated_func()

    assert result is None
    mock_func.assert_called_once()
    mocked_logging_error.assert_called_once_with(
        "A ClientError occurred in function 'mock_func': An error occurred (Unknown) when calling the operation_name operation: Unknown"
    )


@patch("logging.error")
def test_handle_aws_api_errors_catches_exception(mocked_logging_error):
    mock_func = MagicMock(side_effect=Exception("Exception message"))
    mock_func.__name__ = "mock_func"
    decorated_func = aws_client.handle_aws_api_errors(mock_func)

    result = decorated_func()

    assert result is None
    mock_func.assert_called_once()
    mocked_logging_error.assert_called_once_with(
        "An unexpected error occurred in function 'mock_func': Exception message"
    )


def test_handle_aws_api_errors_passes_through_return_value():
    mock_func = MagicMock(return_value="test")
    decorated_func = aws_client.handle_aws_api_errors(mock_func)

    result = decorated_func()

    assert result == "test"
    mock_func.assert_called_once()


@patch("boto3.client")
def test_paginate_no_key(mock_boto3_client):
    """
    Test case to verify that the function works correctly when no keys are provided.
    """
    mock_paginator = MagicMock()
    mock_boto3_client.return_value.get_paginator.return_value = mock_paginator
    pages = [
        {"Key1": ["Value1", "Value2"], "Key2": ["Value3", "Value4"]},
        {"Key1": ["Value5", "Value6"]},
    ]
    mock_paginator.paginate.return_value = pages

    result = aws_client.paginator(mock_boto3_client.return_value, "operation")

    assert result == pages


@patch("boto3.client")
def test_paginate_single_key(mock_boto3_client):
    """
    Test case to verify that the function works correctly with a single key.
    """
    mock_paginator = MagicMock()
    mock_boto3_client.return_value.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [
        {"Key1": ["Value1", "Value2"], "Key2": ["Value3", "Value4"]},
        {"Key1": ["Value5", "Value6"]},
    ]

    result = aws_client.paginator(mock_boto3_client.return_value, "operation", ["Key1"])

    assert result == ["Value1", "Value2", "Value5", "Value6"]


@patch("boto3.client")
def test_paginate_multiple_keys(mock_boto3_client):
    """
    Test case to verify that the function works correctly with multiple keys.
    """
    mock_paginator = MagicMock()
    mock_boto3_client.return_value.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [
        {"Key1": ["Value1", "Value2"], "Key2": ["Value3", "Value4"]},
        {"Key1": ["Value5", "Value6"]},
    ]

    result = aws_client.paginator(
        mock_boto3_client.return_value, "operation", ["Key1", "Key2"]
    )

    assert result == ["Value1", "Value2", "Value3", "Value4", "Value5", "Value6"]


@patch("boto3.client")
def test_paginate_empty_page(mock_boto3_client):
    """
    Test case to verify that the function works correctly with an empty page.
    """
    mock_paginator = MagicMock()
    mock_boto3_client.return_value.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [{}, {"Key1": ["Value5", "Value6"]}]

    result = aws_client.paginator(mock_boto3_client.return_value, "operation", ["Key1"])

    assert result == ["Value5", "Value6"]


@patch("boto3.client")
def test_paginate_no_key_in_page(mock_client):
    """
    Test case to verify that the function works correctly when the key is not in the page.
    """
    mock_paginator = MagicMock()
    mock_client.return_value.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [
        {"Key1": ["Value1", "Value2"]},
        {"Key3": ["Value5", "Value6"]},
    ]

    result = aws_client.paginator(mock_client, "operation", ["Key2"])

    assert result == []


@patch("boto3.client")
def test_assume_role_client(mock_boto3_client):
    mock_sts_client = MagicMock()
    mock_service_client = MagicMock()
    mock_boto3_client.side_effect = [mock_sts_client, mock_service_client]

    mock_sts_client.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "test_access_key_id",
            "SecretAccessKey": "test_secret_access_key",
            "SessionToken": "test_session_token",
        }
    }

    client = aws_client.assume_role_client("test_service", "test_role_arn")

    mock_boto3_client.assert_any_call("sts")
    mock_sts_client.assume_role.assert_called_once_with(
        RoleArn="test_role_arn", RoleSessionName="AssumeRoleSession1"
    )
    mock_boto3_client.assert_any_call(
        "test_service",
        aws_access_key_id="test_access_key_id",
        aws_secret_access_key="test_secret_access_key",
        aws_session_token="test_session_token",
    )
    assert client == mock_service_client


@patch("boto3.client")
def test_assume_role_client_raises_exception_on_error(mock_boto3_client):
    mock_sts_client = MagicMock()
    mock_boto3_client.return_value = mock_sts_client

    mock_sts_client.assume_role.side_effect = BotoCoreError

    with pytest.raises(BotoCoreError):
        aws_client.assume_role_client("test_service", "test_role_arn")

    mock_boto3_client.assert_called_once_with("sts")
    mock_sts_client.assume_role.assert_called_once_with(
        RoleArn="test_role_arn", RoleSessionName="AssumeRoleSession1"
    )


@patch.dict(os.environ, {"AWS_SSO_ROLE_ARN": "test_role_arn"})
@patch("integrations.aws.client.assume_role_client")
def test_execute_aws_api_call_non_paginated(mock_assume_role_client):
    mock_client = MagicMock()
    mock_assume_role_client.return_value = mock_client
    mock_method = MagicMock()
    mock_method.return_value = {"key": "value"}
    mock_client.some_method = mock_method

    result = aws_client.execute_aws_api_call(
        "service_name", "some_method", arg1="value1"
    )

    mock_assume_role_client.assert_called_once_with("service_name", "test_role_arn")
    mock_method.assert_called_once_with(arg1="value1")
    assert result == {"key": "value"}


@patch.dict(os.environ, {"AWS_SSO_ROLE_ARN": "test_role_arn"})
@patch("integrations.aws.client.assume_role_client")
@patch("integrations.aws.client.paginator")
def test_execute_aws_api_call_paginated(mock_paginator, mock_assume_role_client):
    mock_client = MagicMock()
    mock_assume_role_client.return_value = mock_client
    mock_paginator.return_value = ["value1", "value2", "value3"]

    result = aws_client.execute_aws_api_call(
        "service_name", "some_method", paginated=True, arg1="value1"
    )

    mock_assume_role_client.assert_called_once_with("service_name", "test_role_arn")
    mock_paginator.assert_called_once_with(mock_client, "some_method", arg1="value1")
    assert result == ["value1", "value2", "value3"]


@patch("integrations.aws.client.assume_role_client")
def test_execute_aws_api_call_with_role_arn(mock_assume_role_client):
    mock_client = MagicMock()
    mock_assume_role_client.return_value = mock_client
    mock_method = MagicMock()
    mock_method.return_value = {"key": "value"}
    mock_client.some_method = mock_method

    result = aws_client.execute_aws_api_call(
        "service_name", "some_method", role_arn="test_role_arn", arg1="value1"
    )

    mock_assume_role_client.assert_called_once_with("service_name", "test_role_arn")
    mock_method.assert_called_once_with(arg1="value1")
    assert result == {"key": "value"}


@patch.dict(os.environ, {"AWS_SSO_ROLE_ARN": "test_role_arn"})
@patch("integrations.aws.client.assume_role_client")
def test_execute_aws_api_call_raises_exception_on_error(mock_assume_role):
    mock_assume_role.side_effect = ValueError

    with pytest.raises(ValueError):
        aws_client.execute_aws_api_call("service_name", "some_method", arg1="value1")

    mock_assume_role.assert_called_once_with("service_name", "test_role_arn")


@patch.dict(os.environ, clear=True)
@patch("integrations.aws.client.assume_role_client")
def test_execute_aws_api_call_raises_exception_on_name_error(mock_assume_role):
    with pytest.raises(ValueError) as exc_info:
        aws_client.execute_aws_api_call("service_name", "some_method", arg1="value1")

    assert (
        str(exc_info.value)
        == "role_arn must be provided either as a keyword argument or as the AWS_SSO_ROLE_ARN environment variable"
    )
    mock_assume_role.assert_not_called()
