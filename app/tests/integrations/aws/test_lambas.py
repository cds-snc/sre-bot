from unittest.mock import patch, MagicMock
from integrations.aws.lambdas import list_functions, list_layers, get_layer_version


@patch("integrations.aws.lambdas.execute_aws_api_call")
def test_list_functions(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = [
        {"FunctionName": "function1"},
        {"FunctionName": "function2"},
    ]
    result = list_functions()
    mock_execute_aws_api_call.assert_called_once_with(
        "lambda", "list_functions", paginated=True, keys=["Functions"]
    )
    assert result == [
        {"FunctionName": "function1"},
        {"FunctionName": "function2"},
    ]


@patch("integrations.aws.lambdas.execute_aws_api_call")
def test_list_layers(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = [
        {"LayerName": "layer1", "LatestMatchingVersion": {"Version": 1}},
        {"LayerName": "layer2", "LatestMatchingVersion": {"Version": 23}},
    ]

    result = list_layers()
    mock_execute_aws_api_call.assert_called_once_with(
        "lambda", "list_layers", paginated=True, keys=["Layers"]
    )
    assert result == [
        {"LayerName": "layer1", "LatestMatchingVersion": {"Version": 1}},
        {"LayerName": "layer2", "LatestMatchingVersion": {"Version": 23}},
    ]


@patch("integrations.aws.lambdas.execute_aws_api_call")
def test_get_layer_version(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = {"LayerName": "layer1", "Version": 1}
    result = get_layer_version("layer1", 1)
    mock_execute_aws_api_call.assert_called_once_with(
        "lambda", "get_layer_version", LayerName="layer1", VersionNumber=1
    )
    assert result == {"LayerName": "layer1", "Version": 1}
