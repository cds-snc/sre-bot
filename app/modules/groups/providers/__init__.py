"""Provider registry and helpers for group providers.

This module maintains the provider registry and exposes decorators and
helpers for registering and accessing provider implementations.

All provider contracts, capabilities, and abstract base classes are defined
in `modules.groups.providers.base`.
"""

from typing import Dict, Optional
from core.config import settings
from core.logging import get_module_logger
from modules.groups.providers.base import GroupProvider

logger = get_module_logger()

PROVIDER_REGISTRY: Dict[str, GroupProvider] = {}


def register_provider(name: str):
    """Decorator to register a provider class or instance.

    Usage:
        @register_provider("google")
        class GoogleWorkspaceProvider(GroupProvider):
            ...
    """

    def decorator(obj):
        instance = obj() if isinstance(obj, type) else obj

        if not isinstance(instance, GroupProvider):
            raise TypeError(
                f"Registered provider must implement GroupProvider: {name}, got {type(instance)}"
            )

        if name in PROVIDER_REGISTRY:
            raise RuntimeError(f"Provider already registered with name: {name}")

        # Check config for enabled/disabled
        provider_cfg = {}
        if getattr(settings, "groups", None) and isinstance(
            settings.groups.providers, dict
        ):
            provider_cfg = settings.groups.providers.get(name, {}) or {}
        enabled = provider_cfg.get("enabled", True)
        if not enabled:
            logger.info("provider_disabled_by_config", provider=name)
            return obj

        PROVIDER_REGISTRY[name] = instance
        logger.info("provider_registered", provider=name, type=type(instance).__name__)
        return obj

    return decorator


def get_primary_provider_name() -> str:
    """Return the configured primary provider name."""
    provs = getattr(settings, "groups", None) and getattr(
        settings.groups, "providers", {}
    )
    if not provs or not isinstance(provs, dict):
        raise ValueError("GROUP_PROVIDERS is not configured")
    for name, cfg in provs.items():
        if isinstance(cfg, dict) and cfg.get("primary"):
            return name
    raise ValueError("No primary provider configured in GROUP_PROVIDERS")


def get_primary_provider() -> GroupProvider:
    """Return the registered primary provider instance."""
    name = get_primary_provider_name()
    return get_provider(name)


def get_provider(provider_name: str) -> GroupProvider:
    """Get provider instance by name (raises ValueError if unknown)."""
    if provider_name not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider_name}")
    return PROVIDER_REGISTRY[provider_name]


def get_active_providers(
    provider_filter: Optional[str] = None,
) -> Dict[str, GroupProvider]:
    """Get all active providers or filtered by name."""
    if provider_filter:
        return {provider_filter: get_provider(provider_filter)}
    return PROVIDER_REGISTRY


def _validate_startup_configuration() -> None:
    """Validate provider configuration at startup."""
    provs = getattr(settings, "groups", None) and getattr(
        settings.groups, "providers", {}
    )
    if not provs:
        logger.info(
            "provider_startup_validation_skipped", reason="no providers configured"
        )
        return

    try:
        primary_name = get_primary_provider_name()
    except Exception as e:
        raise RuntimeError(f"Provider configuration error: {e}") from e

    if primary_name not in PROVIDER_REGISTRY:
        raise RuntimeError(
            f"Primary provider '{primary_name}' is configured but not registered. "
            "Ensure the provider module is imported and register_provider() is applied."
        )

    primary = PROVIDER_REGISTRY[primary_name]
    caps = getattr(primary, "capabilities", None)
    if not caps or not getattr(caps, "provides_role_info", False):
        raise RuntimeError(
            f"Primary provider '{primary_name}' does not advertise provides_role_info=True. "
            "Primary provider must expose role information for permission checks."
        )


# NOTE: Do not validate startup configuration at package import time.
# Validation is performed after explicit provider discovery via `load_providers()`
# to avoid import-order issues where callers import the package before
# provider submodules are imported/registered.


def load_providers() -> None:
    """Discover and import provider modules under this package.

    This will import every top-level module in the `modules.groups.providers`
    package (skipping private modules). Import errors are logged and do not
    halt startup so a single faulty provider doesn't block all providers.
    """
    import importlib
    import pkgutil

    for finder, modname, ispkg in pkgutil.iter_modules(__path__):
        # skip private modules
        if modname.startswith("_"):
            continue
        full_name = f"{__name__}.{modname}"
        try:
            importlib.import_module(full_name)
        except Exception as e:
            logger.warning("provider_import_failed", module=full_name, error=str(e))

    # After attempting to import provider modules, validate the startup
    # configuration so we fail fast if the configured primary provider was
    # not registered or does not advertise required capabilities.
    try:
        _validate_startup_configuration()
    except Exception as exc:
        logger.error(
            "provider_startup_validation_failed",
            component="providers",
            module_path=__name__,
            error=str(exc),
        )
        raise
