"""AWS Clients facade for all AWS service operations.

Provides attribute-based access to per-service clients (DynamoDB, Identity Store,
Organizations, SSO Admin) with consistent error handling and OperationResult return types.

Composition-based design: each service has a focused client class, composed together
in a lightweight facade.
"""

from typing import Optional

import structlog

from infrastructure.clients.aws.dynamodb import DynamoDBClient
from infrastructure.clients.aws.identity_store import IdentityStoreClient
from infrastructure.clients.aws.organizations import OrganizationsClient
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.clients.aws.sso_admin import SsoAdminClient

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

    def __init__(
        self,
        session_provider: SessionProvider,
        default_identity_store_id: Optional[str] = None,
    ) -> None:
        self.dynamodb: DynamoDBClient = DynamoDBClient(session_provider)
        self.identitystore: IdentityStoreClient = IdentityStoreClient(
            session_provider, default_identity_store_id
        )
        self.organizations: OrganizationsClient = OrganizationsClient(session_provider)
        self.sso_admin: SsoAdminClient = SsoAdminClient(session_provider)
        self._logger = logger.bind(component="aws_clients")
