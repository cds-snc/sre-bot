"""Infrastructure AWS clients public API.

This package provides DI-friendly AWS clients with per-service class decomposition.

The main facade is AWSClients, which composes per-service clients (DynamoDB,
IdentityStore, Organizations, SsoAdmin) and exposes them as attributes.
"""

from infrastructure.clients.aws.config import ConfigClient
from infrastructure.clients.aws.cost_explorer import CostExplorerClient
from infrastructure.clients.aws.dynamodb import DynamoDBClient
from infrastructure.clients.aws.facade import AWSClients, get_aws_clients
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
    "ConfigClient",
    "GuardDutyClient",
    "CostExplorerClient",
    "get_aws_clients",
]
