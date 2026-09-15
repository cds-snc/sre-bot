"""Unit tests for AWS Lambda handler."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from infrastructure.operations import OperationResult, OperationStatus
from modules.aws import lambdas
from packages.aws_platform.adapters.aws_lambda import LambdaAdapter

FUNCTIONS_FAILURE_TEXT = (
    "Failed to list Lambda functions. Please try again later.\n"
    "Impossible de lister les fonctions Lambda. Veuillez réessayer plus tard."
)
FUNCTIONS_EMPTY_TEXT = "No Lambda functions found.\nAucune fonction Lambda trouvée."
LAYERS_FAILURE_TEXT = (
    "Failed to list Lambda layers. Please try again later.\n"
    "Impossible de lister les couches Lambda. Veuillez réessayer plus tard."
)
LAYERS_EMPTY_TEXT = "No Lambda layers found.\nAucune couche Lambda trouvée."


@pytest.fixture
def make_command():
    """Factory for creating command arguments."""

    def _make(action: str = ""):
        return [action] if action else []

    return _make


@pytest.fixture
def lambda_adapter() -> Iterator[MagicMock]:
    """Patch the module's adapter factory with a spec'd double.

    Tests set each operation's OperationResult so assertions cover the handler's
    branching, not SDK transport; the factory mock is exposed as ``factory``.
    """
    adapter = MagicMock(spec=LambdaAdapter)
    with patch("modules.aws.lambdas.build_lambda_adapter", return_value=adapter) as factory:
        adapter.factory = factory
        yield adapter


@pytest.fixture
def mock_logger() -> Iterator[MagicMock]:
    """Patch the module logger so structured failure events can be inspected."""
    with patch("modules.aws.lambdas.logger") as logger:
        yield logger


def _logged(mock_logger: MagicMock, event: str) -> list[dict[str, Any]]:
    """Return the keyword arguments of every log call for ``event``, whether made on the logger or a bound child."""
    return [dict(entry.kwargs) for entry in mock_logger.mock_calls if entry.args[:1] == (event,)]


def _failure(status: OperationStatus) -> OperationResult[Any]:
    """Return a classified adapter failure carrying a distinctive code and message."""
    return OperationResult.error(status, message="lambda unavailable", error_code="SomeAwsException")


def _responses(respond: MagicMock) -> list[str]:
    """Return every text passed to respond, in call order."""
    return [entry.args[0] for entry in respond.call_args_list]


# -- command_handler routing ------------------------------------------------------


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
    respond.assert_called_once_with("Invalid command. Type `/aws lambda help` for more information.")


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
def test_should_delegate_function_singular_command(mock_request_functions, make_command):
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
    respond.assert_called_once_with("Invalid command. Type `/aws lambda help` for more information.")


# -- request_list_functions -------------------------------------------------------


@pytest.mark.unit
def test_should_list_functions_successfully(lambda_adapter: MagicMock) -> None:
    """A successful listing is announced then rendered with every function name in one message."""
    # Arrange
    respond = MagicMock()
    lambda_adapter.list_functions.return_value = OperationResult.success(
        data=[{"FunctionName": "test-function-1"}, {"FunctionName": "test-function-2"}]
    )

    # Act
    lambdas.request_list_functions(MagicMock(), MagicMock(), respond)

    # Assert
    responses = _responses(respond)
    assert responses[0] == "Fetching Lambda functions..."
    assert len(responses) == 2
    assert "test-function-1" in responses[1]
    assert "test-function-2" in responses[1]


@pytest.mark.unit
def test_should_log_functions_count(lambda_adapter: MagicMock, mock_logger: MagicMock) -> None:
    """The adapter is built and queried once per request, and the found count is logged."""
    # Arrange
    lambda_adapter.list_functions.return_value = OperationResult.success(
        data=[{"FunctionName": "test-function-1"}, {"FunctionName": "test-function-2"}, {"FunctionName": "f3"}]
    )

    # Act
    lambdas.request_list_functions(MagicMock(), MagicMock(), MagicMock())

    # Assert
    lambda_adapter.factory.assert_called_once_with()
    lambda_adapter.list_functions.assert_called_once_with()
    mock_logger.bind.assert_any_call(count=3)


@pytest.mark.unit
@pytest.mark.parametrize("status", [OperationStatus.TRANSIENT_ERROR, OperationStatus.UNAUTHORIZED])
def test_should_respond_failure_and_log_when_list_functions_fails(
    lambda_adapter: MagicMock, mock_logger: MagicMock, status: OperationStatus
) -> None:
    """A classified failure is logged with its classification and shown as a distinct bilingual failure, not an empty list."""
    # Arrange
    respond = MagicMock()
    lambda_adapter.list_functions.return_value = _failure(status)

    # Act
    lambdas.request_list_functions(MagicMock(), MagicMock(), respond)

    # Assert
    assert _responses(respond) == ["Fetching Lambda functions...", FUNCTIONS_FAILURE_TEXT]
    assert {"status": status.value, "error_code": "SomeAwsException", "error": "lambda unavailable"}.items() <= (
        _logged(mock_logger, "lambda_functions_lookup_failed")[0].items()
    )


@pytest.mark.unit
def test_should_respond_none_found_when_no_functions(lambda_adapter: MagicMock, mock_logger: MagicMock) -> None:
    """A successful empty listing gets the bilingual none-found message and logs no failure."""
    # Arrange
    respond = MagicMock()
    lambda_adapter.list_functions.return_value = OperationResult.success(data=[])

    # Act
    lambdas.request_list_functions(MagicMock(), MagicMock(), respond)

    # Assert
    assert _responses(respond) == ["Fetching Lambda functions...", FUNCTIONS_EMPTY_TEXT]
    assert _logged(mock_logger, "lambda_functions_lookup_failed") == []


@pytest.mark.unit
def test_should_propagate_unclassified_error_from_list_functions(lambda_adapter: MagicMock) -> None:
    """An error the adapter does not classify (an input error) propagates rather than being reported as a failure."""
    # Arrange
    respond = MagicMock()
    lambda_adapter.list_functions.side_effect = ClientError(
        {"Error": {"Code": "InvalidParameterValueException", "Message": "bad"}}, "ListFunctions"
    )

    # Act / Assert
    with pytest.raises(ClientError):
        lambdas.request_list_functions(MagicMock(), MagicMock(), respond)
    assert FUNCTIONS_FAILURE_TEXT not in _responses(respond)


# -- request_list_layers ----------------------------------------------------------


@pytest.mark.unit
def test_should_list_layers_successfully(lambda_adapter: MagicMock) -> None:
    """A successful listing is announced then rendered with every layer name in one message."""
    # Arrange
    respond = MagicMock()
    lambda_adapter.list_layers.return_value = OperationResult.success(
        data=[
            {"LayerName": "test-layer-1", "LatestMatchingVersion": {"Version": 1}},
            {"LayerName": "test-layer-2", "LatestMatchingVersion": {"Version": 2}},
        ]
    )

    # Act
    lambdas.request_list_layers(MagicMock(), MagicMock(), respond)

    # Assert
    responses = _responses(respond)
    assert responses[0] == "Fetching Lambda layers..."
    assert len(responses) == 2
    assert "test-layer-1" in responses[1]
    assert "test-layer-2" in responses[1]


@pytest.mark.unit
def test_should_format_layer_version_correctly(lambda_adapter: MagicMock) -> None:
    """Each layer line carries its latest matching version number."""
    # Arrange
    respond = MagicMock()
    lambda_adapter.list_layers.return_value = OperationResult.success(
        data=[{"LayerName": "my-custom-layer", "LatestMatchingVersion": {"Version": 42}}]
    )

    # Act
    lambdas.request_list_layers(MagicMock(), MagicMock(), respond)

    # Assert
    assert "my-custom-layer" in _responses(respond)[1]
    assert "latest version: 42" in _responses(respond)[1]


@pytest.mark.unit
def test_should_list_layer_without_latest_matching_version(lambda_adapter: MagicMock) -> None:
    """LatestMatchingVersion is optional in the Lambda API: such a layer is listed by name without a version suffix."""
    # Arrange
    respond = MagicMock()
    lambda_adapter.list_layers.return_value = OperationResult.success(
        data=[
            {"LayerName": "versionless-layer"},
            {"LayerName": "versioned-layer", "LatestMatchingVersion": {"Version": 7}},
        ]
    )

    # Act
    lambdas.request_list_layers(MagicMock(), MagicMock(), respond)

    # Assert
    rendered = _responses(respond)[1]
    versionless_line = next(line for line in rendered.splitlines() if "versionless-layer" in line)
    assert "latest version" not in versionless_line
    assert "latest version: 7" in rendered


@pytest.mark.unit
def test_should_respond_fetching_before_listing_layers(lambda_adapter: MagicMock) -> None:
    """The user is told the listing started before the AWS call, so a slow call is not silent.

    Both doubles append to one shared list, so the assertion checks true call order.
    """
    # Arrange
    order: list[str] = []
    respond = MagicMock(side_effect=lambda text: order.append(f"respond:{text}"))

    def list_layers() -> OperationResult[list[dict[str, Any]]]:
        order.append("list_layers")
        return OperationResult.success(data=[])

    lambda_adapter.list_layers.side_effect = list_layers

    # Act
    lambdas.request_list_layers(MagicMock(), MagicMock(), respond)

    # Assert
    assert order[:2] == ["respond:Fetching Lambda layers...", "list_layers"]


@pytest.mark.unit
@pytest.mark.parametrize("status", [OperationStatus.TRANSIENT_ERROR, OperationStatus.UNAUTHORIZED])
def test_should_respond_failure_and_log_when_list_layers_fails(
    lambda_adapter: MagicMock, mock_logger: MagicMock, status: OperationStatus
) -> None:
    """A classified failure is logged with its classification and shown as a distinct bilingual failure, not an empty list."""
    # Arrange
    respond = MagicMock()
    lambda_adapter.list_layers.return_value = _failure(status)

    # Act
    lambdas.request_list_layers(MagicMock(), MagicMock(), respond)

    # Assert
    assert _responses(respond) == ["Fetching Lambda layers...", LAYERS_FAILURE_TEXT]
    assert {"status": status.value, "error_code": "SomeAwsException", "error": "lambda unavailable"}.items() <= (
        _logged(mock_logger, "lambda_layers_lookup_failed")[0].items()
    )


@pytest.mark.unit
def test_should_respond_none_found_when_no_layers(lambda_adapter: MagicMock, mock_logger: MagicMock) -> None:
    """A successful empty listing gets the bilingual none-found message and logs no failure."""
    # Arrange
    respond = MagicMock()
    lambda_adapter.list_layers.return_value = OperationResult.success(data=[])

    # Act
    lambdas.request_list_layers(MagicMock(), MagicMock(), respond)

    # Assert
    assert _responses(respond) == ["Fetching Lambda layers...", LAYERS_EMPTY_TEXT]
    assert _logged(mock_logger, "lambda_layers_lookup_failed") == []
