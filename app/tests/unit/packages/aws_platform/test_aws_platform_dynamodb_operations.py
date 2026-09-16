"""Behavior tests for DynamoDBAdapter operations.

A real boto3 dynamodb client built with static dummy credentials is wrapped
in botocore.stub.Stubber, which validates requests against the service model and
replays canned responses. Each operation test covers the success path with
expected params and the data shape, pagination across two pages via
LastEvaluatedKey, absent items (get_item returns data=None, not an error),
classification paths for ResourceNotFoundException, AccessDeniedException,
ThrottlingException, ConditionalCheckFailedException, BotoCoreError transient
errors, and unmapped errors propagating. update_item routing (retries=True vs
retries=False) is tested with dual Stubbers.
"""

from typing import Any
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber

from infrastructure.operations.status import OperationStatus
from packages.aws_platform.adapters.dynamodb import DynamoDBAdapter

pytestmark = pytest.mark.unit


def _dynamodb_client() -> Any:
    """Build a real boto3 dynamodb client with dummy static credentials."""
    return boto3.client(
        "dynamodb",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestScan:
    """Scan returns paginated Items flattened into a single list."""

    def test_scan_single_page(self) -> None:
        """Scan with single page of Items returns the list."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_response(
                "scan",
                {
                    "Items": [
                        {"id": {"S": "item1"}, "name": {"S": "Item One"}},
                        {"id": {"S": "item2"}, "name": {"S": "Item Two"}},
                    ]
                },
                expected_params={"TableName": "test_table"},
            )

            result = adapter.scan(TableName="test_table")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert result.data[0]["id"]["S"] == "item1"
        assert result.data[1]["id"]["S"] == "item2"

    def test_scan_pagination_two_pages(self) -> None:
        """Scan flattens Items across two pages via LastEvaluatedKey."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_response(
                "scan",
                {
                    "Items": [
                        {"id": {"S": "item1"}, "name": {"S": "Item One"}},
                    ],
                    "LastEvaluatedKey": {"id": {"S": "item1"}},
                },
                expected_params={"TableName": "test_table"},
            )
            stub.add_response(
                "scan",
                {
                    "Items": [
                        {"id": {"S": "item2"}, "name": {"S": "Item Two"}},
                    ]
                },
                expected_params={"TableName": "test_table", "ExclusiveStartKey": {"id": {"S": "item1"}}},
            )

            result = adapter.scan(TableName="test_table")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert [item["id"]["S"] for item in result.data] == ["item1", "item2"]

    def test_scan_empty(self) -> None:
        """Scan with no Items returns empty list."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_response(
                "scan",
                {"Items": []},
                expected_params={"TableName": "test_table"},
            )

            result = adapter.scan(TableName="test_table")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []


class TestGetItem:
    """GetItem returns the Item or None when absent."""

    def test_get_item_found(self) -> None:
        """GetItem with Item in response returns the Item."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_response(
                "get_item",
                {
                    "Item": {
                        "id": {"S": "item1"},
                        "name": {"S": "Item One"},
                    }
                },
                expected_params={"TableName": "test_table", "Key": {"id": {"S": "item1"}}},
            )

            result = adapter.get_item(TableName="test_table", Key={"id": {"S": "item1"}})

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == {"id": {"S": "item1"}, "name": {"S": "Item One"}}

    def test_get_item_absent(self) -> None:
        """GetItem with no Item key returns success with data=None (not an error)."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_response(
                "get_item",
                {},
                expected_params={"TableName": "test_table", "Key": {"id": {"S": "nonexistent"}}},
            )

            result = adapter.get_item(TableName="test_table", Key={"id": {"S": "nonexistent"}})

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is None


class TestPutItem:
    """PutItem returns success with data=None."""

    def test_put_item_success(self) -> None:
        """PutItem with valid item returns success."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_response(
                "put_item",
                {},
                expected_params={
                    "TableName": "test_table",
                    "Item": {"id": {"S": "item1"}, "name": {"S": "Item One"}},
                },
            )

            result = adapter.put_item(
                TableName="test_table",
                Item={"id": {"S": "item1"}, "name": {"S": "Item One"}},
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is None


class TestUpdateItem:
    """UpdateItem routes between retry and no-retry clients based on retries param."""

    def test_update_item_default_retries_uses_standard_client(self) -> None:
        """UpdateItem with default retries=True uses the standard-retry client."""
        std_client = _dynamodb_client()
        no_retry_client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=std_client, client_no_retry=no_retry_client)

        with Stubber(std_client) as std_stub, Stubber(no_retry_client) as no_retry_stub:
            std_stub.add_response(
                "update_item",
                {},
                expected_params={
                    "TableName": "test_table",
                    "Key": {"id": {"S": "item1"}},
                    "UpdateExpression": "SET #n = :v",
                    "ExpressionAttributeNames": {"#n": "name"},
                    "ExpressionAttributeValues": {":v": {"S": "Updated"}},
                },
            )

            result = adapter.update_item(
                TableName="test_table",
                Key={"id": {"S": "item1"}},
                UpdateExpression="SET #n = :v",
                ExpressionAttributeNames={"#n": "name"},
                ExpressionAttributeValues={":v": {"S": "Updated"}},
            )

            std_stub.assert_no_pending_responses()
            no_retry_stub.assert_no_pending_responses()

        assert result.is_success

    def test_update_item_retries_false_uses_no_retry_client(self) -> None:
        """UpdateItem with retries=False uses the no-retry client."""
        std_client = _dynamodb_client()
        no_retry_client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=std_client, client_no_retry=no_retry_client)

        with Stubber(std_client) as std_stub, Stubber(no_retry_client) as no_retry_stub:
            no_retry_stub.add_response(
                "update_item",
                {},
                expected_params={
                    "TableName": "test_table",
                    "Key": {"id": {"S": "item1"}},
                    "UpdateExpression": "SET #c = #c + :inc",
                    "ExpressionAttributeNames": {"#c": "counter"},
                    "ExpressionAttributeValues": {":inc": {"N": "1"}},
                },
            )

            result = adapter.update_item(
                retries=False,
                TableName="test_table",
                Key={"id": {"S": "item1"}},
                UpdateExpression="SET #c = #c + :inc",
                ExpressionAttributeNames={"#c": "counter"},
                ExpressionAttributeValues={":inc": {"N": "1"}},
            )

            no_retry_stub.assert_no_pending_responses()
            std_stub.assert_no_pending_responses()

        assert result.is_success


class TestErrorClassification:
    """Errors are classified via classify_aws_error; unmapped errors propagate."""

    def test_not_found_code_is_not_found(self) -> None:
        """ResourceNotFoundException maps to NOT_FOUND."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_item",
                service_error_code="ResourceNotFoundException",
                http_status_code=400,
            )

            result = adapter.get_item(TableName="test_table", Key={"id": {"S": "item1"}})

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.NOT_FOUND
        assert result.error_code == "ResourceNotFoundException"

    def test_unauthorized_code_is_unauthorized(self) -> None:
        """AccessDeniedException maps to UNAUTHORIZED."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "scan",
                service_error_code="AccessDeniedException",
                http_status_code=403,
            )

            result = adapter.scan(TableName="test_table")

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.UNAUTHORIZED
        assert result.error_code == "AccessDeniedException"

    def test_throttling_is_transient_with_retry_after(self) -> None:
        """ThrottlingException maps to TRANSIENT_ERROR with retry_after=60."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "put_item",
                service_error_code="ThrottlingException",
                http_status_code=400,
            )

            result = adapter.put_item(
                TableName="test_table",
                Item={"id": {"S": "item1"}},
            )

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ThrottlingException"
        assert result.retry_after == 60

    def test_conditional_check_failed_is_permanent(self) -> None:
        """ConditionalCheckFailedException maps to PERMANENT_ERROR."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "update_item",
                service_error_code="ConditionalCheckFailedException",
                http_status_code=400,
            )

            result = adapter.update_item(
                TableName="test_table",
                Key={"id": {"S": "item1"}},
                UpdateExpression="SET #n = :v",
                ExpressionAttributeNames={"#n": "name"},
                ExpressionAttributeValues={":v": {"S": "Updated"}},
            )

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "ConditionalCheckFailedException"

    def test_botocore_error_is_transient(self) -> None:
        """BotoCoreError (EndpointConnectionError) maps to TRANSIENT_ERROR."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        endpoint_error = EndpointConnectionError(endpoint_url="https://dynamodb.ca-central-1.amazonaws.com")
        with Stubber(client) as stub, patch.object(client, "get_item", side_effect=endpoint_error):
            result = adapter.get_item(TableName="test_table", Key={"id": {"S": "item1"}})

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "EndpointConnectionError"

    def test_unmapped_client_error_propagates(self) -> None:
        """ValidationException (unmapped) propagates as ClientError."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "scan",
                service_error_code="ValidationException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.scan(TableName="test_table")

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "ValidationException"

    def test_programmer_error_propagates(self) -> None:
        """Non-ClientError exceptions (e.g., KeyError) propagate unchanged."""
        client = _dynamodb_client()
        adapter = DynamoDBAdapter(client=client, client_no_retry=client)

        with Stubber(client) as stub, patch.object(client, "put_item", side_effect=KeyError("missing_key")):
            with pytest.raises(KeyError):
                adapter.put_item(TableName="test_table", Item={"id": {"S": "item1"}})

            stub.assert_no_pending_responses()
