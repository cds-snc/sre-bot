"""AWS DynamoDB Next Module

Provides simplified, standardized functions for DynamoDB operations using client_next.py.
Features:
- Consistent error handling and retries via client_next.execute_aws_api_call
- Standardized OperationResult responses
- Automatic pagination for scan/query operations
- Unified logging and throttling management

Usage:
    result = get_item(
        table_name="sre_bot_idempotency",
        Key={"idempotency_key": {"S": "unique-key"}},
    )
    if result.is_success:
        item = result.data
    else:
        error = result.message
"""

from typing import Any, Dict

import structlog
from core.config import settings
from integrations.aws.client_next import execute_aws_api_call
from infrastructure.operations.result import OperationResult

logger = structlog.get_logger()

AWS_REGION = settings.aws.AWS_REGION


def get_item(
    table_name: str,
    Key: Dict[str, Any],
    **kwargs,
) -> OperationResult:
    """Get an item from DynamoDB table.

    Args:
        table_name: DynamoDB table name
        Key: Primary key attributes (DynamoDB format)
        **kwargs: Additional parameters for get_item call

    Returns:
        OperationResult: Item if found, or error details
    """
    return execute_aws_api_call(
        service_name="dynamodb",
        method="get_item",
        TableName=table_name,
        Key=Key,
        **kwargs,
    )


def put_item(
    table_name: str,
    Item: Dict[str, Any],
    **kwargs,
) -> OperationResult:
    """Put an item into DynamoDB table.

    Args:
        table_name: DynamoDB table name
        Item: Item attributes (DynamoDB format)
        **kwargs: Additional parameters for put_item call

    Returns:
        OperationResult: Success or error details
    """
    return execute_aws_api_call(
        service_name="dynamodb",
        method="put_item",
        TableName=table_name,
        Item=Item,
        **kwargs,
    )


def update_item(
    table_name: str,
    Key: Dict[str, Any],
    **kwargs,
) -> OperationResult:
    """Update an item in DynamoDB table.

    Args:
        table_name: DynamoDB table name
        Key: Primary key attributes (DynamoDB format)
        **kwargs: Additional parameters for update_item call

    Returns:
        OperationResult: Updated attributes or error details
    """
    return execute_aws_api_call(
        service_name="dynamodb",
        method="update_item",
        TableName=table_name,
        Key=Key,
        **kwargs,
    )


def delete_item(
    table_name: str,
    Key: Dict[str, Any],
    **kwargs,
) -> OperationResult:
    """Delete an item from DynamoDB table.

    Args:
        table_name: DynamoDB table name
        Key: Primary key attributes (DynamoDB format)
        **kwargs: Additional parameters for delete_item call

    Returns:
        OperationResult: Success or error details
    """
    return execute_aws_api_call(
        service_name="dynamodb",
        method="delete_item",
        TableName=table_name,
        Key=Key,
        **kwargs,
    )


def query(
    table_name: str,
    KeyConditionExpression: str,
    **kwargs,
) -> OperationResult:
    """Query a DynamoDB table with automatic pagination.

    Args:
        table_name: DynamoDB table name
        KeyConditionExpression: Query condition
        **kwargs: Additional parameters for query call

    Returns:
        OperationResult: List of items or error details
    """
    return execute_aws_api_call(
        service_name="dynamodb",
        method="query",
        TableName=table_name,
        KeyConditionExpression=KeyConditionExpression,
        keys=["Items"],
        force_paginate=True,
        **kwargs,
    )


def scan(
    table_name: str,
    **kwargs,
) -> OperationResult:
    """Scan a DynamoDB table with automatic pagination.

    Args:
        table_name: DynamoDB table name
        **kwargs: Additional parameters for scan call

    Returns:
        OperationResult: List of items or error details
    """
    return execute_aws_api_call(
        service_name="dynamodb",
        method="scan",
        TableName=table_name,
        keys=["Items"],
        force_paginate=True,
        **kwargs,
    )
