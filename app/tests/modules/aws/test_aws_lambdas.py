from unittest.mock import patch, MagicMock
from modules.aws import lambdas


def test_aws_lambdas_command_handles_empty_command():
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ""
    logger = MagicMock()

    lambdas.command_handler(client, body, respond, args, logger)

    respond.assert_called_once_with(
        "Invalid command. Type `/aws lambda help` for more information."
    )
    logger.info.assert_not_called()


def test_aws_lambdas_command_handles_help_command():
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["help"]
    logger = MagicMock()

    lambdas.command_handler(client, body, respond, args, logger)

    respond.assert_called_once_with(lambdas.help_text)
    logger.info.assert_not_called()


@patch("integrations.aws.lambdas.list_functions")
def test_aws_lambdas_command_handles_functions_command(mock_list_functions):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["functions"]
    logger = MagicMock()

    mock_list_functions.return_value = [{"FunctionName": "test-function"}]

    lambdas.command_handler(client, body, respond, args, logger)

    respond.assert_any_call("Fetching Lambda functions...")
    respond.assert_any_call("Lambda functions found:\n\n • test-function")
    logger.info.assert_called_once_with([{"FunctionName": "test-function"}])


@patch("integrations.aws.lambdas.list_layers")
def test_aws_lambdas_command_handles_layers_command(mock_list_layers):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["layers"]
    logger = MagicMock()

    mock_list_layers.return_value = [
        {
            "LayerName": "aws-sentinel-connector-layer",
            "LatestMatchingVersion": {"Version": 163},
        }
    ]

    lambdas.command_handler(client, body, respond, args, logger)

    respond.assert_any_call("Fetching Lambda layers...")
    respond.assert_any_call(
        "Lambda layers found:\n\n • aws-sentinel-connector-layer <latest version: 163>"
    )
    logger.info.assert_called_once_with(
        [
            {
                "LayerName": "aws-sentinel-connector-layer",
                "LatestMatchingVersion": {"Version": 163},
            }
        ]
    )


@patch("integrations.aws.lambdas.list_functions")
def test_request_list_functions_handles_empty_response(mock_list_functions):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    logger = MagicMock()

    mock_list_functions.return_value = []

    lambdas.request_list_functions(client, body, respond, logger)

    respond.assert_any_call("Fetching Lambda functions...")
    logger.info.assert_not_called()


@patch("integrations.aws.lambdas.list_functions")
def test_request_list_functions_handles_non_empty_response(mock_list_functions):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    logger = MagicMock()

    mock_list_functions.return_value = [{"FunctionName": "test-function"}]

    lambdas.request_list_functions(client, body, respond, logger)

    respond.assert_any_call("Fetching Lambda functions...")
    respond.assert_any_call("Lambda functions found:\n\n • test-function")
    logger.info.assert_called_once_with([{"FunctionName": "test-function"}])


@patch("integrations.aws.lambdas.list_layers")
def test_request_list_layers_handles_empty_response(mock_list_layers):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    logger = MagicMock()

    mock_list_layers.return_value = []

    lambdas.request_list_layers(client, body, respond, logger)

    respond.assert_any_call("Fetching Lambda layers...")
    respond.assert_any_call("Lambda layers management is currently disabled.")
    logger.info.assert_not_called()


@patch("integrations.aws.lambdas.list_layers")
def test_request_list_layers_handles_non_empty_response(mock_list_layers):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    logger = MagicMock()

    mock_list_layers.return_value = [
        {
            "LayerName": "aws-sentinel-connector-layer",
            "LatestMatchingVersion": {"Version": 163},
        }
    ]

    lambdas.request_list_layers(client, body, respond, logger)

    respond.assert_any_call("Fetching Lambda layers...")
    respond.assert_any_call(
        "Lambda layers found:\n\n • aws-sentinel-connector-layer <latest version: 163>"
    )
    logger.info.assert_called_once_with(
        [
            {
                "LayerName": "aws-sentinel-connector-layer",
                "LatestMatchingVersion": {"Version": 163},
            }
        ]
    )
