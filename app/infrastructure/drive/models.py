"""Canonical typed models for Drive provider results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DriveFile:
    """A file or folder returned by a Drive provider."""

    id: str
    name: str | None
    mime_type: str | None = None
    parents: tuple[str, ...] = ()
    provider: str | None = None
