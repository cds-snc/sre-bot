"""Infrastructure AWS clients public API.

This package provides DI-friendly AWS client factory that returns
`OperationResult` and avoids module-level configuration reads.

Use the factory to access AWS services in your code:

    from infrastructure.clients.aws import AWSClientFactory

    aws = AWSClientFactory(aws_region="us-east-1")
    result = aws.list_users(identity_store_id="...")

For high-level helper operations, import from the helpers module:

    from infrastructure.clients.aws.helpers import list_groups_with_memberships

    result = list_groups_with_memberships(aws, store_id, ...)

Use the provider functions in `infrastructure.services` to expose
dependencies to FastAPI routes.
"""

from infrastructure.clients.aws.factory import AWSClientFactory

__all__ = [
    "AWSClientFactory",
]
