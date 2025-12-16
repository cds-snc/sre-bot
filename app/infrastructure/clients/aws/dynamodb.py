"""DynamoDB client helpers using infrastructure client pattern.

All functions accept optional `aws_region`, `role_arn`, and `endpoint_url`
parameters so callers (and tests) can provide configuration via DI.
"""

from typing import Any, Dict, Optional

from infrastructure.clients.aws.client import execute_aws_api_call
from infrastructure.operations.result import OperationResult


def _build_client_kwargs(
    aws_region: Optional[str] = None, endpoint_url: Optional[str] = None
) -> dict:
    client_config = {}
    session_config = {}
    if aws_region:
        session_config["region_name"] = aws_region
        client_config["region_name"] = aws_region
    if endpoint_url:
        client_config["endpoint_url"] = endpoint_url
    return {
        "session_config": session_config or None,
        "client_config": client_config or None,
    }


def get_item(
    table_name: str,
    Key: Dict[str, Any],
    aws_region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "dynamodb",
        "get_item",
        TableName=table_name,
        Key=Key,
        **_build_client_kwargs(aws_region, endpoint_url),
        **kwargs,
    )


def put_item(
    table_name: str,
    Item: Dict[str, Any],
    aws_region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "dynamodb",
        "put_item",
        TableName=table_name,
        Item=Item,
        **_build_client_kwargs(aws_region, endpoint_url),
        **kwargs,
    )


def update_item(
    table_name: str,
    Key: Dict[str, Any],
    aws_region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "dynamodb",
        "update_item",
        TableName=table_name,
        Key=Key,
        **_build_client_kwargs(aws_region, endpoint_url),
        **kwargs,
    )


def delete_item(
    table_name: str,
    Key: Dict[str, Any],
    aws_region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "dynamodb",
        "delete_item",
        TableName=table_name,
        Key=Key,
        **_build_client_kwargs(aws_region, endpoint_url),
        **kwargs,
    )


def query(
    table_name: str,
    KeyConditionExpression: str,
    aws_region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "dynamodb",
        "query",
        keys=["Items"],
        force_paginate=True,
        TableName=table_name,
        KeyConditionExpression=KeyConditionExpression,
        **_build_client_kwargs(aws_region, endpoint_url),
        **kwargs,
    )


def scan(
    table_name: str,
    aws_region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    **kwargs
) -> OperationResult:
    return execute_aws_api_call(
        "dynamodb",
        "scan",
        keys=["Items"],
        force_paginate=True,
        TableName=table_name,
        **_build_client_kwargs(aws_region, endpoint_url),
        **kwargs,
    )
