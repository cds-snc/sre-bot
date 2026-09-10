"""Shared Drive infrastructure capability."""

from infrastructure.drive.factory import get_drive_provider
from infrastructure.drive.google import DRIVE_SCOPES
from infrastructure.drive.models import DriveFile
from infrastructure.drive.provider import DriveProvider
from infrastructure.drive.settings import DriveSettings, get_drive_settings

__all__ = [
    "DRIVE_SCOPES",
    "DriveFile",
    "DriveProvider",
    "DriveSettings",
    "get_drive_provider",
    "get_drive_settings",
]
