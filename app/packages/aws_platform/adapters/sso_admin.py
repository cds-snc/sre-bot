"""AWS SSO Admin adapter.

Holds a typed boto3 sso-admin client built by ``get_aws_client``, calls the SDK
directly (pagination through ``get_paginator``), classifies expected SDK errors
with ``classify_aws_error`` and returns ``OperationResult`` at every operation.
Programmer errors propagate.

The client carries eagerly assumed STS credentials, so callers build the adapter
with :func:`build_sso_admin_adapter` at function entry, never at import.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations import OperationResult
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings

if TYPE_CHECKING:
    from types_boto3_sso_admin.client import SSOAdminClient

logger = structlog.get_logger()

type _PaginatorName = Literal["list_account_assignments_for_principal"]


class SsoAdminAdapter:
    """SSO Admin account-assignment operations returning ``OperationResult``.

    Args:
        client: sso-admin client.
        instance_arn: ``InstanceArn`` sent on every call.
        system_admin_permissions: permission set ARN the ``"write"`` alias resolves to.
        view_only_permissions: permission set ARN the ``"read"`` alias resolves to.
    """

    def __init__(
        self,
        client: SSOAdminClient,
        instance_arn: str,
        system_admin_permissions: str,
        view_only_permissions: str,
    ) -> None:
        self._client = client
        self._instance_arn = instance_arn
        self._system_admin_permissions = system_admin_permissions
        self._view_only_permissions = view_only_permissions

    # -- error handling -----------------------------------------------------

    @staticmethod
    def _map_sdk_exception(operation: str, exc: Exception) -> OperationResult[Any]:
        """Classify an expected botocore exception into an error result."""
        status, error_code, retry_after = classify_aws_error(exc)
        logger.warning(
            "aws_sso_admin_operation_failed",
            operation=operation,
            status=status.value,
            error_code=error_code,
        )
        return OperationResult.error(
            status,
            message=str(exc),
            error_code=error_code,
            retry_after=retry_after,
            provider="aws",
            operation=operation,
        )

    def _call[T](self, operation: str, fn: Callable[[], T]) -> OperationResult[T]:
        """Run one SDK call, classifying ClientError/BotoCoreError; anything else propagates."""
        try:
            return OperationResult.success(data=fn(), provider="aws", operation=operation)
        except (ClientError, BotoCoreError) as exc:
            return self._map_sdk_exception(operation, exc)

    def _paginate(
        self, paginator_name: _PaginatorName, response_key: str, **kwargs: Any
    ) -> OperationResult[list[dict[str, Any]]]:
        """Flatten every page of a paginated operation into one list."""

        def collect() -> list[dict[str, Any]]:
            paginator = self._client.get_paginator(paginator_name)
            items: list[dict[str, Any]] = []
            for page in paginator.paginate(InstanceArn=self._instance_arn, **kwargs):
                page_items = page.get(response_key, [])
                if isinstance(page_items, list):
                    items.extend(page_items)
            return items

        return self._call(paginator_name, collect)

    def _get_predefined_permission_set(self, permission_set: str) -> str:
        """Resolve the ``"write"``/``"read"`` aliases to configured ARNs; any other value passes through."""
        predefined = {
            "write": self._system_admin_permissions,
            "read": self._view_only_permissions,
        }
        return predefined.get(permission_set, permission_set)

    # -- account assignments ------------------------------------------------

    def create_account_assignment(
        self,
        user_id: str,
        account_id: str,
        permission_set: str,
        principal_type: Literal["USER", "GROUP"] = "USER",
    ) -> OperationResult[bool]:
        """Assign a permission set on an account; data is False only when the initial status is FAILED.

        IN_PROGRESS counts as success: the creation status is not polled.
        """

        def create() -> bool:
            response = self._client.create_account_assignment(
                InstanceArn=self._instance_arn,
                TargetId=account_id,
                TargetType="AWS_ACCOUNT",
                PermissionSetArn=self._get_predefined_permission_set(permission_set),
                PrincipalType=principal_type,
                PrincipalId=user_id,
            )
            return response["AccountAssignmentCreationStatus"].get("Status") != "FAILED"

        return self._call("create_account_assignment", create)

    def delete_account_assignment(
        self,
        user_id: str,
        account_id: str,
        permission_set: str,
    ) -> OperationResult[bool]:
        """Remove a user's permission set on an account; data is False only when the initial status is FAILED.

        IN_PROGRESS counts as success: the deletion status is not polled.
        """

        def delete() -> bool:
            response = self._client.delete_account_assignment(
                InstanceArn=self._instance_arn,
                TargetId=account_id,
                TargetType="AWS_ACCOUNT",
                PermissionSetArn=self._get_predefined_permission_set(permission_set),
                PrincipalType="USER",
                PrincipalId=user_id,
            )
            return response["AccountAssignmentDeletionStatus"].get("Status") != "FAILED"

        return self._call("delete_account_assignment", delete)

    def list_account_assignments_for_principal(
        self,
        principal_id: str,
        principal_type: Literal["USER", "GROUP"] = "USER",
    ) -> OperationResult[list[dict[str, Any]]]:
        """List every account assignment held by a principal across all pages."""
        return self._paginate(
            "list_account_assignments_for_principal",
            "AccountAssignments",
            PrincipalId=principal_id,
            PrincipalType=principal_type,
        )


def build_sso_admin_adapter() -> SsoAdminAdapter:
    """Build the adapter with the sso-admin role from ``SERVICE_ROLE_MAP`` and the SSO instance settings."""
    settings = get_aws_settings()
    role_arn = settings.SERVICE_ROLE_MAP.get("sso-admin") or None
    return SsoAdminAdapter(
        get_aws_client("sso-admin", role_arn=role_arn),
        instance_arn=settings.INSTANCE_ARN,
        system_admin_permissions=settings.SYSTEM_ADMIN_PERMISSIONS,
        view_only_permissions=settings.VIEW_ONLY_PERMISSIONS,
    )
