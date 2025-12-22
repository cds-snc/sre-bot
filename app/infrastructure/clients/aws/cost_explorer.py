"""AWS Cost Explorer client implementation.

Provides operations to interact with AWS Cost Explorer service, enabling retrieval of cost and usage data with consistent error handling via OperationResult.
"""

from typing import Any, Dict, Optional

import structlog

from infrastructure.clients.aws.executor import execute_aws_api_call
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.operations.result import OperationResult


logger = structlog.get_logger()


class CostExplorerClient:
    """Client for AWS Cost Explorer service operations.

    This class wraps calls to the AWS Cost Explorer APIs using the centralized
    `execute_aws_api_call` helper which returns an `OperationResult`.
    """

    def __init__(
        self,
        session_provider: SessionProvider,
        default_role_arn: Optional[str] = None,
    ) -> None:
        self._session_provider = session_provider
        self._default_role_arn = default_role_arn
        self.service_name = "ce"

    def get_cost_and_usage(
        self, time_period: Dict[str, str], metrics: list, **kwargs
    ) -> OperationResult:
        """Get cost and usage data from AWS Cost Explorer.

        Returns an OperationResult whose `data` contains the cost and usage details
        when successful.
        """
        params: Dict[str, Any] = {
            "TimePeriod": time_period,
            "Metrics": metrics,
            **kwargs,
        }

        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self.service_name,
            role_arn=self._default_role_arn,
        )
        result = execute_aws_api_call(
            "ce",
            "get_cost_and_usage",
            **client_kwargs,
            **params,
        )

        return result
