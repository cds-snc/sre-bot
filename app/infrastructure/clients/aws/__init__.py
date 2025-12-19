"""Infrastructure AWS clients public API.

This package provides DI-friendly AWS clients with per-service class decomposition.

The main facade is AWSClients, which composes per-service clients (DynamoDB,
IdentityStore, Organizations, SsoAdmin) and exposes them as attributes:

    from infrastructure.services.dependencies import AWSClientsDep

    @router.post("/accounts")
    def create_account(aws: AWSClientsDep):
        result = aws.dynamodb.get_item("my_table", {"id": {"S": "123"}})
        if result.is_success:
            return result.data

        result = aws.identitystore.list_users(store_id)
        if result.is_success:
            return result.data

All infrastructure services are accessed through `infrastructure/services/`
as the single point of entry for dependency injection.
"""

from infrastructure.clients.aws.cost_explorer import CostExplorerClient
from infrastructure.clients.aws.dynamodb import DynamoDBClient
from infrastructure.clients.aws.facade import AWSClients
from infrastructure.clients.aws.guard_duty import GuardDutyClient
from infrastructure.clients.aws.identity_store import IdentityStoreClient
from infrastructure.clients.aws.organizations import OrganizationsClient
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.clients.aws.sso_admin import SsoAdminClient

__all__ = [
    "AWSClients",
    "SessionProvider",
    "DynamoDBClient",
    "IdentityStoreClient",
    "OrganizationsClient",
    "SsoAdminClient",
    "GuardDutyClient",
    "CostExplorerClient",
]
