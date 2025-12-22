"""AWS Health client for checking the health of AWS services.

Provides aggregated health check operations for AWS services, enabling monitoring and alerting for service availability and performance issues.
"""

from typing import Callable, Dict, Iterable, Optional

import structlog

from infrastructure.clients.aws.config import ConfigClient
from infrastructure.clients.aws.cost_explorer import CostExplorerClient
from infrastructure.clients.aws.dynamodb import DynamoDBClient
from infrastructure.clients.aws.guard_duty import GuardDutyClient
from infrastructure.clients.aws.identity_store import IdentityStoreClient
from infrastructure.clients.aws.organizations import OrganizationsClient
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.clients.aws.sso_admin import SsoAdminClient
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

logger = structlog.get_logger()


class AWSIntegrationHealth:
    """Health check operations aggregator for AWS services.

    Args:
        session_provider: SessionProvider instance for credential/config management
    """

    def __init__(
        self,
        session_provider: SessionProvider,
        default_identity_store_id: Optional[str] = None,
        default_sso_instance_arn: Optional[str] = None,
        config_aggregator_name: Optional[str] = None,
        include_guardduty: bool = True,
        include_cost_explorer: bool = True,
    ) -> None:
        self._session_provider = session_provider
        self._logger = logger.bind(component="aws_integration_health")

        # Clients with defaults inherited from facade
        self.dynamodb: DynamoDBClient = DynamoDBClient(
            session_provider,
            default_role_arn=self._session_provider.get_role_arn_for_service(
                "dynamodb"
            ),
        )
        self.identitystore: IdentityStoreClient = IdentityStoreClient(
            session_provider,
            default_identity_store_id=default_identity_store_id,
        )
        self.organizations: OrganizationsClient = OrganizationsClient(
            session_provider,
            default_role_arn=self._session_provider.get_role_arn_for_service(
                "organizations"
            ),
        )
        self.sso_admin: SsoAdminClient = SsoAdminClient(
            session_provider,
            default_sso_instance_arn=default_sso_instance_arn,
        )
        self.config: ConfigClient = ConfigClient(
            session_provider,
            default_role_arn=self._session_provider.get_role_arn_for_service("config"),
        )
        self.guardduty: Optional[GuardDutyClient] = None
        if include_guardduty:
            self.guardduty = GuardDutyClient(
                session_provider,
                default_role_arn=self._session_provider.get_role_arn_for_service(
                    "guardduty"
                ),
            )
        self.cost_explorer: Optional[CostExplorerClient]
        if include_cost_explorer:
            self.cost_explorer = CostExplorerClient(
                session_provider,
                default_role_arn=self._session_provider.get_role_arn_for_service("ce"),
            )
        else:
            self.cost_explorer = None

        self._config_aggregator_name = config_aggregator_name

        # Registry of cheap health checks per service
        self._checks: Dict[str, Callable[[], OperationResult]] = {
            "dynamodb": self._check_dynamodb,
            "identitystore": self._check_identity_store,
            "organizations": self._check_organizations,
            "sso-admin": self._check_sso_admin,
            "config": self._check_config,
        }
        if self.guardduty:
            self._checks["guardduty"] = self._check_guardduty
        if self.cost_explorer:
            self._checks["ce"] = self._check_cost_explorer

    def check_service_health(self, service_name: str) -> OperationResult:
        """Check health for a single AWS service.

        Returns OperationResult with success/error and timing metadata.
        """
        check = self._checks.get(service_name)
        if not check:
            return OperationResult.permanent_error(
                message=f"Service '{service_name}' is not registered for health checks",
                error_code="SERVICE_NOT_REGISTERED",
            )
        return check()

    def check_all(
        self,
        include: Optional[Iterable[str]] = None,
        exclude: Optional[Iterable[str]] = None,
    ) -> OperationResult:
        """Run health checks for all (or filtered) services.

        Returns an OperationResult with per-service results in `data`.
        Overall success is true only if all included services succeed.
        """
        include_set = set(include) if include else set(self._checks.keys())
        exclude_set = set(exclude) if exclude else set()
        services = [s for s in include_set if s not in exclude_set]

        results: Dict[str, OperationResult] = {}
        all_success = True

        for service in sorted(services):
            res = self.check_service_health(service)
            results[service] = res
            if not res.is_success:
                all_success = False

        if all_success:
            return OperationResult.success(
                data={"services": results}, message="All services healthy"
            )
        # Use first failed service's status, or TRANSIENT_ERROR if no results
        first_status = (
            results[next(iter(results))].status
            if results
            else OperationStatus.TRANSIENT_ERROR
        )
        return OperationResult.error(
            status=first_status,
            message="One or more services unhealthy",
            data={"services": results},
        )

    # --- Individual checks ---
    def _check_dynamodb(self) -> OperationResult:
        role = getattr(self.dynamodb, "_default_role_arn", None)
        return self.dynamodb.healthcheck(role_arn=role)

    def _check_identity_store(self) -> OperationResult:
        # Minimal list_users call to validate access; uses default identity store id inside client
        return self.identitystore.list_users(MaxResults=1)

    def _check_organizations(self) -> OperationResult:
        role = getattr(self.organizations, "_default_role_arn", None)
        return self.organizations.list_accounts(role_arn=role, MaxResults=1)

    def _check_sso_admin(self) -> OperationResult:
        # list_permission_sets is lightweight and validates instance access
        return self.sso_admin.list_permission_sets(MaxResults=1)

    def _check_config(self) -> OperationResult:
        if not self._config_aggregator_name:
            return OperationResult.success(
                data={"skipped": True, "reason": "config aggregator not configured"},
                message="Config health check skipped",
            )
        return self.config.describe_aggregate_compliance_by_config_rules(
            config_aggregator_name=self._config_aggregator_name,
            filters=None,
        )

    def _check_guardduty(self) -> OperationResult:
        if not self.guardduty:
            return OperationResult.success(
                data={"skipped": True, "reason": "guardduty not enabled"},
                message="GuardDuty health check skipped",
            )
        return self.guardduty.list_detectors()

    def _check_cost_explorer(self) -> OperationResult:
        if not self.cost_explorer:
            return OperationResult.success(
                data={"skipped": True, "reason": "cost explorer not enabled"},
                message="Cost Explorer health check skipped",
            )
        # Very lightweight: ask for an empty time range? Instead, skip to avoid cost
        return OperationResult.success(
            data={"skipped": True, "reason": "cost explorer check not implemented"},
            message="Cost Explorer health check skipped",
        )
