"""Infrastructure AWS clients public API.

This package provides DI-friendly AWS client wrappers that return
`OperationResult` and avoid module-level configuration reads.

Use the provider functions in `infrastructure.services` to expose
dependencies to FastAPI routes and other code.
"""

from .client import execute_aws_api_call, get_boto3_client

# DynamoDB operations
from .dynamodb import (
    get_item,
    put_item,
    update_item,
    delete_item,
    query,
    scan,
)

# Identity store operations
from .identity_store import (
    get_user,
    get_user_by_username,
    list_users,
    create_user,
    delete_user,
)

# Organizations
from .organizations import (
    list_organization_accounts,
    get_account_details,
    get_account_id_by_name,
)

# SSO Admin
from .sso import (
    create_account_assignment,
    delete_account_assignment,
    list_account_assignments_for_principal,
)

__all__ = [
    "execute_aws_api_call",
    "get_boto3_client",
    "get_item",
    "put_item",
    "update_item",
    "delete_item",
    "query",
    "scan",
    "get_user",
    "get_user_by_username",
    "list_users",
    "create_user",
    "delete_user",
    "list_organization_accounts",
    "get_account_details",
    "get_account_id_by_name",
    "create_account_assignment",
    "delete_account_assignment",
    "list_account_assignments_for_principal",
]
