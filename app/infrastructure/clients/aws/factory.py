"""Unified AWS client factory for all AWS service operations.

Provides type-safe access to DynamoDB, Identity Store, Organizations, and SSO Admin
services with consistent error handling and OperationResult return types.

All dependencies (region, role ARN, endpoints) are injected via constructor,
enabling dependency injection and easy testing.
"""

from typing import Any, Callable, Dict, Optional

import structlog

from infrastructure.clients.aws.client import execute_aws_api_call
from infrastructure.operations.result import OperationResult

logger = structlog.get_logger()


class AWSClientFactory:
    """Factory for AWS service client operations.

    Consolidates DynamoDB, Identity Store, Organizations, and SSO Admin operations
    into a single injectable class. All methods return OperationResult for
    consistent error handling and downstream processing.

    Args:
        aws_region: AWS region for clients (e.g., 'us-east-1')
        endpoint_url: Custom endpoint URL (for testing/LocalStack)
        role_arn: IAM role to assume for cross-account access
        treat_conflict_as_success: When True, resource-already-exists errors return SUCCESS
        conflict_callback: Optional callback invoked on conflict (e.g., for logging)

    Example:
        factory = AWSClientFactory(aws_region="us-east-1")
        result = factory.get_item("my_table", {"id": {"S": "123"}})
        if result.is_success:
            print(result.data)
    """

    def __init__(
        self,
        aws_region: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        role_arn: Optional[str] = None,
        default_identity_store_id: Optional[str] = None,
        treat_conflict_as_success: bool = False,
        conflict_callback: Optional[Callable[[Exception], None]] = None,
    ):
        self.aws_region = aws_region
        self.endpoint_url = endpoint_url
        self.role_arn = role_arn
        self.default_identity_store_id = default_identity_store_id
        self.treat_conflict_as_success = treat_conflict_as_success
        self.conflict_callback = conflict_callback
        self._logger = logger.bind(component="aws_client_factory")

    def _build_client_kwargs(self, role_arn: Optional[str] = None) -> Dict[str, Any]:
        """Build session and client config kwargs.

        Args:
            role_arn: Optional override for factory's default role_arn.
                     If provided, this role will be used instead of self.role_arn.
        """
        session_config = {}
        client_config = {}
        if self.aws_region:
            session_config["region_name"] = self.aws_region
            client_config["region_name"] = self.aws_region
        if self.endpoint_url:
            client_config["endpoint_url"] = self.endpoint_url
        return {
            "session_config": session_config or None,
            "client_config": client_config or None,
            "role_arn": role_arn or self.role_arn,
        }

    # ======================== DynamoDB Operations ========================

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
            role_arn: Optional override for cross-account access
            **kwargs: Additional DynamoDB get_item parameters

        Returns:
            OperationResult with item data or error
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "dynamodb",
            "get_item",
            TableName=table_name,
            Key=Key,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
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
            role_arn: Optional override for cross-account access
            **kwargs: Additional DynamoDB put_item parameters

        Returns:
            OperationResult with status
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "dynamodb",
            "put_item",
            TableName=table_name,
            Item=Item,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
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
            role_arn: Optional override for cross-account access
            **kwargs: Additional DynamoDB update_item parameters (UpdateExpression, etc.)

        Returns:
            OperationResult with updated item data or error
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "dynamodb",
            "update_item",
            TableName=table_name,
            Key=Key,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
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
            role_arn: Optional override for cross-account access
            **kwargs: Additional DynamoDB delete_item parameters

        Returns:
            OperationResult with status
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "dynamodb",
            "delete_item",
            TableName=table_name,
            Key=Key,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
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
            role_arn: Optional override for cross-account access
            **kwargs: Additional DynamoDB query parameters

        Returns:
            OperationResult with items list or error
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "dynamodb",
            "query",
            TableName=table_name,
            KeyConditionExpression=KeyConditionExpression,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
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
            role_arn: Optional override for cross-account access
            **kwargs: Additional DynamoDB scan parameters

        Returns:
            OperationResult with items list or error
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "dynamodb",
            "scan",
            TableName=table_name,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
            **client_kwargs,
            **kwargs,
        )

    # ======================== Identity Store Operations ========================

    def list_users(
        self,
        *,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """List users in Identity Store.

        Args:
            identity_store_id: Optional override for AWS Identity Store ID (uses factory default if omitted)
            role_arn: Optional override for cross-account access
            **kwargs: Additional parameters (Filters, etc.)

        Returns:
            OperationResult with list of users or error
        """
        store_id = identity_store_id or self.default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "list_users",
            IdentityStoreId=store_id,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
            **client_kwargs,
            **kwargs,
        )

    def get_user(
        self,
        user_id: str,
        *,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Get a user from Identity Store.

        Args:
            user_id: User ID to retrieve (required)
            identity_store_id: Optional override for AWS Identity Store ID (uses factory default if omitted)
            role_arn: Optional override for cross-account access
            **kwargs: Additional parameters

        Returns:
            OperationResult with user details or error
        """
        store_id = identity_store_id or self.default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "describe_user",
            IdentityStoreId=store_id,
            UserId=user_id,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
            **client_kwargs,
            **kwargs,
        )

    def create_user(
        self,
        UserName: str,
        DisplayName: str,
        *,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Create a new user in Identity Store.

        Args:
            UserName: Username for the new user (required)
            DisplayName: Display name for the user (required)
            identity_store_id: Optional override for AWS Identity Store ID (uses factory default if omitted)
            role_arn: Optional override for cross-account access
            **kwargs: Additional parameters

        Returns:
            OperationResult with created user details or error
        """
        store_id = identity_store_id or self.default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "create_user",
            IdentityStoreId=store_id,
            UserName=UserName,
            DisplayName=DisplayName,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
            **client_kwargs,
            **kwargs,
        )

    def delete_user(
        self,
        user_id: str,
        *,
        identity_store_id: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Delete a user from Identity Store.

        Args:
            user_id: User ID to delete (required)
            identity_store_id: Optional override for AWS Identity Store ID (uses factory default if omitted)
            role_arn: Optional override for cross-account access
            **kwargs: Additional parameters

        Returns:
            OperationResult with status or error
        """
        store_id = identity_store_id or self.default_identity_store_id
        if not store_id:
            return OperationResult.permanent_error(
                message="identity_store_id is required",
                error_code="MISSING_IDENTITY_STORE_ID",
            )

        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "identitystore",
            "delete_user",
            IdentityStoreId=store_id,
            UserId=user_id,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
            **client_kwargs,
            **kwargs,
        )

    # ======================== Organizations Operations ========================

    def list_organization_accounts(
        self,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """List all accounts in the AWS Organization.

        Args:
            role_arn: Optional override for cross-account access
            **kwargs: Additional parameters

        Returns:
            OperationResult with list of accounts or error
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "organizations",
            "list_accounts",
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
            **client_kwargs,
            **kwargs,
        )

    def get_account_details(
        self,
        account_id: str,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Get details for a specific AWS account.

        Args:
            account_id: AWS Account ID
            role_arn: Optional override for cross-account access
            **kwargs: Additional parameters

        Returns:
            OperationResult with account details or error
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "organizations",
            "describe_account",
            AccountId=account_id,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
            **client_kwargs,
            **kwargs,
        )

    def get_account_id_by_name(
        self,
        account_name: str,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Find an account ID by account name.

        Args:
            account_name: Name of the account to find
            role_arn: Optional override for cross-account access
            **kwargs: Additional parameters

        Returns:
            OperationResult with account ID or error
        """
        log = self._logger.bind(
            method="get_account_id_by_name", account_name=account_name
        )
        log.info("fetching_accounts")

        # List all accounts and search by name
        result = self.list_organization_accounts(role_arn=role_arn, **kwargs)
        if not result.is_success:
            return result

        accounts = result.data.get("Accounts", []) if result.data else []
        for account in accounts:
            if account.get("Name") == account_name:
                log.info("account_found", account_id=account.get("Id"))
                return OperationResult.success(
                    data={"AccountId": account.get("Id")},
                    message=f"Found account {account_name}",
                )

        log.warning("account_not_found")
        return OperationResult.permanent_error(
            message=f"Account '{account_name}' not found",
            error_code="ACCOUNT_NOT_FOUND",
        )

    # ======================== SSO Admin Operations ========================

    def create_account_assignment(
        self,
        instance_arn: str,
        permission_set_arn: str,
        principal_id: str,
        principal_type: str,
        target_id: str,
        target_type: str = "AWS_ACCOUNT",
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Create an account assignment in AWS SSO.

        Args:
            instance_arn: ARN of the SSO instance
            permission_set_arn: ARN of the permission set
            principal_id: ID of the principal (user or group)
            principal_type: Type of principal ('USER' or 'GROUP')
            target_id: Target AWS account ID
            target_type: Type of target (default 'AWS_ACCOUNT')
            role_arn: Optional override for cross-account access
            **kwargs: Additional parameters

        Returns:
            OperationResult with assignment details or error (may return conflict if already assigned)
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "sso-admin",
            "create_account_assignment",
            InstanceArn=instance_arn,
            PermissionSetArn=permission_set_arn,
            PrincipalId=principal_id,
            PrincipalType=principal_type,
            TargetId=target_id,
            TargetType=target_type,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
            **client_kwargs,
            **kwargs,
        )

    def delete_account_assignment(
        self,
        instance_arn: str,
        permission_set_arn: str,
        principal_id: str,
        principal_type: str,
        target_id: str,
        target_type: str = "AWS_ACCOUNT",
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Delete an account assignment from AWS SSO.

        Args:
            instance_arn: ARN of the SSO instance
            permission_set_arn: ARN of the permission set
            principal_id: ID of the principal (user or group)
            principal_type: Type of principal ('USER' or 'GROUP')
            target_id: Target AWS account ID
            target_type: Type of target (default 'AWS_ACCOUNT')
            role_arn: Optional override for cross-account access
            **kwargs: Additional parameters

        Returns:
            OperationResult with status or error
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "sso-admin",
            "delete_account_assignment",
            InstanceArn=instance_arn,
            PermissionSetArn=permission_set_arn,
            PrincipalId=principal_id,
            PrincipalType=principal_type,
            TargetId=target_id,
            TargetType=target_type,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
            **client_kwargs,
            **kwargs,
        )

    def list_account_assignments_for_principal(
        self,
        instance_arn: str,
        principal_id: str,
        principal_type: str,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """List account assignments for a principal.

        Args:
            instance_arn: ARN of the SSO instance
            principal_id: ID of the principal (user or group)
            principal_type: Type of principal ('USER' or 'GROUP')
            role_arn: Optional override for cross-account access
            **kwargs: Additional parameters

        Returns:
            OperationResult with list of assignments or error
        """
        client_kwargs = self._build_client_kwargs(role_arn=role_arn)
        return execute_aws_api_call(
            "sso-admin",
            "list_account_assignments",
            InstanceArn=instance_arn,
            PrincipalId=principal_id,
            PrincipalType=principal_type,
            treat_conflict_as_success=self.treat_conflict_as_success,
            conflict_callback=self.conflict_callback,
            **client_kwargs,
            **kwargs,
        )
