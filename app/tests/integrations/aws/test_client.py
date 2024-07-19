import os
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
from unittest.mock import MagicMock, patch
from integrations.aws import client as aws_client

ROLE_ARN = "test_role_arn"


@patch("integrations.aws.client.logger")
def test_handle_aws_api_errors_catches_botocore_error(mock_logger):
    mock_func = MagicMock(side_effect=BotoCoreError())
    mock_func.__name__ = "mock_func_name"
    mock_func.__module__ = "mock_module"
    decorated_func = aws_client.handle_aws_api_errors(mock_func)

    result = decorated_func()

    assert result is False
    mock_func.assert_called_once()
    mock_logger.error.assert_called_once_with(
        "mock_module.mock_func_name:BotoCore error: An unspecified error occurred"
    )
    mock_logger.info.assert_not_called()


@patch("integrations.aws.client.logger")
def test_handle_aws_api_errors_catches_client_error_resource_not_found(mock_logger):
    mock_func = MagicMock(
        side_effect=ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}}, "operation_name"
        )
    )
    mock_func.__name__ = "mock_func_name"
    mock_func.__module__ = "mock_module"
    decorated_func = aws_client.handle_aws_api_errors(mock_func)

    result = decorated_func()

    assert result is False
    mock_func.assert_called_once()
    mock_logger.warning.assert_called_once_with(
        "mock_module.mock_func_name: An error occurred (ResourceNotFoundException) when calling the operation_name operation: Unknown"
    )
    mock_logger.error.assert_not_called()
    mock_logger.info.assert_not_called()


@patch("integrations.aws.client.logger")
def test_handle_aws_api_errors_catches_client_error_other(mock_logger):
    mock_func = MagicMock(
        side_effect=ClientError({"Error": {"Code": "OtherError"}}, "operation_name")
    )
    mock_func.__name__ = "mock_func_name"
    mock_func.__module__ = "mock_module"
    decorated_func = aws_client.handle_aws_api_errors(mock_func)

    result = decorated_func()

    assert result is False
    mock_func.assert_called_once()
    mock_logger.error.assert_called_once_with(
        "mock_module.mock_func_name: An error occurred (OtherError) when calling the operation_name operation: Unknown"
    )
    mock_logger.info.assert_not_called()


@patch("integrations.aws.client.logger")
def test_handle_aws_api_errors_catches_exception(mock_logger):
    mock_func = MagicMock(side_effect=Exception("Exception message"))
    mock_func.__name__ = "mock_func_name"
    mock_func.__module__ = "mock_module"
    decorated_func = aws_client.handle_aws_api_errors(mock_func)

    result = decorated_func()

    assert result is False
    mock_func.assert_called_once()
    mock_logger.error.assert_called_once_with(
        "mock_module.mock_func_name: Exception message"
    )
    mock_logger.info.assert_not_called()


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
def test_assume_role_client_returns_credentials(mock_boto3_client):
    mock_sts_client = MagicMock()
    mock_boto3_client.return_value = mock_sts_client

    mock_sts_client.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "test_access_key_id",
            "SecretAccessKey": "test_secret_access_key",
            "SessionToken": "test_session_token",
        }
    }

    credentials = aws_client.assume_role_client("test_role_arn")

    mock_boto3_client.assert_called_once_with("sts")
    mock_sts_client.assume_role.assert_called_once_with(
        RoleArn="test_role_arn", RoleSessionName="AssumeRoleSession1"
    )
    expected_credentials = {
        "AccessKeyId": "test_access_key_id",
        "SecretAccessKey": "test_secret_access_key",
        "SessionToken": "test_session_token",
    }
    assert credentials == expected_credentials


@patch("integrations.aws.client.assume_role_client")
@patch("integrations.aws.client.boto3.client")
def test_get_aws_service_client_assumes_role(mock_boto3_client, mock_assume_role):
    mock_client = MagicMock()
    mock_boto3_client.return_value = mock_client

    config = {"role_arn": "test_role_arn"}

    mock_assume_role.return_value = {
        "AccessKeyId": "test_access_key_id",
        "SecretAccessKey": "test_secret_access_key",
        "SessionToken": "test_session_token",
    }

    client = aws_client.get_aws_service_client("service_name", **config)

    mock_assume_role.assert_called_once_with("test_role_arn")
    mock_boto3_client.assert_called_once_with(
        "service_name",
        aws_access_key_id="test_access_key_id",
        aws_secret_access_key="test_secret_access_key",
        aws_session_token="test_session_token",
    )
    assert client == mock_client


@patch("integrations.aws.client.boto3.client")
def test_get_aws_service_client_no_role(mock_boto3_client):
    mock_client = MagicMock()
    mock_boto3_client.return_value = mock_client

    client = aws_client.get_aws_service_client("service_name")

    mock_boto3_client.assert_called_once_with("service_name")
    assert client == mock_client


@patch.dict(os.environ, {"AWS_ORG_ACCOUNT_ROLE_ARN": "test_role_arn"})
@patch("integrations.aws.client.paginator")
@patch("integrations.aws.client.convert_kwargs_to_pascal_case")
@patch("integrations.aws.client.get_aws_service_client")
def test_execute_aws_api_call_non_paginated(
    mock_get_aws_service_client, mock_convert_kwargs_to_pascal_case, mock_paginator
):
    mock_client = MagicMock()
    mock_get_aws_service_client.return_value = mock_client
    mock_convert_kwargs_to_pascal_case.return_value = {"Arg1": "value1"}
    mock_method = MagicMock()
    mock_method.return_value = {"key": "value"}
    mock_client.some_method = mock_method

    result = aws_client.execute_aws_api_call(
        "service_name", "some_method", arg1="value1"
    )

    mock_get_aws_service_client.assert_called_once_with(
        "service_name", None, region_name="ca-central-1"
    )
    mock_method.assert_called_once_with(Arg1="value1")
    assert result == {"key": "value"}
    mock_convert_kwargs_to_pascal_case.assert_called_once_with({"arg1": "value1"})
    mock_paginator.assert_not_called()


@patch.dict(os.environ, {"AWS_ORG_ACCOUNT_ROLE_ARN": "test_role_arn"})
@patch("integrations.aws.client.convert_kwargs_to_pascal_case")
@patch("integrations.aws.client.get_aws_service_client")
@patch("integrations.aws.client.paginator")
def test_execute_aws_api_call_paginated(
    mock_paginator, mock_get_aws_service_client, mock_convert_kwargs_to_pascal_case
):
    mock_client = MagicMock()
    mock_get_aws_service_client.return_value = mock_client
    mock_convert_kwargs_to_pascal_case.return_value = {"Arg1": "value1"}
    mock_paginator.return_value = ["value1", "value2", "value3"]

    result = aws_client.execute_aws_api_call(
        "service_name", "some_method", paginated=True, arg1="value1"
    )

    mock_get_aws_service_client.assert_called_once_with(
        "service_name", None, region_name="ca-central-1"
    )
    mock_paginator.assert_called_once_with(
        mock_client, "some_method", None, Arg1="value1"
    )
    mock_convert_kwargs_to_pascal_case.assert_called_once_with({"arg1": "value1"})
    assert result == ["value1", "value2", "value3"]


@patch("integrations.aws.client.paginator")
@patch("integrations.aws.client.convert_kwargs_to_pascal_case")
@patch("integrations.aws.client.get_aws_service_client")
def test_execute_aws_api_call_with_role_arn(
    mock_get_aws_service_client, mock_convert_kwargs_to_pascal_case, mock_paginator
):
    mock_client = MagicMock()
    mock_get_aws_service_client.return_value = mock_client
    mock_convert_kwargs_to_pascal_case.return_value = {"Arg1": "value1"}
    mock_method = MagicMock()
    mock_method.return_value = {"key": "value"}
    mock_client.some_method = mock_method

    result = aws_client.execute_aws_api_call(
        "service_name", "some_method", role_arn="test_role_arn", arg1="value1"
    )

    mock_get_aws_service_client.assert_called_once_with(
        "service_name", "test_role_arn", region_name="ca-central-1"
    )
    mock_method.assert_called_once_with(Arg1="value1")
    assert result == {"key": "value"}
    mock_paginator.assert_not_called()
    mock_convert_kwargs_to_pascal_case.assert_called_once_with({"arg1": "value1"})
