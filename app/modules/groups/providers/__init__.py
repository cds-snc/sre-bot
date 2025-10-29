"""Provider registry and helpers for group providers.

SIMPLE ACTIVATION MODEL:
1. @register_provider decorator → DISCOVERED_PROVIDER_CLASSES (class registration)
2. activate_providers() → reads config ONCE, instantiates, populates PROVIDER_REGISTRY
3. Helper functions → only query PROVIDER_REGISTRY, no config re-parsing

Config overrides applied ONLY during activate_providers(), then discarded.
"""

from typing import Dict, Optional, Type

from core.config import settings
from core.logging import get_module_logger
from modules.groups.providers.base import GroupProvider

logger = get_module_logger()

# Registry of instantiated providers (populated at activation time)
PROVIDER_REGISTRY: Dict[str, GroupProvider] = {}

# Discovery registry: decorator records provider classes here during import
DISCOVERED_PROVIDER_CLASSES: Dict[str, Type[GroupProvider]] = {}

# Primary provider name (set once during activate_providers())
_PRIMARY_PROVIDER_NAME: Optional[str] = None


def register_provider(name: str):
    """Decorator to register a provider class.

    Records the class in DISCOVERED_PROVIDER_CLASSES.
    Instantiation happens later during activate_providers().
    """

    def decorator(obj):
        if not isinstance(obj, type):
            raise TypeError("register_provider decorator must be applied to a class")

        if not issubclass(obj, GroupProvider):
            raise TypeError(
                f"Registered provider must subclass GroupProvider: {name}, got {obj}"
            )

        if name in DISCOVERED_PROVIDER_CLASSES:
            raise RuntimeError(f"Provider already discovered with name: {name}")

        DISCOVERED_PROVIDER_CLASSES[name] = obj
        logger.debug("provider_discovered", provider=name, class_name=obj.__name__)
        return obj

    return decorator


def activate_providers() -> None:
    """Instantiate discovered providers with config overrides.

    - Reads config ONCE from settings
    - Instantiates each discovered provider
    - Determines and caches primary provider
    - No lazy activation; all done at startup
    """
    global _PRIMARY_PROVIDER_NAME

    # Read config once
    provs_cfg = getattr(settings, "groups", None) and getattr(
        settings.groups, "providers", {}
    )
    provs_cfg = provs_cfg if isinstance(provs_cfg, dict) else {}

    # Instantiate all discovered providers
    for name, provider_cls in DISCOVERED_PROVIDER_CLASSES.items():
        cfg = provs_cfg.get(name, {})
        enabled = cfg.get("enabled", True)

        if not enabled:
            logger.info("provider_disabled_by_config", provider=name)
            continue

        try:
            # Use from_config if available, else default instantiation
            if hasattr(provider_cls, "from_config") and callable(
                getattr(provider_cls, "from_config")
            ):
                instance = provider_cls.from_config(cfg)
            else:
                init_kwargs = (
                    cfg.get("init_kwargs", {}) if isinstance(cfg, dict) else {}
                )
                try:
                    instance = provider_cls(**init_kwargs)
                except TypeError:
                    instance = provider_cls()

            if not isinstance(instance, GroupProvider):
                raise TypeError(f"Provider must be a GroupProvider instance: {name}")

            PROVIDER_REGISTRY[name] = instance
            logger.info(
                "provider_activated", provider=name, type=type(instance).__name__
            )
        except Exception as e:
            logger.error("provider_activation_failed", provider=name, error=str(e))
            raise

    # Determine primary provider
    _PRIMARY_PROVIDER_NAME = _determine_primary(provs_cfg)
    logger.info("primary_provider_set", provider=_PRIMARY_PROVIDER_NAME)


def _determine_primary(provs_cfg: Dict) -> str:
    """Determine the primary provider from registry or config.

    Priority:
    1. Provider marked primary=True in config
    2. Single provider with is_primary=True capability
    3. Only provider in registry
    4. Single discovered provider (if registry empty)
    """
    # Check config for explicit primary
    for name, cfg in provs_cfg.items():
        if isinstance(cfg, dict) and cfg.get("primary"):
            if name not in PROVIDER_REGISTRY:
                raise ValueError(
                    f"Primary provider '{name}' not in registry. "
                    "Ensure it's discovered and enabled."
                )
            return name

    # Check capabilities in registry
    if PROVIDER_REGISTRY:
        primaries = [
            n
            for n, p in PROVIDER_REGISTRY.items()
            if getattr(p.capabilities, "is_primary", False)
        ]
        if len(primaries) == 1:
            return primaries[0]
        if len(primaries) > 1:
            raise RuntimeError(f"Multiple providers claim is_primary=True: {primaries}")
        # Single provider in registry
        if len(PROVIDER_REGISTRY) == 1:
            return next(iter(PROVIDER_REGISTRY.keys()))

    # Fallback: single discovered (not yet instantiated)
    if len(DISCOVERED_PROVIDER_CLASSES) == 1:
        return next(iter(DISCOVERED_PROVIDER_CLASSES.keys()))

    raise ValueError(
        "Cannot determine primary provider. "
        "Ensure at least one provider is configured/discovered."
    )


def get_primary_provider() -> GroupProvider:
    """Return the primary provider instance.

    Raises ValueError if no primary provider is active.
    """
    if _PRIMARY_PROVIDER_NAME is None:
        raise ValueError("No primary provider set. Call activate_providers() first.")

    if _PRIMARY_PROVIDER_NAME not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Primary provider '{_PRIMARY_PROVIDER_NAME}' not in registry."
        )

    return PROVIDER_REGISTRY[_PRIMARY_PROVIDER_NAME]


def get_primary_provider_name() -> str:
    """Return the name of the primary provider.

    Raises ValueError if no primary provider is active.
    """
    if _PRIMARY_PROVIDER_NAME is None:
        raise ValueError("No primary provider set. Call activate_providers() first.")

    return _PRIMARY_PROVIDER_NAME


def get_provider(provider_name: str) -> GroupProvider:
    """Get provider instance by name.

    Raises ValueError if provider not in registry.
    """
    if provider_name not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider_name}")

    return PROVIDER_REGISTRY[provider_name]


def get_active_providers(
    provider_filter: Optional[str] = None,
) -> Dict[str, GroupProvider]:
    """Get active providers, optionally filtered by name."""
    if provider_filter:
        return {provider_filter: get_provider(provider_filter)}

    return PROVIDER_REGISTRY.copy()


def load_providers() -> None:
    """Discover and import provider modules, then activate.

    - Imports all top-level modules (skips private)
    - Calls activate_providers() to instantiate and set primary
    - Validates startup config
    """
    import importlib
    import pkgutil

    for finder, modname, ispkg in pkgutil.iter_modules(__path__):
        if modname.startswith("_"):
            continue
        full_name = f"{__name__}.{modname}"
        try:
            importlib.import_module(full_name)
        except Exception as e:
            logger.warning("provider_import_failed", module=full_name, error=str(e))

    # Activate providers and set primary
    activate_providers()

    # Validate startup state
    _validate_startup()


def _validate_startup() -> None:
    """Validate that primary provider meets requirements."""
    if _PRIMARY_PROVIDER_NAME is None:
        raise RuntimeError("No primary provider configured.")

    primary = get_primary_provider()
    caps = getattr(primary, "capabilities", None)

    if not caps or not getattr(caps, "provides_role_info", False):
        raise RuntimeError(
            f"Primary provider '{_PRIMARY_PROVIDER_NAME}' "
            "does not advertise provides_role_info=True."
        )

    logger.info(
        "provider_startup_validated",
        primary=_PRIMARY_PROVIDER_NAME,
        total_active=len(PROVIDER_REGISTRY),
    )
