"""Infrastructure AWS clients public API.

This package provides DI-friendly AWS client factory that returns
`OperationResult` and avoids module-level configuration reads.

Use the factory through the dependency injection system:

    from infrastructure.services.dependencies import AWSClientDep

    @router.post("/accounts")
    def create_account(aws: AWSClientDep):
        result = aws.create_account_assignment(store_id, principal_id, ...)
        if result.is_success:
            return {"assignment_id": result.data}

For high-level helper operations (batch, orchestration), use AWSHelpers:

    from infrastructure.services.dependencies import AWSHelpersDep

    @router.get("/groups/{store_id}")
    def list_groups(helpers: AWSHelpersDep):
        result = helpers.list_groups_with_memberships(store_id)
        if result.is_success:
            return result.data

All infrastructure services are accessed through `infrastructure/services/`
as the single point of entry for dependency injection.
"""

from infrastructure.clients.aws.factory import AWSClientFactory
from infrastructure.clients.aws.helpers import AWSHelpers

__all__ = [
    "AWSClientFactory",
    "AWSHelpers",
]
