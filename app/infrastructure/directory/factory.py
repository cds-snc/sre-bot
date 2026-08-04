"""Directory provider factory — pure backend constructors, no dispatch."""

from functools import cache
from typing import TYPE_CHECKING

from infrastructure.clients.google_workspace import (
    GoogleWorkspaceClients,
    get_google_workspace_clients,
)
from infrastructure.configuration.infrastructure.directory import get_directory_settings
from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.provider import DirectoryProvider

if TYPE_CHECKING:
    from infrastructure.configuration.infrastructure import DirectorySettings


def build_google_directory_provider(
    google_clients: GoogleWorkspaceClients,
    directory_settings: DirectorySettings,
) -> DirectoryProvider:
    """Build a GoogleDirectoryProvider with injected clients.

    Args:
        google_clients: Google Workspace clients facade.
        directory_settings: Directory provider settings.

    Returns:
        DirectoryProvider: GoogleDirectoryProvider instance.
    """
    return GoogleDirectoryProvider(
        google_clients=google_clients,
        directory_settings=directory_settings,
    )


@cache
def get_directory_provider() -> DirectoryProvider:
    """Singleton accessor for the configured DirectoryProvider implementation."""

    directory_settings = get_directory_settings()
    provider_key = directory_settings.provider
    if provider_key == "google":
        return build_google_directory_provider(
            google_clients=get_google_workspace_clients(),
            directory_settings=directory_settings,
        )
    raise ValueError(f"Unsupported directory provider: {provider_key!r}")
