"""Directory provider factory — pure backend constructors, no dispatch."""

from __future__ import annotations

from functools import cache, partial
from typing import TYPE_CHECKING

from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.provider import DirectoryProvider
from integrations.google_workspace.client import get_admin_directory_service
from integrations.google_workspace.settings import get_google_workspace_settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from googleapiclient._apis.admin.directory_v1 import DirectoryResource as AdminDirectoryResource


def build_google_directory_provider(
    get_service: Callable[[list[str]], AdminDirectoryResource],
    customer_id: str,
) -> DirectoryProvider:
    """Build a GoogleDirectoryProvider with an injected, per-call scoped service factory.

    Args:
        get_service: Factory building a scoped Admin Directory Resource for a
            given OAuth scope list — called once per operation, preserving
            today's per-call least-privilege delegated-credential behaviour.
        customer_id: Google Workspace customer ID used by directory operations.

    Returns:
        DirectoryProvider: GoogleDirectoryProvider instance.
    """
    return GoogleDirectoryProvider(
        get_service=get_service,
        customer_id=customer_id,
    )


@cache
def get_directory_provider() -> DirectoryProvider:
    """Singleton accessor for the DirectoryProvider: the Google adapter, the only one today."""
    tenant = get_google_workspace_settings().tenant
    get_service = partial(
        get_admin_directory_service,
        delegated_user_email=tenant.delegated_user_email if tenant is not None else None,
    )
    return build_google_directory_provider(
        get_service=get_service,
        # Without the Google entry there is no key either, so no call ever sends the empty id.
        customer_id=tenant.customer_id if tenant is not None else "",
    )
