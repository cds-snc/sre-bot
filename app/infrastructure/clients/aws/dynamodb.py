"""DynamoDB client for AWS operations.

Provides type-safe access to DynamoDB operations (get_item, put_item, query, scan, etc.)
with consistent error handling and OperationResult return types.
"""

from typing import Any, Dict, Optional

import structlog

from infrastructure.clients.aws.executor import execute_aws_api_call
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.operations.result import OperationResult

logger = structlog.get_logger()


class DynamoDBClient:
    """Client for DynamoDB operations.

    All methods return OperationResult for consistent error handling and
    downstream processing.

    Args:
        session_provider: SessionProvider instance for credential/config management
    """

    def __init__(
        self,
        session_provider: SessionProvider,
        default_role_arn: Optional[str] = None,
    ) -> None:
        self._session_provider = session_provider
        self._default_role_arn = default_role_arn
        self._service_name = "dynamodb"
        self._logger = logger.bind(component="dynamodb_client")

    def get_item(
        self,
        table_name: str,
        Key: Dict[str, Any],
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Get an item from DynamoDB.

        Args:
            table_name: Name of the DynamoDB table
            Key: Primary key of the item (e.g., {"id": {"S": "123"}})
            role_arn: Optional cross-account role ARN
            **kwargs: Additional DynamoDB get_item parameters

        Returns:
            OperationResult with item data or error
        """
        effective_role = role_arn or self._default_role_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=effective_role
        )
        return execute_aws_api_call(
            "dynamodb",
            "get_item",
            TableName=table_name,
            Key=Key,
            **client_kwargs,
            **kwargs,
        )

    def put_item(
        self,
        table_name: str,
        Item: Dict[str, Any],
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Put an item into DynamoDB.

        Args:
            table_name: Name of the DynamoDB table
            Item: Item to store (DynamoDB format with type descriptors)
            role_arn: Optional cross-account role ARN
            **kwargs: Additional DynamoDB put_item parameters

        Returns:
            OperationResult with status
        """
        effective_role = role_arn or self._default_role_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=effective_role
        )
        return execute_aws_api_call(
            "dynamodb",
            "put_item",
            TableName=table_name,
            Item=Item,
            **client_kwargs,
            **kwargs,
        )

    def update_item(
        self,
        table_name: str,
        Key: Dict[str, Any],
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Update an item in DynamoDB.

        Args:
            table_name: Name of the DynamoDB table
            Key: Primary key of the item
            role_arn: Optional cross-account role ARN
            **kwargs: Additional DynamoDB update_item parameters (UpdateExpression, etc.)

        Returns:
            OperationResult with updated item data or error
        """
        effective_role = role_arn or self._default_role_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=effective_role
        )
        return execute_aws_api_call(
            "dynamodb",
            "update_item",
            TableName=table_name,
            Key=Key,
            **client_kwargs,
            **kwargs,
        )

    def delete_item(
        self,
        table_name: str,
        Key: Dict[str, Any],
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Delete an item from DynamoDB.

        Args:
            table_name: Name of the DynamoDB table
            Key: Primary key of the item to delete
            role_arn: Optional cross-account role ARN
            **kwargs: Additional DynamoDB delete_item parameters

        Returns:
            OperationResult with status
        """
        effective_role = role_arn or self._default_role_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=effective_role
        )
        return execute_aws_api_call(
            "dynamodb",
            "delete_item",
            TableName=table_name,
            Key=Key,
            **client_kwargs,
            **kwargs,
        )

    def query(
        self,
        table_name: str,
        KeyConditionExpression: Any,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Query items from DynamoDB using key condition.

        Args:
            table_name: Name of the DynamoDB table
            KeyConditionExpression: Key condition expression
            role_arn: Optional cross-account role ARN
            **kwargs: Additional DynamoDB query parameters

        Returns:
            OperationResult with items list or error
        """
        effective_role = role_arn or self._default_role_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=effective_role
        )
        return execute_aws_api_call(
            "dynamodb",
            "query",
            TableName=table_name,
            KeyConditionExpression=KeyConditionExpression,
            **client_kwargs,
            **kwargs,
        )

    def scan(
        self,
        table_name: str,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Scan all items from a DynamoDB table.

        Args:
            table_name: Name of the DynamoDB table
            role_arn: Optional cross-account role ARN
            **kwargs: Additional DynamoDB scan parameters

        Returns:
            OperationResult with items list or error
        """
        effective_role = role_arn or self._default_role_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=effective_role
        )
        return execute_aws_api_call(
            "dynamodb",
            "scan",
            TableName=table_name,
            **client_kwargs,
            **kwargs,
        )

    def healthcheck(self, role_arn: Optional[str] = None) -> OperationResult:
        """Lightweight health check for DynamoDB.

        Performs a cheap `list_tables` call to verify the service is reachable.
        Returns OperationResult.success on success, or an error OperationResult.
        """
        client_kwargs = self._session_provider.build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "dynamodb",
            "list_tables",
            max_retries=0,
            **client_kwargs,
        )
