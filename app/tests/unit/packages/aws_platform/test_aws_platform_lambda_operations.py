"""Behavior tests for LambdaAdapter operations.

A real boto3 lambda client built with static dummy credentials is wrapped
in botocore.stub.Stubber, which validates requests against the service model and
replays canned responses. Each operation test covers the success path with
expected params and the data shape, pagination across two pages with NextMarker,
and classification paths for ServiceException and other transient errors.
"""

from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber

from infrastructure.operations.status import OperationStatus
from packages.aws_platform.adapters.aws_lambda import LambdaAdapter

pytestmark = pytest.mark.unit


def _lambda_client() -> Any:
    """Build a real boto3 lambda client with dummy static credentials."""
    return boto3.client(
        "lambda",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestListFunctions:
    """ListFunctions returns paginated list of Lambda functions."""

    def test_list_functions_single_page(self) -> None:
        """ListFunctions with single page returns list of functions."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_functions",
                {
                    "Functions": [
                        {
                            "FunctionName": "function1",
                            "FunctionArn": "arn:aws:lambda:ca-central-1:123456789012:function:function1",
                            "Runtime": "python3.11",
                            "Handler": "index.handler",
                            "CodeSize": 1024,
                            "Timeout": 30,
                            "MemorySize": 128,
                        }
                    ]
                },
                expected_params={},
            )

            result = adapter.list_functions()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1
        assert result.data[0]["FunctionName"] == "function1"

    def test_list_functions_pagination_two_pages(self) -> None:
        """ListFunctions flattens functions across two pages via NextMarker."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_functions",
                {
                    "Functions": [
                        {
                            "FunctionName": "function1",
                            "FunctionArn": "arn:aws:lambda:ca-central-1:123456789012:function:function1",
                            "Runtime": "python3.11",
                            "Handler": "index.handler",
                            "CodeSize": 1024,
                            "Timeout": 30,
                            "MemorySize": 128,
                        }
                    ],
                    "NextMarker": "functions-marker",
                },
                expected_params={},
            )
            stub.add_response(
                "list_functions",
                {
                    "Functions": [
                        {
                            "FunctionName": "function2",
                            "FunctionArn": "arn:aws:lambda:ca-central-1:123456789012:function:function2",
                            "Runtime": "python3.11",
                            "Handler": "index.handler",
                            "CodeSize": 2048,
                            "Timeout": 60,
                            "MemorySize": 256,
                        }
                    ]
                },
                expected_params={"Marker": "functions-marker"},
            )

            result = adapter.list_functions()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert [f["FunctionName"] for f in result.data] == ["function1", "function2"]

    def test_list_functions_empty(self) -> None:
        """ListFunctions with no functions returns empty list."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_functions",
                {"Functions": []},
                expected_params={},
            )

            result = adapter.list_functions()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []


class TestListLayers:
    """ListLayers returns paginated list of Lambda layers."""

    def test_list_layers_single_page(self) -> None:
        """ListLayers with single page returns list of layers."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_layers",
                {
                    "Layers": [
                        {
                            "LayerArn": "arn:aws:lambda:ca-central-1:123456789012:layer:layer1:1",
                            "LayerName": "layer1",
                            "LatestMatchingVersion": {
                                "LayerVersionArn": "arn:aws:lambda:ca-central-1:123456789012:layer:layer1:1",
                                "Version": 1,
                            },
                        }
                    ]
                },
                expected_params={},
            )

            result = adapter.list_layers()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1
        assert result.data[0]["LayerName"] == "layer1"

    def test_list_layers_pagination_two_pages(self) -> None:
        """ListLayers flattens layers across two pages via NextMarker."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_layers",
                {
                    "Layers": [
                        {
                            "LayerArn": "arn:aws:lambda:ca-central-1:123456789012:layer:layer1:1",
                            "LayerName": "layer1",
                            "LatestMatchingVersion": {
                                "LayerVersionArn": "arn:aws:lambda:ca-central-1:123456789012:layer:layer1:1",
                                "Version": 1,
                            },
                        }
                    ],
                    "NextMarker": "layers-marker",
                },
                expected_params={},
            )
            stub.add_response(
                "list_layers",
                {
                    "Layers": [
                        {
                            "LayerArn": "arn:aws:lambda:ca-central-1:123456789012:layer:layer2:2",
                            "LayerName": "layer2",
                            "LatestMatchingVersion": {
                                "LayerVersionArn": "arn:aws:lambda:ca-central-1:123456789012:layer:layer2:2",
                                "Version": 2,
                            },
                        }
                    ]
                },
                expected_params={"Marker": "layers-marker"},
            )

            result = adapter.list_layers()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert [layer["LayerName"] for layer in result.data] == ["layer1", "layer2"]

    def test_list_layers_empty(self) -> None:
        """ListLayers with no layers returns empty list."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_layers",
                {"Layers": []},
                expected_params={},
            )

            result = adapter.list_layers()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []


class TestErrorClassification:
    """Errors are classified via classify_aws_error; unmapped errors propagate."""

    def test_service_exception_is_transient(self) -> None:
        """ServiceException maps to TRANSIENT_ERROR."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_functions",
                service_error_code="ServiceException",
                http_status_code=500,
            )

            result = adapter.list_functions()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ServiceException"

    def test_internal_server_error_is_transient(self) -> None:
        """InternalServerErrorException maps to TRANSIENT_ERROR with retry_after."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_layers",
                service_error_code="InternalServerErrorException",
                http_status_code=500,
            )

            result = adapter.list_layers()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "InternalServerErrorException"
        assert result.retry_after == 60

    def test_throttling_classification_with_retry_after(self) -> None:
        """ThrottlingException maps to TRANSIENT_ERROR with retry_after=60."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_functions",
                service_error_code="ThrottlingException",
                http_status_code=429,
            )

            result = adapter.list_functions()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ThrottlingException"
        assert result.retry_after == 60

    def test_botocore_connection_error_is_transient(self) -> None:
        """BotoCoreError (EndpointConnectionError) maps to TRANSIENT_ERROR."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:

            def raise_endpoint_error(*args: Any, **kwargs: Any) -> None:
                raise EndpointConnectionError(endpoint_url="https://lambda.ca-central-1.amazonaws.com")

            stub.client.list_functions = raise_endpoint_error

            result = adapter.list_functions()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "EndpointConnectionError"

    def test_unmapped_client_error_propagates(self) -> None:
        """ValidationException (unmapped) propagates as ClientError."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_functions",
                service_error_code="ValidationException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.list_functions()

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "ValidationException"

    def test_programmer_error_propagates(self) -> None:
        """Non-ClientError exceptions (e.g., KeyError) propagate unchanged."""
        client = _lambda_client()
        adapter = LambdaAdapter(client=client)

        with Stubber(client) as stub:

            def raise_key_error(*args: Any, **kwargs: Any) -> None:
                raise KeyError("missing_key")

            stub.client.list_functions = raise_key_error

            with pytest.raises(KeyError):
                adapter.list_functions()

            stub.assert_no_pending_responses()
