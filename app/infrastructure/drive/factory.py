"""Factory for the configured Drive provider."""

from collections.abc import Callable
from functools import cache
from typing import TYPE_CHECKING

from infrastructure.drive.google import GoogleDriveProvider
from infrastructure.drive.provider import DriveProvider
from infrastructure.drive.settings import DriveSettings, get_drive_settings
from integrations.google_workspace.client import get_drive_service

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import DriveResource  # pyright: ignore[reportMissingModuleSource]


def build_google_drive_provider(
    *,
    get_service: Callable[[list[str], str | None], DriveResource],
    drive_settings: DriveSettings,
) -> DriveProvider:
    """Build a Google Drive provider with an injected service factory."""
    return GoogleDriveProvider(get_service=get_service, drive_settings=drive_settings)


@cache
def get_drive_provider() -> DriveProvider:
    """Return the singleton configured Drive provider."""
    drive_settings = get_drive_settings()
    if drive_settings.provider == "google":
        return build_google_drive_provider(get_service=get_drive_service, drive_settings=drive_settings)
    raise ValueError(f"Unsupported drive provider: {drive_settings.provider!r}")
