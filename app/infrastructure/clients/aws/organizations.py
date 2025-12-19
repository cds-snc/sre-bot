"""Organizations client for AWS operations.

Provides type-safe access to AWS Organizations operations (list_accounts, describe_account, etc.)
with consistent error handling and OperationResult return types.
"""

from typing import Optional

import structlog

from infrastructure.clients.aws.executor import execute_aws_api_call
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.operations.result import OperationResult

logger = structlog.get_logger()


class OrganizationsClient:
    """Client for AWS Organizations operations.

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
        self._service_name = "organizations"
        self._session_provider = session_provider
        self._default_role_arn = default_role_arn
        self._logger = logger.bind(component="organizations_client")

    def list_accounts(
        self,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """List all accounts in the AWS Organization.

        Args:
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters

        Returns:
            OperationResult with list of accounts or error
        """

        effective_role = role_arn or self._default_role_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=effective_role
        )
        self._logger.info("listing_accounts", client_kwargs=client_kwargs)
        return execute_aws_api_call(
            self._service_name,
            "list_accounts",
            **client_kwargs,
            **kwargs,
        )

    def describe_account(
        self,
        account_id: str,
        role_arn: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Get details for a specific AWS account.

        Args:
            account_id: AWS Account ID
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters

        Returns:
            OperationResult with account details or error
        """
        effective_role = role_arn or self._default_role_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=effective_role
        )
        return execute_aws_api_call(
            "organizations",
            "describe_account",
            AccountId=account_id,
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
            role_arn: Optional cross-account role ARN
            **kwargs: Additional parameters

        Returns:
            OperationResult with account ID or error
        """
        log = self._logger.bind(
            method="get_account_id_by_name", account_name=account_name
        )
        log.info("fetching_accounts")

        # List all accounts and search by name
        result = self.list_accounts(
            role_arn=role_arn or self._default_role_arn, **kwargs
        )
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

    def healthcheck(self, role_arn: Optional[str] = None) -> OperationResult:
        """Lightweight health check for Organizations.

        Calls `list_accounts` with minimal retries to validate access to Organizations API.
        """
        effective_role = role_arn or self._default_role_arn
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=effective_role
        )
        return execute_aws_api_call(
            "organizations",
            "list_accounts",
            max_retries=0,
            **client_kwargs,
        )
