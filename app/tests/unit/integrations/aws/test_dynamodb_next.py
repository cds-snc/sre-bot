"""Unit tests for dynamodb_next.py wrapper module."""

import pytest
from unittest.mock import patch

from integrations.aws.dynamodb_next import (
    get_item,
    put_item,
    update_item,
    delete_item,
    query,
    scan,
)
from infrastructure.operations.result import OperationResult, OperationStatus

pytestmark = pytest.mark.unit


class TestDynamoDBNextGetItem:
    """Tests for get_item function."""

    @patch("integrations.aws.dynamodb_next.execute_aws_api_call")
    def test_get_item_calls_execute_with_correct_params(self, mock_execute):
        """get_item calls execute_aws_api_call with correct parameters."""
        mock_execute.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Item retrieved",
        )

        result = get_item(
            table_name="test_table",
            Key={"id": {"S": "123"}},
        )

        mock_execute.assert_called_once_with(
            service_name="dynamodb",
            method="get_item",
            TableName="test_table",
            Key={"id": {"S": "123"}},
        )
        assert result.is_success

    @patch("integrations.aws.dynamodb_next.execute_aws_api_call")
    def test_get_item_returns_operation_result(self, mock_execute):
        """get_item returns OperationResult."""
        expected_result = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Found",
            data={"Item": {"id": {"S": "123"}}},
        )
        mock_execute.return_value = expected_result

        result = get_item(
            table_name="test_table",
            Key={"id": {"S": "123"}},
        )

        assert result is expected_result
        assert result.is_success


class TestDynamoDBNextPutItem:
    """Tests for put_item function."""

    @patch("integrations.aws.dynamodb_next.execute_aws_api_call")
    def test_put_item_calls_execute_with_correct_params(self, mock_execute):
        """put_item calls execute_aws_api_call with correct parameters."""
        mock_execute.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Item stored",
        )

        result = put_item(
            table_name="test_table",
            Item={"id": {"S": "123"}, "name": {"S": "test"}},
        )

        mock_execute.assert_called_once_with(
            service_name="dynamodb",
            method="put_item",
            TableName="test_table",
            Item={"id": {"S": "123"}, "name": {"S": "test"}},
        )
        assert result.is_success

    @patch("integrations.aws.dynamodb_next.execute_aws_api_call")
    def test_put_item_supports_additional_kwargs(self, mock_execute):
        """put_item supports additional parameters."""
        mock_execute.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Item stored",
        )

        result = put_item(
            table_name="test_table",
            Item={"id": {"S": "123"}},
            ConditionExpression="attribute_not_exists(id)",
        )

        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["ConditionExpression"] == "attribute_not_exists(id)"
        assert result.is_success


class TestDynamoDBNextUpdateItem:
    """Tests for update_item function."""

    @patch("integrations.aws.dynamodb_next.execute_aws_api_call")
    def test_update_item_calls_execute_with_correct_params(self, mock_execute):
        """update_item calls execute_aws_api_call with correct parameters."""
        mock_execute.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Item updated",
        )

        result = update_item(
            table_name="test_table",
            Key={"id": {"S": "123"}},
            UpdateExpression="SET #n = :val",
        )

        mock_execute.assert_called_once_with(
            service_name="dynamodb",
            method="update_item",
            TableName="test_table",
            Key={"id": {"S": "123"}},
            UpdateExpression="SET #n = :val",
        )
        assert result.is_success


class TestDynamoDBNextDeleteItem:
    """Tests for delete_item function."""

    @patch("integrations.aws.dynamodb_next.execute_aws_api_call")
    def test_delete_item_calls_execute_with_correct_params(self, mock_execute):
        """delete_item calls execute_aws_api_call with correct parameters."""
        mock_execute.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Item deleted",
        )

        result = delete_item(
            table_name="test_table",
            Key={"id": {"S": "123"}},
        )

        mock_execute.assert_called_once_with(
            service_name="dynamodb",
            method="delete_item",
            TableName="test_table",
            Key={"id": {"S": "123"}},
        )
        assert result.is_success


class TestDynamoDBNextQuery:
    """Tests for query function."""

    @patch("integrations.aws.dynamodb_next.execute_aws_api_call")
    def test_query_calls_execute_with_pagination(self, mock_execute):
        """query calls execute_aws_api_call with pagination enabled."""
        mock_execute.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Query completed",
            data={"Items": []},
        )

        result = query(
            table_name="test_table",
            KeyConditionExpression="id = :id",
        )

        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["service_name"] == "dynamodb"
        assert call_kwargs["method"] == "query"
        assert call_kwargs["force_paginate"] is True
        assert call_kwargs["keys"] == ["Items"]
        assert result.is_success

    @patch("integrations.aws.dynamodb_next.execute_aws_api_call")
    def test_query_supports_expression_values(self, mock_execute):
        """query supports expression attribute values."""
        mock_execute.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Query completed",
            data={"Items": []},
        )

        result = query(
            table_name="test_table",
            KeyConditionExpression="id = :id",
            ExpressionAttributeValues={":id": {"S": "123"}},
        )

        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["ExpressionAttributeValues"] == {":id": {"S": "123"}}
        assert result.is_success


class TestDynamoDBNextScan:
    """Tests for scan function."""

    @patch("integrations.aws.dynamodb_next.execute_aws_api_call")
    def test_scan_calls_execute_with_pagination(self, mock_execute):
        """scan calls execute_aws_api_call with pagination enabled."""
        mock_execute.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Scan completed",
            data={"Items": []},
        )

        result = scan(table_name="test_table")

        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["service_name"] == "dynamodb"
        assert call_kwargs["method"] == "scan"
        assert call_kwargs["force_paginate"] is True
        assert call_kwargs["keys"] == ["Items"]
        assert result.is_success

    @patch("integrations.aws.dynamodb_next.execute_aws_api_call")
    def test_scan_supports_filter_expression(self, mock_execute):
        """scan supports filter expression."""
        mock_execute.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Scan completed",
            data={"Items": []},
        )

        result = scan(
            table_name="test_table",
            FilterExpression="attribute_exists(ttl)",
        )

        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["FilterExpression"] == "attribute_exists(ttl)"
        assert result.is_success
