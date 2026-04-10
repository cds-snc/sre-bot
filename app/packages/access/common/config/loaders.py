"""Shared loader protocol for access runtime configuration."""

from typing import Protocol

from infrastructure.operations import OperationResult
from packages.access.common.config.settings import AccessRuntimeConfig


class AccessConfigLoader(Protocol):
    """Protocol for loading access runtime configuration."""

    def load(self, ref: str) -> OperationResult[AccessRuntimeConfig]:
        """Load access runtime configuration by source-specific reference."""
        ...
