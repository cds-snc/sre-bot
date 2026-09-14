"""AWS Organizations adapter.

Holds a typed boto3 organizations client built by ``get_aws_client``, calls the
SDK directly (pagination through ``get_paginator``), classifies expected SDK
errors with ``classify_aws_error`` and returns ``OperationResult`` at every
operation. Programmer errors propagate.

The client carries eagerly assumed STS credentials, so callers build the adapter
with :func:`build_organizations_adapter` at function entry, never at import.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations import OperationResult
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings

if TYPE_CHECKING:
    from types_boto3_organizations.client import OrganizationsClient

logger = structlog.get_logger()

type _PaginatorName = Literal["list_accounts", "list_tags_for_resource"]


class OrganizationsAdapter:
    """Organizations operations returning ``OperationResult``.

    Args:
        client: organizations client; every operation is a read.
    """

    def __init__(self, client: OrganizationsClient) -> None:
        self._client = client

    # -- error handling -----------------------------------------------------

    @staticmethod
    def _map_sdk_exception(operation: str, exc: Exception) -> OperationResult[Any]:
        """Classify an expected botocore exception into an error result."""
        status, error_code, retry_after = classify_aws_error(exc)
        logger.warning(
            "aws_organizations_operation_failed",
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
            for page in paginator.paginate(**kwargs):
                page_items = page.get(response_key, [])
                if isinstance(page_items, list):
                    items.extend(page_items)
            return items

        return self._call(paginator_name, collect)

    # -- health -------------------------------------------------------------

    def healthcheck(self) -> OperationResult[bool]:
        """Healthy when a single-account ListAccounts call succeeds, whether or not it returns accounts."""

        def check() -> bool:
            self._client.list_accounts(MaxResults=1)
            return True

        return self._call("healthcheck", check)

    # -- accounts -----------------------------------------------------------

    def list_organization_accounts(self) -> OperationResult[list[dict[str, Any]]]:
        """List every account in the organization across all pages."""
        return self._paginate("list_accounts", "Accounts")

    def get_account_details(self, account_id: str) -> OperationResult[dict[str, Any]]:
        """Describe one account by id."""

        def describe() -> dict[str, Any]:
            account: dict[str, Any] = {**self._client.describe_account(AccountId=account_id)["Account"]}
            return account

        return self._call("describe_account", describe)

    def get_account_tags(self, account_id: str) -> OperationResult[list[dict[str, Any]]]:
        """List every tag on an account across all ListTagsForResource pages."""
        return self._paginate("list_tags_for_resource", "Tags", ResourceId=account_id)


def build_organizations_adapter() -> OrganizationsAdapter:
    """Build the adapter with the organizations role from ``SERVICE_ROLE_MAP``."""
    role_arn = get_aws_settings().SERVICE_ROLE_MAP.get("organizations") or None
    return OrganizationsAdapter(get_aws_client("organizations", role_arn=role_arn))
