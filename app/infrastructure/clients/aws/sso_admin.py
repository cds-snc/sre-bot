"""SSO Admin client for AWS operations.

Provides type-safe access to AWS SSO Admin operations (create_account_assignment, delete_account_assignment, etc.)
with consistent error handling and OperationResult return types.
"""

from typing import Optional

import structlog

from infrastructure.clients.aws.executor import execute_aws_api_call
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.operations.result import OperationResult

logger = structlog.get_logger()


class SsoAdminClient:
    """Client for AWS SSO Admin operations.

    All methods return OperationResult for consistent error handling and
    downstream processing.

    Args:
        session_provider: SessionProvider instance for credential/config management
    """

    def __init__(
        self,
        session_provider: SessionProvider,
        default_sso_instance_arn: Optional[str] = None,
    ) -> None:
        self._service_name = "sso-admin"
        self._session_provider = session_provider
        self._logger = logger.bind(component="sso_admin_client")
        self._default_sso_instance_arn = default_sso_instance_arn

    def create_account_assignment(
        self,
        permission_set_arn: str,
        principal_id: str,
        principal_type: str,
        target_id: str,
        target_type: str = "AWS_ACCOUNT",
        instance_arn: Optional[str] = None,
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
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters

        Returns:
            OperationResult with assignment details or error
        """
        if not instance_arn:
            if not self._default_sso_instance_arn:
                raise ValueError("instance_arn must be provided if no default is set")
            instance_arn = self._default_sso_instance_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=role_arn
        )
        return execute_aws_api_call(
            "sso-admin",
            "create_account_assignment",
            InstanceArn=instance_arn,
            PermissionSetArn=permission_set_arn,
            PrincipalId=principal_id,
            PrincipalType=principal_type,
            TargetId=target_id,
            TargetType=target_type,
            **client_kwargs,
            **kwargs,
        )

    def delete_account_assignment(
        self,
        permission_set_arn: str,
        principal_id: str,
        principal_type: str,
        target_id: str,
        target_type: str = "AWS_ACCOUNT",
        instance_arn: Optional[str] = None,
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
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters

        Returns:
            OperationResult with status or error
        """
        if not instance_arn:
            if not self._default_sso_instance_arn:
                raise ValueError("instance_arn must be provided if no default is set")
            instance_arn = self._default_sso_instance_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=role_arn
        )
        return execute_aws_api_call(
            "sso-admin",
            "delete_account_assignment",
            InstanceArn=instance_arn,
            PermissionSetArn=permission_set_arn,
            PrincipalId=principal_id,
            PrincipalType=principal_type,
            TargetId=target_id,
            TargetType=target_type,
            **client_kwargs,
            **kwargs,
        )

    def list_account_assignments(
        self,
        principal_id: str,
        principal_type: str,
        instance_arn: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """List account assignments for a principal.

        Args:
            instance_arn: ARN of the SSO instance
            principal_id: ID of the principal (user or group)
            principal_type: Type of principal ('USER' or 'GROUP')
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters

        Returns:
            OperationResult with list of assignments or error
        """
        if not instance_arn:
            if not self._default_sso_instance_arn:
                raise ValueError("instance_arn must be provided if no default is set")
            instance_arn = self._default_sso_instance_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=role_arn
        )
        return execute_aws_api_call(
            "sso-admin",
            "list_account_assignments",
            InstanceArn=instance_arn,
            PrincipalId=principal_id,
            PrincipalType=principal_type,
            **client_kwargs,
            **kwargs,
        )

    def list_permission_sets(
        self,
        instance_arn: Optional[str] = None,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """List permission sets in the SSO instance.

        Args:
            instance_arn: ARN of the SSO instance
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters
        Returns:
            OperationResult with list of permission sets or error
        """
        if not instance_arn:
            if not self._default_sso_instance_arn:
                raise ValueError("instance_arn must be provided if no default is set")
            instance_arn = self._default_sso_instance_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=role_arn
        )
        return execute_aws_api_call(
            "sso-admin",
            "list_permission_sets",
            InstanceArn=instance_arn,
            **client_kwargs,
            **kwargs,
        )

    def healthcheck(
        self, instance_arn: Optional[str] = None, role_arn: Optional[str] = None
    ) -> OperationResult:
        """Lightweight health check for SSO Admin.

        Calls `list_account_assignments` if an `instance_arn` is provided; otherwise
        attempts a no-arg list call where supported.
        """
        if not instance_arn:
            if not self._default_sso_instance_arn:
                raise ValueError("instance_arn must be provided if no default is set")
            instance_arn = self._default_sso_instance_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=role_arn
        )
        return execute_aws_api_call(
            "sso-admin",
            "list_permission_sets",
            InstanceArn=instance_arn,
            max_retries=0,
            **client_kwargs,
        )
