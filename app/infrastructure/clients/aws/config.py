"""AWS Config client implementation.

Provides operations to interact with AWS Config service, enabling retrieval of configuration compliance and resource details, with consistent error handling via OperationResult.
"""

from typing import Any, Dict, Optional

from infrastructure.clients.aws.executor import execute_aws_api_call
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.operations.result import OperationResult


class ConfigClient:
    """Client for AWS Config service operations.

    This class wraps calls to the AWS Config APIs using the centralized
    `execute_aws_api_call` helper which returns an `OperationResult`.
    """

    def __init__(
        self,
        session_provider: SessionProvider,
        default_role_arn: Optional[str] = None,
    ) -> None:
        self._session_provider = session_provider
        self._default_role_arn = default_role_arn
        self._service_name = "config"

    # TODO: Add support for role_arn parameters to override default_role_arn
    def describe_aggregate_compliance_by_config_rules(
        self, config_aggregator_name: str, filters: Optional[Dict[str, Any]] = None
    ) -> OperationResult:
        """Describe aggregate compliance by config rules.

        Returns an OperationResult whose `data` is a list of compliance objects
        when successful.
        """
        params: Dict[str, Any] = {
            "ConfigurationAggregatorName": config_aggregator_name,
            "Filters": filters,
        }

        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self._service_name, role_arn=self._default_role_arn
        )

        result = execute_aws_api_call(
            "config",
            "describe_aggregate_compliance_by_config_rules",
            paginated=True,
            keys=["AggregateComplianceByConfigRules"],
            **client_kwargs,
            **params,
        )

        return result
