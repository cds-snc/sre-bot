"""AWS SSO Admin adapter.

Holds a typed boto3 sso-admin client built by ``get_aws_client``, calls the
SDK directly, classifies expected SDK errors with ``classify_aws_error`` and
returns ``OperationResult`` at every operation.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from infrastructure.operations import OperationResult

if TYPE_CHECKING:
    from types_boto3_sso_admin.client import SSOAdminClient


class SsoAdminAdapter:
    """SSO Admin operations returning ``OperationResult``."""

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

    def _call[T](self, operation: str, fn: Callable[[], T]) -> OperationResult[T]:
        """Run one SDK call, classifying ClientError/BotoCoreError; anything else propagates."""
        raise NotImplementedError

    def _paginate(self, paginator_name: str, response_key: str, **kwargs: Any) -> OperationResult[list[dict[str, Any]]]:
        """Flatten every page of a paginated operation into one list."""
        raise NotImplementedError

    def create_account_assignment(
        self,
        user_id: str,
        account_id: str,
        permission_set: str,
        principal_type: str = "USER",
    ) -> OperationResult[bool]:
        """Create an account assignment."""
        raise NotImplementedError

    def delete_account_assignment(
        self,
        user_id: str,
        account_id: str,
        permission_set: str,
    ) -> OperationResult[bool]:
        """Delete an account assignment."""
        raise NotImplementedError

    def list_account_assignments_for_principal(
        self,
        principal_id: str,
        principal_type: str = "USER",
    ) -> OperationResult[list[dict[str, Any]]]:
        """List account assignments for a principal."""
        raise NotImplementedError


def build_sso_admin_adapter() -> SsoAdminAdapter:
    """Build the SSO Admin adapter."""
    raise NotImplementedError
