"""Access Sync adapter registry.

Holds the mapping from platform key (e.g. 'aws') to its AccessSyncAdapter
implementation.  Adapters are registered at startup from runtime config.
"""

from typing import Dict, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from packages.access_sync.adapters import AccessSyncAdapter


class AccessSyncRegistry:
    """Registry for platform sync adapters.

    Adapters are injected at construction time; use register_adapter to add
    entries dynamically (e.g. from a hookimpl).
    """

    def __init__(self, adapters: "Mapping[str, AccessSyncAdapter]") -> None:
        self._adapters: "Dict[str, AccessSyncAdapter]" = dict(adapters)

    def register_adapter(self, platform: str, adapter: "AccessSyncAdapter") -> None:
        """Register or replace the adapter for *platform*."""
        self._adapters[platform] = adapter

    def get_adapter(self, platform: str) -> "AccessSyncAdapter":
        """Return the adapter for *platform*.

        Raises:
            KeyError: If no adapter is registered for the given platform.
        """
        if platform not in self._adapters:
            raise KeyError(f"adapter_not_registered: {platform}")
        return self._adapters[platform]

    def registered_platforms(self) -> list:
        """Return a sorted list of registered platform keys."""
        return sorted(self._adapters.keys())
