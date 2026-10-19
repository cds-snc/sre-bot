"""The configured-systems read: which workplace systems this instance works with.

A tenant entry in a vendor's settings slice is what configures a system
(``decisions/workplace-systems.md`` rule 3). Features learn the configured
systems and their tenant ids through this read, never by importing a vendor
slice.
"""

from collections.abc import Mapping
from typing import Protocol

from contracts.workplace.systems import WorkplaceSystem


class ConfiguredSystems(Protocol):
    """Read-only view of the configured workplace systems, built once at startup."""

    def tenants(self) -> Mapping[WorkplaceSystem, str]:
        """Return the tenant id of each configured system; a system not configured is absent."""
        ...
