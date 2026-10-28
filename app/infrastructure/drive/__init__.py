"""Shared Drive infrastructure capability."""

from infrastructure.drive.factory import get_drive_provider
from infrastructure.drive.google import DRIVE_SCOPES
from infrastructure.drive.models import DriveFile
from infrastructure.drive.provider import DriveProvider

__all__ = [
    "DRIVE_SCOPES",
    "DriveFile",
    "DriveProvider",
    "get_drive_provider",
]
