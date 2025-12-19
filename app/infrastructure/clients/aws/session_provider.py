"""Session provider for AWS client operations.

Centralizes boto3 session creation, credential management, and configuration
building for all AWS service clients. Handles role assumption and parameter
propagation for cross-account access.
"""

from typing import Any, Dict, Optional

import structlog

from infrastructure.clients.aws.executor import get_boto3_client

logger = structlog.get_logger()


class SessionProvider:
    """Centralized provider for AWS session configuration and credential handling.

    Manages region, endpoint URL, and role assumption logic so per-service
    clients don't need to duplicate this code.

    Args:
        region: AWS region for all clients (e.g., 'us-east-1')
        endpoint_url: Custom endpoint URL (for testing/LocalStack)
    """

    def __init__(
        self,
        region: Optional[str] = None,
        service_role_map: Optional[dict[str, str]] = None,
        endpoint_url: Optional[str] = None,
    ) -> None:
        self.region = region
        self.service_role_map = service_role_map
        self.endpoint_url = endpoint_url

    def get_role_arn_for_service(self, service_name: str) -> Optional[str]:
        """Get the role ARN to assume for the given AWS service.

        Args:
            service_name: AWS service name (e.g., 'dynamodb')
        Returns:
            Role ARN string or None if no role is configured for the service
        """
        logger.debug("resolving_role_arn", service_name=service_name)
        if self.service_role_map and service_name in self.service_role_map:
            return self.service_role_map[service_name]
        return None

    def build_client_kwargs(
        self,
        service_name: Optional[str] = None,
        role_arn: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build session and client configuration kwargs for boto3.

        Automatically resolves the role ARN from the service_role_map if
        service_name is provided and role_arn is not explicitly given.

        Args:
            service_name: AWS service name (e.g., 'dynamodb') for role lookup
            role_arn: Optional cross-account role ARN to assume. If not provided,
                      attempts to resolve from service_role_map using service_name.

        Returns:
            Dict with session_config, client_config, and role_arn for
            passing to execute_aws_api_call
        """
        # Resolve role from map if not provided
        logger.debug(
            "building_client_kwargs",
            service_name=service_name,
            role_arn=role_arn,
        )
        if role_arn is None and service_name:
            role_arn = self.get_role_arn_for_service(service_name)

        session_config = {}
        client_config = {}

        if self.region:
            session_config["region_name"] = self.region
            client_config["region_name"] = self.region

        if self.endpoint_url:
            client_config["endpoint_url"] = self.endpoint_url

        logger.debug(
            "built_client_kwargs",
            session_config=session_config,
            client_config=client_config,
            role_arn=role_arn,
        )
        return {
            "session_config": session_config or None,
            "client_config": client_config or None,
            "role_arn": role_arn,
        }

    def get_boto3_client(
        self, service_name: str, role_arn: Optional[str] = None
    ) -> Any:
        """Get a fully-configured boto3 client for the given service.

        Args:
            service_name: AWS service name (e.g., 'dynamodb')
            role_arn: Optional cross-account role ARN to assume

        Returns:
            Configured boto3 client instance
        """
        kw = self.build_client_kwargs(role_arn)
        return get_boto3_client(
            service_name,
            session_config=kw["session_config"],
            client_config=kw["client_config"],
            role_arn=kw["role_arn"],
        )
