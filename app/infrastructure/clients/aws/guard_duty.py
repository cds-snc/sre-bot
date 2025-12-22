"""AWS GuardDuty client implementation.

Provides operations to interact with AWS GuardDuty service, enabling retrieval of detectors and findings statistics with consistent error handling via OperationResult.
"""

from typing import Optional

import structlog

from infrastructure.clients.aws.executor import execute_aws_api_call
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.operations.result import OperationResult

logger = structlog.get_logger()


class GuardDutyClient:
    """Client for AWS GuardDuty service operations.

    This class wraps calls to the AWS GuardDuty APIs using the centralized
    `execute_aws_api_call` helper which returns an `OperationResult`.
    """

    def __init__(
        self,
        session_provider: SessionProvider,
        default_role_arn: Optional[str] = None,
    ) -> None:
        self._session_provider = session_provider
        self._default_role_arn = default_role_arn
        self.service_name = "guardduty"

    def list_detectors(self) -> OperationResult:
        """List GuardDuty detectors.

        Returns an OperationResult whose `data` is a list of detector IDs
        when successful.
        """
        client_kwargs = self._session_provider.build_client_kwargs(
            service_name=self.service_name,
            role_arn=self._default_role_arn,
        )
        return execute_aws_api_call(
            "guardduty",
            "list_detectors",
            paginated=True,
            keys=["DetectorIds"],
            **client_kwargs,
        )

    def healthcheck(self) -> OperationResult:
        """Perform a healthcheck by listing detectors.

        Returns an OperationResult indicating success or failure.
        """
        return self.list_detectors()
