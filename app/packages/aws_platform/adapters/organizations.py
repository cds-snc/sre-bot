"""AWS Organizations adapter.

Holds a typed boto3 organizations client built by ``get_aws_client``, calls the
SDK directly, classifies expected SDK errors with ``classify_aws_error`` and
returns ``OperationResult`` at every operation.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from infrastructure.operations import OperationResult

if TYPE_CHECKING:
    from types_boto3_organizations.client import OrganizationsClient


class OrganizationsAdapter:
    """Organizations operations returning ``OperationResult``."""

    def __init__(self, client: OrganizationsClient) -> None:
        self._client = client

    def _call[T](self, operation: str, fn: Callable[[], T]) -> OperationResult[T]:
        """Run one SDK call, classifying ClientError/BotoCoreError; anything else propagates."""
        raise NotImplementedError

    def _paginate(self, paginator_name: str, response_key: str, **kwargs: Any) -> OperationResult[list[dict[str, Any]]]:
        """Flatten every page of a paginated operation into one list."""
        raise NotImplementedError

    def list_organization_accounts(self) -> OperationResult[list[dict[str, Any]]]:
        """List all accounts in the organization."""
        raise NotImplementedError

    def get_account_details(self, account_id: str) -> OperationResult[dict[str, Any]]:
        """Get details for a specific account."""
        raise NotImplementedError

    def get_account_tags(self, account_id: str) -> OperationResult[list[dict[str, Any]]]:
        """Get tags for a specific account."""
        raise NotImplementedError

    def healthcheck(self) -> OperationResult[bool]:
        """Health check operation."""
        raise NotImplementedError


def build_organizations_adapter() -> OrganizationsAdapter:
    """Build the Organizations adapter."""
    raise NotImplementedError
