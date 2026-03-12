"""Directory provider factory — explicit dispatch, no runtime discovery.

Factory functions receive all external dependencies as arguments.  The
@lru_cache singleton accessor in infrastructure.services.providers is the
single point that calls get_settings() and get_google_workspace_clients()
and passes the results here.
"""

from infrastructure.clients.google_workspace import GoogleWorkspaceClients
from infrastructure.configuration import Settings
from infrastructure.directory.google import GoogleDirectoryProvider
from infrastructure.directory.provider import DirectoryProvider


def build_directory_provider(
    settings: Settings,
    google_clients: GoogleWorkspaceClients,
) -> DirectoryProvider:
    """Build a DirectoryProvider for the configured IDP backend.

    Args:
        settings: Application settings — settings.directory.provider selects
            which implementation to activate.
        google_clients: Google Workspace clients facade, passed through to the
            Google implementation when selected.

    Returns:
        DirectoryProvider: Configured provider instance.

    Raises:
        ValueError: When settings.directory.provider names an unimplemented backend.
    """
    provider_key = settings.directory.provider
    if provider_key == "google":
        return build_google_directory_provider(google_clients=google_clients)
    raise ValueError(f"Unsupported directory provider: {provider_key!r}")


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
