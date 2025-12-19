"""AWS Clients facade for all AWS service operations.

Provides attribute-based access to per-service clients (DynamoDB, Identity Store,
Organizations, SSO Admin) with consistent error handling and OperationResult return types.

Composition-based design: each service has a focused client class, composed together
in a lightweight facade.
"""

import structlog

from infrastructure.clients.aws.config import ConfigClient
from infrastructure.clients.aws.cost_explorer import CostExplorerClient
from infrastructure.clients.aws.dynamodb import DynamoDBClient
from infrastructure.clients.aws.guard_duty import GuardDutyClient
from infrastructure.clients.aws.health import AWSIntegrationHealth
from infrastructure.clients.aws.identity_store import IdentityStoreClient
from infrastructure.clients.aws.organizations import OrganizationsClient
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.clients.aws.sso_admin import SsoAdminClient
from infrastructure.configuration.integrations.aws import AwsSettings

logger = structlog.get_logger()


class AWSClients:
    """Facade for all AWS service clients.

    Composes per-service clients (DynamoDB, Identity Store, Organizations, SSO Admin)
    and exposes them as attributes for natural IDE discoverability and grouped access.

    Each service client is initialized with a shared SessionProvider that handles
    credential management, region configuration, and role assumption.

    Args:
        session_provider: SessionProvider instance for credential/config management
        default_identity_store_id: Default Identity Store ID (passed to IdentityStoreClient)

    Usage:
        @router.get("/items/{item_id}")
        def get_item(item_id: str, aws: AWSClientsDep):
            result = aws.dynamodb.get_item("my_table", {"id": {"S": item_id}})
            if result.is_success:
                return result.data
    """

    def __init__(self, aws_settings: AwsSettings) -> None:
        """Initialize AWS clients facade with settings.

        Args:
            aws_settings: AWS configuration from settings.aws
        """
        self._session_provider = SessionProvider(
            region=aws_settings.AWS_REGION,
            service_role_map=aws_settings.SERVICE_ROLE_MAP,
            endpoint_url=getattr(aws_settings, "ENDPOINT_URL", None),
        )

        self.dynamodb: DynamoDBClient = DynamoDBClient(
            self._session_provider,
            default_role_arn=self._session_provider.get_role_arn_for_service(
                "dynamodb"
            ),
        )
        self.identitystore: IdentityStoreClient = IdentityStoreClient(
            self._session_provider,
            default_identity_store_id=aws_settings.INSTANCE_ID,
        )
        self.organizations: OrganizationsClient = OrganizationsClient(
            self._session_provider,
            default_role_arn=self._session_provider.get_role_arn_for_service(
                "organizations"
            ),
        )
        self.sso_admin: SsoAdminClient = SsoAdminClient(
            self._session_provider,
            default_sso_instance_arn=aws_settings.INSTANCE_ARN,
        )
        self.config: ConfigClient = ConfigClient(
            self._session_provider,
            default_role_arn=self._session_provider.get_role_arn_for_service("config"),
        )
        self.guardduty: GuardDutyClient = GuardDutyClient(
            self._session_provider,
            default_role_arn=self._session_provider.get_role_arn_for_service(
                "guardduty"
            ),
        )
        self.cost_explorer: CostExplorerClient = CostExplorerClient(
            self._session_provider,
            default_role_arn=self._session_provider.get_role_arn_for_service("ce"),
        )
        self.health: AWSIntegrationHealth = AWSIntegrationHealth(
            self._session_provider,
            default_identity_store_id=aws_settings.INSTANCE_ID,
            default_sso_instance_arn=aws_settings.INSTANCE_ARN,
        )
        self._logger = logger.bind(component="aws_clients")
