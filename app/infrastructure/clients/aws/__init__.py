"""Infrastructure AWS clients public API.

This package provides DI-friendly AWS client factory that returns
`OperationResult` and avoids module-level configuration reads.

Use the provider functions in `infrastructure.services` to expose
dependencies to FastAPI routes and other code.
"""

from infrastructure.clients.aws.client import execute_aws_api_call, get_boto3_client
from infrastructure.clients.aws.factory import AWSClientFactory
from infrastructure.clients.aws.helpers import (
    get_batch_users,
    get_batch_groups,
    list_groups_with_memberships,
    healthcheck,
)


__all__ = [
    "execute_aws_api_call",
    "get_boto3_client",
    "AWSClientFactory",
    "get_batch_users",
    "get_batch_groups",
    "list_groups_with_memberships",
    "healthcheck",
]
