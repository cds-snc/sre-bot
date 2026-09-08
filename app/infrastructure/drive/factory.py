"""Factory for the configured Drive provider."""

from collections.abc import Callable
from functools import cache, partial
from typing import Any

from infrastructure.configuration.integrations.google import get_google_workspace_settings
from infrastructure.drive.google import GoogleDriveProvider
from infrastructure.drive.provider import DriveProvider
from infrastructure.drive.settings import DriveSettings, get_drive_settings
from integrations.google_workspace.client import get_drive_service


def build_google_drive_provider(
    *,
    get_service: Callable[[list[str], str | None], Any],
    drive_settings: DriveSettings,
) -> DriveProvider:
    """Build a Google Drive provider with an injected service factory."""
    return GoogleDriveProvider(get_service=get_service, drive_settings=drive_settings)


@cache
def get_drive_provider() -> DriveProvider:
    """Return the singleton configured Drive provider."""
    drive_settings = get_drive_settings()
    if drive_settings.provider == "google":
        workspace_settings = get_google_workspace_settings()
        get_service = partial(get_drive_service, delegated_user_email=workspace_settings.SRE_BOT_EMAIL or None)
        return build_google_drive_provider(get_service=get_service, drive_settings=drive_settings)
    raise ValueError(f"Unsupported drive provider: {drive_settings.provider!r}")
