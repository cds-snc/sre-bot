"""Translation resource spec and the registrar Protocol feature packages register it through."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class I18nResourceSpec:
    """Specification for a translation resource location.

    Attributes:
        owner: Feature package or module owning the resource (e.g., "packages.geolocate").
        path: Filesystem path to translation files (can be relative or absolute).
        required: Whether startup should fail if this resource path is missing.
        format: Translation file format (e.g., "yaml", "json").
        domain: Logical translation domain for grouping (e.g., "geolocate", "core").
    """

    owner: str
    path: str
    required: bool = True
    format: str = "yaml"
    domain: str = "default"

    def __post_init__(self) -> None:
        """Validate resource spec on creation."""
        if not self.owner:
            raise ValueError("owner must not be empty")
        if not self.path:
            raise ValueError("path must not be empty")
        if self.format not in ("yaml", "json"):
            raise ValueError(f"format must be 'yaml' or 'json', got {self.format}")


class I18nResourceRegistrar(Protocol):
    """Registration boundary for feature translation resources.

    This protocol defines the exact contract feature packages must interact with.
    """

    def register(self, spec: I18nResourceSpec) -> None:
        """Register a translation resource location."""
        ...
