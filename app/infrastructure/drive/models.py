"""Canonical typed models for Drive provider results."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DriveFile:
    """A file or folder returned by a Drive provider."""

    id: str
    name: str
    mime_type: str | None = None
    parents: tuple[str, ...] = ()
    app_properties: dict[str, str] = field(default_factory=dict)
    provider: str | None = None
