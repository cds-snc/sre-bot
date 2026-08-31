"""Directory provider factory — pure backend constructors, no dispatch."""

from __future__ import annotations

from functools import cache, partial
from typing import TYPE_CHECKING

from infrastructure.configuration.infrastructure.directory import get_directory_settings
from infrastructure.configuration.integrations.google import get_google_workspace_settings
from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.provider import DirectoryProvider
from integrations.google_workspace.client import get_admin_directory_service

if TYPE_CHECKING:
    from collections.abc import Callable

    from googleapiclient._apis.admin.directory_v1 import DirectoryResource as AdminDirectoryResource

    from infrastructure.configuration.infrastructure import DirectorySettings


def build_google_directory_provider(
    get_service: Callable[[list[str]], AdminDirectoryResource],
    directory_settings: DirectorySettings,
    customer_id: str,
) -> DirectoryProvider:
    """Build a GoogleDirectoryProvider with an injected, per-call scoped service factory.

    Args:
        get_service: Factory building a scoped Admin Directory Resource for a
            given OAuth scope list — called once per operation, preserving
            today's per-call least-privilege delegated-credential behaviour.
        directory_settings: Directory provider settings.
        customer_id: Google Workspace customer ID used by directory operations.

    Returns:
        DirectoryProvider: GoogleDirectoryProvider instance.
    """
    return GoogleDirectoryProvider(
        get_service=get_service,
        directory_settings=directory_settings,
        customer_id=customer_id,
    )


@cache
def get_directory_provider() -> DirectoryProvider:
    """Singleton accessor for the configured DirectoryProvider implementation."""

    directory_settings = get_directory_settings()
    provider_key = directory_settings.provider
    if provider_key == "google":
        workspace_settings = get_google_workspace_settings()
        get_service = partial(
            get_admin_directory_service,
            delegated_user_email=workspace_settings.SRE_BOT_EMAIL or None,
        )
        return build_google_directory_provider(
            get_service=get_service,
            directory_settings=directory_settings,
            customer_id=workspace_settings.GOOGLE_WORKSPACE_CUSTOMER_ID,
        )
    raise ValueError(f"Unsupported directory provider: {provider_key!r}")
