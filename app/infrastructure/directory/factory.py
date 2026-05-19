"""Directory provider factory — pure backend constructors, no dispatch.

Each ``build_*`` function is a thin constructor that accepts injected client
dependencies and returns a configured DirectoryProvider implementation.

Dispatch (which backend to build based on settings.directory.provider) lives
in ``infrastructure.services.providers``, which owns all client singletons and
is the single orchestration point for dependency wiring.

Adding a new backend:
    1. Implement a new DirectoryProvider class in ``infrastructure/directory/``.
    2. Add a ``build_<name>_directory_provider()`` function here, receiving its
       client facade(s) as typed arguments.
    3. Add the dispatch branch in ``infrastructure.services.providers.get_directory_provider``.
"""

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
    directory_settings: "DirectorySettings",
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
