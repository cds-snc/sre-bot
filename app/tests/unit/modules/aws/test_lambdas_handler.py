"""Unit tests for AWS Lambda handler."""

import pytest
from unittest.mock import MagicMock, patch

from modules.aws import lambdas


@pytest.fixture
def make_command():
    """Factory for creating command arguments."""

    def _make(action: str = ""):
        return [action] if action else []

    return _make


@pytest.mark.unit
def test_should_show_help_when_empty_command(make_command):
    """Test command_handler responds with help for empty command."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = make_command("")

    # Act
    lambdas.command_handler(client, body, respond, args)

    # Assert
    respond.assert_called_once_with(
        "Invalid command. Type `/aws lambda help` for more information."
    )


@pytest.mark.unit
def test_should_respond_help_text_when_help_command(make_command):
    """Test command_handler responds with help text."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = make_command("help")

    # Act
    lambdas.command_handler(client, body, respond, args)

    # Assert
    respond.assert_called_once_with(lambdas.help_text)


@pytest.mark.unit
def test_should_respond_aide_text_when_aide_command(make_command):
    """Test command_handler responds with help text for French command."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = make_command("aide")

    # Act
    lambdas.command_handler(client, body, respond, args)

    # Assert
    respond.assert_called_once_with(lambdas.help_text)


@pytest.mark.unit
@patch("modules.aws.lambdas.request_list_functions")
def test_should_delegate_functions_command(mock_request_functions, make_command):
    """Test command_handler delegates functions command."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = make_command("functions")

    # Act
    lambdas.command_handler(client, body, respond, args)

    # Assert
    mock_request_functions.assert_called_once_with(client, body, respond)


@pytest.mark.unit
@patch("modules.aws.lambdas.request_list_functions")
def test_should_delegate_function_singular_command(
    mock_request_functions, make_command
):
    """Test command_handler delegates function (singular) command."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = make_command("function")

    # Act
    lambdas.command_handler(client, body, respond, args)

    # Assert
    mock_request_functions.assert_called_once_with(client, body, respond)


@pytest.mark.unit
@patch("modules.aws.lambdas.request_list_layers")
def test_should_delegate_layers_command(mock_request_layers, make_command):
    """Test command_handler delegates layers command."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = make_command("layers")

    # Act
    lambdas.command_handler(client, body, respond, args)

    # Assert
    mock_request_layers.assert_called_once_with(client, body, respond)


@pytest.mark.unit
@patch("modules.aws.lambdas.request_list_layers")
def test_should_delegate_layer_singular_command(mock_request_layers, make_command):
    """Test command_handler delegates layer (singular) command."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = make_command("layer")

    # Act
    lambdas.command_handler(client, body, respond, args)

    # Assert
    mock_request_layers.assert_called_once_with(client, body, respond)


@pytest.mark.unit
def test_should_show_error_for_invalid_command(make_command):
    """Test command_handler shows error for invalid command."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["invalid-command"]

    # Act
    lambdas.command_handler(client, body, respond, args)

    # Assert
    respond.assert_called_once_with(
        "Invalid command. Type `/aws lambda help` for more information."
    )


@pytest.mark.unit
@patch("modules.aws.lambdas.aws_lambdas.list_functions")
def test_should_list_functions_successfully(mock_list_functions):
    """Test request_list_functions lists Lambda functions."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    mock_list_functions.return_value = [
        {"FunctionName": "test-function-1"},
        {"FunctionName": "test-function-2"},
    ]

    # Act
    lambdas.request_list_functions(client, body, respond)

    # Assert
    respond.assert_any_call("Fetching Lambda functions...")
    assert respond.call_count == 2
    second_call = respond.call_args_list[1][0][0]
    assert "test-function-1" in second_call
    assert "test-function-2" in second_call


@pytest.mark.unit
@patch("modules.aws.lambdas.aws_lambdas.list_functions")
def test_should_show_disabled_message_when_no_functions(mock_list_functions):
    """Test request_list_functions shows disabled message when empty."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    mock_list_functions.return_value = []

    # Act
    lambdas.request_list_functions(client, body, respond)

    # Assert
    respond.assert_any_call("Fetching Lambda functions...")
    respond.assert_any_call("Lambda functions management is currently disabled.")


@pytest.mark.unit
@patch("modules.aws.lambdas.aws_lambdas.list_functions")
def test_should_log_functions_count(mock_list_functions):
    """Test request_list_functions logs function count."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    mock_list_functions.return_value = [
        {"FunctionName": "test-function-1"},
        {"FunctionName": "test-function-2"},
        {"FunctionName": "test-function-3"},
    ]

    # Act
    lambdas.request_list_functions(client, body, respond)

    # Assert
    mock_list_functions.assert_called_once()
    respond.assert_called()


@pytest.mark.unit
@patch("modules.aws.lambdas.aws_lambdas.list_layers")
def test_should_list_layers_successfully(mock_list_layers):
    """Test request_list_layers lists Lambda layers."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    mock_list_layers.return_value = [
        {
            "LayerName": "test-layer-1",
            "LatestMatchingVersion": {"Version": 1},
        },
        {
            "LayerName": "test-layer-2",
            "LatestMatchingVersion": {"Version": 2},
        },
    ]

    # Act
    lambdas.request_list_layers(client, body, respond)

    # Assert
    respond.assert_any_call("Fetching Lambda layers...")
    assert respond.call_count == 2
    second_call = respond.call_args_list[1][0][0]
    assert "test-layer-1" in second_call
    assert "test-layer-2" in second_call


@pytest.mark.unit
@patch("modules.aws.lambdas.aws_lambdas.list_layers")
def test_should_show_disabled_message_when_no_layers(mock_list_layers):
    """Test request_list_layers shows disabled message when empty."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    mock_list_layers.return_value = []

    # Act
    lambdas.request_list_layers(client, body, respond)

    # Assert
    respond.assert_any_call("Fetching Lambda layers...")
    respond.assert_any_call("Lambda layers management is currently disabled.")


@pytest.mark.unit
@patch("modules.aws.lambdas.aws_lambdas.list_layers")
def test_should_format_layer_version_correctly(mock_list_layers):
    """Test request_list_layers formats layer version correctly."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    mock_list_layers.return_value = [
        {
            "LayerName": "my-custom-layer",
            "LatestMatchingVersion": {"Version": 42},
        }
    ]

    # Act
    lambdas.request_list_layers(client, body, respond)

    # Assert
    second_call = respond.call_args_list[1][0][0]
    assert "my-custom-layer" in second_call
    assert "latest version: 42" in second_call
