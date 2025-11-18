"""Provider registry and helpers for group providers.

SIMPLE ACTIVATION MODEL:
1. @register_provider decorator → DISCOVERED_PROVIDER_CLASSES (class registration)
2. activate_providers() → reads config ONCE, instantiates, populates PROVIDER_REGISTRY
3. Helper functions → only query PROVIDER_REGISTRY, no config re-parsing

Config overrides applied ONLY during activate_providers(), then discarded.
"""

import importlib
import pkgutil
from typing import Dict, Optional, Type

from core.logging import get_module_logger
from modules.groups.providers.base import GroupProvider, PrimaryGroupProvider
from modules.groups.providers import registry_utils

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


def activate_providers() -> str:
    """Instantiate discovered providers with activation-time defaults and optional
    config overrides.

    Behavior:
    - Read config once from settings.groups.providers.
    - Filter out providers with enabled=False in config.
    - Instantiate remaining discovered provider classes.
    - Apply provider-provided defaults and config overrides.
    - Populate PROVIDER_REGISTRY and validate uniqueness of activated prefixes.
    - Determine and return the primary provider name.

    Raises:
        RuntimeError: on duplicate prefix collisions, disabled primary provider,
            or when provider instantiation/validation fails.
    """
    # pylint: disable=import-outside-toplevel
    from core.config import settings  # Import at function level to avoid circular deps

    try:
        provider_configs = settings.groups.providers or {}
    except AttributeError as e:
        raise ValueError(
            "Groups configuration not found in settings. "
            "Ensure core.config has groups configured."
        ) from e

    # Filter discovered providers based on config
    enabled_providers = registry_utils.filter_disabled_providers(
        DISCOVERED_PROVIDER_CLASSES, provider_configs
    )

    # Instantiate and configure each provider
    new_registry: Dict[str, GroupProvider] = {}
    for name, provider_cls in enabled_providers.items():
        try:
            # Instantiate provider with fallback strategies
            instance = registry_utils.instantiate_provider(provider_cls, name)

            if not isinstance(instance, GroupProvider):
                raise TypeError(f"Provider must be a GroupProvider instance: {name}")

            # Attach registration name to instance
            setattr(instance, "name", name)

            # Apply domain configuration if available
            provider_cfg = provider_configs.get(name, {})
            registry_utils.apply_domain_config(instance, provider_cfg)

            # Resolve and set prefix
            prefix = registry_utils.resolve_prefix(instance, provider_cfg, name)
            setattr(instance, "_prefix", prefix)

            # Apply capability overrides
            registry_utils.apply_capability_overrides(instance, provider_cfg)

            new_registry[name] = instance
            logger.info(
                "provider_activated",
                provider=name,
                type=type(instance).__name__,
                prefix=prefix,
            )

        except Exception as e:  # noqa: B902 - log and re-raise activation errors
            logger.error("provider_activation_failed", provider=name, error=str(e))
            raise

    # Validate uniqueness of non-empty prefixes
    prefix_map = registry_utils.collect_prefixes(new_registry)
    registry_utils.validate_prefix_uniqueness(prefix_map)

    # Determine primary provider and atomically swap registry
    provider_name = _determine_primary(registry=new_registry)

    PROVIDER_REGISTRY.clear()
    PROVIDER_REGISTRY.update(new_registry)
    global _PRIMARY_PROVIDER_NAME
    _PRIMARY_PROVIDER_NAME = provider_name

    logger.info("primary_provider_set", provider=provider_name)
    return provider_name


def _determine_primary(registry: Optional[Dict[str, GroupProvider]] = None) -> str:
    """Determine the primary provider from the freshly-built registry.

    Simplified priority:
    1. Exactly one provider in registry with `capabilities.is_primary == True`
    2. If registry contains exactly one provider, choose it
    3. Otherwise raise ValueError

    Note: This function only considers ACTIVE providers (those in the registry).
    Disabled providers are filtered out during activate_providers().
    """
    from core.config import settings

    reg = registry if registry is not None else PROVIDER_REGISTRY
    provider_configs = settings.groups.providers or {}

    if not reg:
        # If nothing instantiated but exactly one discovered provider, use it
        if len(DISCOVERED_PROVIDER_CLASSES) == 1:
            single_name = next(iter(DISCOVERED_PROVIDER_CLASSES.keys()))
            # Check if that single provider is disabled
            if not provider_configs.get(single_name, {}).get("enabled", True):
                raise ValueError(
                    f"Cannot determine primary provider: sole provider '{single_name}' is disabled in config."
                )
            return single_name
        raise ValueError(
            "Cannot determine primary provider: no active providers found."
        )

    primaries = [
        n for n, p in reg.items() if getattr(p.get_capabilities(), "is_primary", False)
    ]
    if len(primaries) == 1:
        return primaries[0]
    if len(primaries) > 1:
        raise RuntimeError(f"Multiple providers claim is_primary=True: {primaries}")

    if len(reg) == 1:
        return next(iter(reg.keys()))

    raise ValueError(
        "Cannot determine primary provider. Multiple providers active and "
        "none declare `is_primary=True`. Mark one provider's capabilities "
        "with is_primary=True or reduce to a single provider."
    )


def reset_registry() -> None:
    """Reset provider registry and primary name. Used for testing."""
    global _PRIMARY_PROVIDER_NAME
    PROVIDER_REGISTRY.clear()
    _PRIMARY_PROVIDER_NAME = None
    logger.debug("provider_registry_reset")


def get_primary_provider() -> PrimaryGroupProvider:
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


def load_providers() -> str:
    """Discover and import provider modules, then activate.

    - Imports all top-level modules (skips private)
    - Calls activate_providers() to instantiate and set primary
    - Validates startup config
    """

    for module_info in pkgutil.iter_modules(__path__):
        modname = module_info.name
        if modname.startswith("_"):
            continue
        full_name = f"{__name__}.{modname}"
        try:
            importlib.import_module(full_name)
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning("provider_import_failed", module=full_name, error=str(e))
    # Activate providers and get primary provider name
    primary_name = activate_providers()

    # Validate startup state using the returned primary name
    _validate_startup(primary_name)

    return primary_name


def _validate_startup(primary_name: str) -> None:
    """Validate that primary provider meets requirements.

    Accepts the primary provider name to avoid reading a module global.
    """
    if not primary_name:
        raise RuntimeError("No primary provider configured.")

    if primary_name not in PROVIDER_REGISTRY:
        raise RuntimeError(f"Primary provider '{primary_name}' not in registry.")

    primary = PROVIDER_REGISTRY[primary_name]
    caps = getattr(primary, "capabilities", None)

    if not caps or not getattr(caps, "provides_role_info", False):
        raise RuntimeError(
            f"Primary provider '{primary_name}' does not advertise provides_role_info=True."
        )

    logger.info(
        "provider_startup_validated",
        primary=primary_name,
        total_active=len(PROVIDER_REGISTRY),
    )
