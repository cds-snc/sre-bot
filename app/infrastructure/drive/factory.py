"""Factory for the configured Drive provider."""

from collections.abc import Callable
from functools import cache
from typing import TYPE_CHECKING

from infrastructure.drive.google import GoogleDriveProvider
from infrastructure.drive.provider import DriveProvider
from integrations.google_workspace.client import get_drive_service

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import DriveResource  # pyright: ignore[reportMissingModuleSource]


def build_google_drive_provider(
    *,
    get_service: Callable[[list[str], str | None], DriveResource],
) -> DriveProvider:
    """Build a Google Drive provider with an injected service factory."""
    return GoogleDriveProvider(get_service=get_service)


@cache
def get_drive_provider() -> DriveProvider:
    """Return the singleton Drive provider: Google Drive, the only implementation."""
    return build_google_drive_provider(get_service=get_drive_service)
