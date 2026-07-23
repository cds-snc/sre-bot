"""i18n resource registry for managing translation file locations.

Allows feature packages to co-locate translation YAML files with their code
and register them through the feature plugin lifecycle.
"""

from dataclasses import dataclass, field
from pathlib import Path

import structlog

from infrastructure.operations import OperationResult, OperationStatus


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


@dataclass
class I18nResourceRegistry:
    """Registry for collecting i18n resource specifications from features.

    Manages resource collection, validation, and deduplication across all
    discovered feature packages during startup.
    """

    _specs: list[I18nResourceSpec] = field(default_factory=list)
    _paths_seen: set[str] = field(default_factory=set)

    def register(self, spec: I18nResourceSpec) -> None:
        """Register a translation resource location.

        Args:
            spec: I18nResourceSpec describing the resource location.

        Raises:
            ValueError: If resource specification is invalid or duplicate.
        """
        logger = structlog.get_logger()
        log = logger.bind(owner=spec.owner, path=spec.path, domain=spec.domain)

        # Deduplicate on path alone — same path registered by different owners should merge once
        path_key = spec.path
        if path_key in self._paths_seen:
            log.warning("i18n_resource_duplicate_skipped")
            return

        self._paths_seen.add(path_key)
        self._specs.append(spec)
        log.info("i18n_resource_registered", required=spec.required)

    def list_specs(self) -> list[I18nResourceSpec]:
        """Get all registered resource specifications.

        Returns:
            List of I18nResourceSpec in registration order.
        """
        return list(self._specs)

    def list_paths(self) -> list[str]:
        """Get all registered resource paths in order.

        Returns:
            List of filesystem paths extracted from specs.
        """
        return [spec.path for spec in self._specs]

    def validate_paths(self) -> OperationResult[None]:
        """Validate that all required resource paths exist on filesystem.

        Returns:
            OperationResult.success() if all required paths exist.
            OperationResult.error() if any required path is missing.
        """
        logger = structlog.get_logger()
        missing_required: list[str] = []
        missing_optional: list[str] = []

        for spec in self._specs:
            path = Path(spec.path)
            if not path.exists():
                if spec.required:
                    missing_required.append(spec.path)
                else:
                    missing_optional.append(spec.path)

        # Log warnings for missing optional paths
        if missing_optional:
            log = logger.bind(paths=missing_optional)
            log.warning("i18n_optional_resources_missing")

        # Return failure if any required paths are missing
        if missing_required:
            log = logger.bind(paths=missing_required, count=len(missing_required))
            log.error("i18n_required_resources_missing")
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message=f"Required i18n resources missing: {missing_required}",
            )

        log = logger.bind(registered_count=len(self._specs))
        log.info("i18n_resource_validation_passed")
        return OperationResult.success()

    def get_resource_count(self) -> int:
        """Get count of registered resources.

        Returns:
            Number of registered resource specifications.
        """
        return len(self._specs)
