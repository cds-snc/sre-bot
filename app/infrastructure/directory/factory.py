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

from infrastructure.clients.google_workspace import GoogleWorkspaceClients
from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.provider import DirectoryProvider


def build_google_directory_provider(
    google_clients: GoogleWorkspaceClients,
) -> DirectoryProvider:
    """Build a GoogleDirectoryProvider with injected clients.

    Args:
        google_clients: Google Workspace clients facade.

    Returns:
        DirectoryProvider: GoogleDirectoryProvider instance.
    """
    return GoogleDirectoryProvider(google_clients=google_clients)
