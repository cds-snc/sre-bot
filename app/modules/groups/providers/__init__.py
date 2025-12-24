"""Provider registry and helpers for group providers.

ROLE-SEPARATED REGISTRY MODEL (Feature-Level):
1. Two separate registries: _primary_registry, _secondary_registry
2. register_primary_provider() and register_secondary_provider() decorators
3. activate_providers() with role-specific validation
4. Public API functions work with appropriate registry

This provides:
- Clear semantic separation between primary (canonical) and secondary (replica) providers
- Simplified validation logic (primary only, secondaries independently)
- Better observability (metrics naturally separate primary vs secondary)
- Reduced complexity in orchestration (direct secondary access)

Note: This is a FEATURE-LEVEL pattern specific to groups module.
"""

import importlib
import pkgutil
from typing import Dict, Optional, Type

import structlog
from modules.groups.providers.base import GroupProvider, PrimaryGroupProvider
from modules.groups.providers import registry_utils

logger = structlog.get_logger()

# Separate registries for different provider roles
_primary_discovered: Dict[str, Type[PrimaryGroupProvider]] = {}
_primary_active: Optional[PrimaryGroupProvider] = None

_secondary_discovered: Dict[str, Type[GroupProvider]] = {}
_secondary_active: Dict[str, GroupProvider] = {}

# Primary provider name (set once during activate_providers())
_PRIMARY_PROVIDER_NAME: Optional[str] = None


def register_primary_provider(name: str):
    """Register a primary (canonical) provider.

    Primary providers:
    - Provide role information (e.g., member vs manager)
    - Serve as the canonical source of truth
    - Used for authorization and group creation
    - Exactly one must be active at any time

    Args:
        name: Unique identifier for this provider

    Returns:
        Decorator function

    Example:
        @register_primary_provider("google")
        class GoogleWorkspaceProvider(PrimaryGroupProvider):
            ...
    """

    def decorator(obj):
        if not isinstance(obj, type):
            raise TypeError(
                "register_primary_provider decorator must be applied to a class"
            )

        if not issubclass(obj, PrimaryGroupProvider):
            raise TypeError(
                f"Primary provider must subclass PrimaryGroupProvider: {name}, got {obj}"
            )

        if name in _primary_discovered:
            raise RuntimeError(f"Primary provider already discovered with name: {name}")

        _primary_discovered[name] = obj
        logger.debug(
            "primary_provider_discovered", provider=name, class_name=obj.__name__
        )
        return obj

    return decorator


def register_secondary_provider(name: str):
    """Register a secondary (replica or adapter) provider.

    Secondary providers:
    - Replicate group memberships from primary
    - Used for cross-directory synchronization
    - Zero or more can be active
    - Don't provide role information

    Args:
        name: Unique identifier for this provider

    Returns:
        Decorator function

    Example:
        @register_secondary_provider("aws")
        class AwsIdentityCenterProvider(GroupProvider):
            ...
    """

    def decorator(obj):
        if not isinstance(obj, type):
            raise TypeError(
                "register_secondary_provider decorator must be applied to a class"
            )

        if not issubclass(obj, GroupProvider):
            raise TypeError(
                f"Secondary provider must subclass GroupProvider: {name}, got {obj}"
            )

        if name in _secondary_discovered:
            raise RuntimeError(
                f"Secondary provider already discovered with name: {name}"
            )

        _secondary_discovered[name] = obj
        logger.debug(
            "secondary_provider_discovered", provider=name, class_name=obj.__name__
        )
        return obj

    return decorator


def register_provider(name: str):
    """Register a provider by auto-detecting its role from base class.

    Convenience decorator that automatically determines role based on
    which base class the provider inherits from:
    - Subclass of PrimaryGroupProvider -> registered as primary
    - Subclass of GroupProvider (not Primary) -> registered as secondary

    Prefer using register_primary_provider() or register_secondary_provider()
    explicitly for clarity. This decorator exists for convenience during migration.

    Args:
        name: Unique identifier for this provider

    Returns:
        Decorator function

    Raises:
        TypeError: If provider doesn't inherit from GroupProvider

    Example:
        @register_provider("google")
        class GoogleWorkspaceProvider(PrimaryGroupProvider):  # Auto-detected as primary
            ...

        @register_provider("aws")
        class AwsIdentityCenterProvider(GroupProvider):  # Auto-detected as secondary
            ...
    """

    def decorator(cls):
        if not isinstance(cls, type):
            raise TypeError("register_provider decorator must be applied to a class")

        if issubclass(cls, PrimaryGroupProvider):
            return register_primary_provider(name)(cls)
        elif issubclass(cls, GroupProvider):
            return register_secondary_provider(name)(cls)
        else:
            raise TypeError(
                f"Provider must inherit from GroupProvider or PrimaryGroupProvider: "
                f"{name}, got {cls.__name__}"
            )

    return decorator


def activate_providers() -> str:
    """Activate primary and secondary providers with role separation.

    Two-stage activation:
    1. Registry activation: Filter disabled, instantiate, apply config
    2. Validation: Verify primary provider capabilities, validate prefix uniqueness

    Returns:
        Name of the activated primary provider

    Raises:
        RuntimeError: If activation fails (no primary, validation errors)
        ValueError: If configuration is invalid
    """
    # pylint: disable=import-outside-toplevel
    from infrastructure.configuration import settings

    try:
        provider_configs = settings.groups.providers or {}
    except AttributeError as e:
        raise ValueError(
            "Groups configuration not found in settings. "
            "Ensure core.config has groups configured."
        ) from e

    # Separate primary from secondaries based on type
    primary_config = {}
    secondary_config = {}

    for pname, cfg in provider_configs.items():
        if not isinstance(cfg, dict):
            continue
        # Check if this is a discovered primary provider
        if pname in _primary_discovered:
            primary_config[pname] = cfg
        # Check if this is a discovered secondary provider
        elif pname in _secondary_discovered:
            secondary_config[pname] = cfg
        else:
            # Unknown provider in config, skip with warning
            logger.warning("provider_not_discovered", provider=pname)

    # Activate primary provider
    primary_name = _activate_primary(primary_config)

    # Activate secondary providers
    _activate_secondaries(secondary_config)

    logger.info(
        "providers_activated",
        primary=primary_name,
        secondaries=list(_secondary_active.keys()),
        total=len(_secondary_active) + 1,
    )

    return primary_name


def _activate_primary(primary_config: Dict[str, dict]) -> str:
    """Activate the primary provider.

    Args:
        primary_config: Config dict mapping provider names to config dicts

    Returns:
        Name of the activated primary provider

    Raises:
        RuntimeError: If no primary or multiple primaries enabled
    """
    # pylint: disable=global-statement
    global _primary_active, _PRIMARY_PROVIDER_NAME

    # Filter to enabled primary providers
    enabled = {
        name: cfg
        for name, cfg in primary_config.items()
        if cfg.get("enabled", True) and name in _primary_discovered
    }

    if len(enabled) != 1:
        raise RuntimeError(
            f"Expected exactly 1 enabled primary provider, "
            f"got {len(enabled)}: {list(enabled.keys())}"
        )

    primary_name = next(iter(enabled.keys()))
    primary_class = _primary_discovered[primary_name]
    provider_cfg = enabled[primary_name]

    try:
        # Single-stage activation: pass config to __init__
        instance = registry_utils.instantiate_provider(
            primary_class, primary_name, config=provider_cfg
        )

        if not isinstance(instance, PrimaryGroupProvider):
            raise TypeError(
                f"Primary provider must be PrimaryGroupProvider: {primary_name}"
            )

        # Attach registration name
        setattr(instance, "name", primary_name)

        # Resolve and set prefix
        prefix = registry_utils.resolve_prefix(instance, provider_cfg, primary_name)
        setattr(instance, "_prefix", prefix)

        # Apply capability overrides (if not already handled in __init__)
        registry_utils.apply_capability_overrides(instance, provider_cfg)

        # Validate primary capabilities
        if not instance.get_capabilities().provides_role_info:
            raise RuntimeError(
                f"Primary provider '{primary_name}' must provide role info "
                f"(provides_role_info=True)"
            )

        _primary_active = instance
        _PRIMARY_PROVIDER_NAME = primary_name

        logger.info(
            "primary_provider_activated",
            provider=primary_name,
            type=type(instance).__name__,
            prefix=prefix,
        )

        return primary_name

    except Exception as e:
        logger.error(
            "primary_provider_activation_failed", provider=primary_name, error=str(e)
        )
        raise


def _activate_secondaries(secondary_config: Dict[str, dict]) -> None:
    """Activate secondary providers.

    Args:
        secondary_config: Config dict mapping provider names to config dicts
    """
    # pylint: disable=global-statement
    global _secondary_active

    # Filter to enabled secondary providers
    enabled = {
        name: cfg
        for name, cfg in secondary_config.items()
        if cfg.get("enabled", True) and name in _secondary_discovered
    }

    new_active: Dict[str, GroupProvider] = {}

    for name, provider_cfg in enabled.items():
        provider_class = _secondary_discovered[name]

        try:
            # Single-stage activation: pass config to __init__
            instance = registry_utils.instantiate_provider(
                provider_class, name, config=provider_cfg
            )

            if not isinstance(instance, GroupProvider):
                raise TypeError(f"Secondary provider must be GroupProvider: {name}")

            # Attach registration name
            setattr(instance, "name", name)

            # Resolve and set prefix
            prefix = registry_utils.resolve_prefix(instance, provider_cfg, name)
            setattr(instance, "_prefix", prefix)

            # Apply capability overrides (if not already handled in __init__)
            registry_utils.apply_capability_overrides(instance, provider_cfg)

            new_active[name] = instance

            logger.info(
                "secondary_provider_activated",
                provider=name,
                type=type(instance).__name__,
                prefix=prefix,
            )

        except Exception as e:
            logger.error(
                "secondary_provider_activation_failed", provider=name, error=str(e)
            )
            raise

    # Validate prefix uniqueness across secondaries
    prefix_map = registry_utils.collect_prefixes(new_active)
    registry_utils.validate_prefix_uniqueness(prefix_map)

    _secondary_active = new_active

    logger.info(
        "secondary_providers_activated",
        count=len(new_active),
        providers=list(new_active.keys()),
    )


def reset_registry() -> None:
    """Reset provider registries and primary name. Used for testing."""
    # pylint: disable=global-statement
    global _primary_active, _secondary_active, _PRIMARY_PROVIDER_NAME
    _primary_active = None
    _secondary_active = {}
    _PRIMARY_PROVIDER_NAME = None
    logger.debug("provider_registries_reset")


def get_primary_provider() -> PrimaryGroupProvider:
    """Return the primary provider instance.

    Raises ValueError if no primary provider is active.
    """
    if _primary_active is None:
        raise ValueError("No primary provider set. Call activate_providers() first.")

    return _primary_active


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
    # Check primary
    if provider_name == _PRIMARY_PROVIDER_NAME:
        if _primary_active is None:
            raise ValueError(f"Unknown provider: {provider_name}")
        return _primary_active

    # Check secondaries
    if provider_name not in _secondary_active:
        raise ValueError(f"Unknown provider: {provider_name}")

    return _secondary_active[provider_name]


def get_active_providers(
    provider_filter: Optional[str] = None,
) -> Dict[str, GroupProvider]:
    """Get active providers, optionally filtered by name."""
    # Build combined registry
    combined: Dict[str, GroupProvider] = {}
    if _primary_active is not None and _PRIMARY_PROVIDER_NAME is not None:
        combined[_PRIMARY_PROVIDER_NAME] = _primary_active
    combined.update(_secondary_active)

    if provider_filter:
        return {provider_filter: get_provider(provider_filter)}

    return combined


def get_secondary_providers() -> Dict[str, GroupProvider]:
    """Get all active secondary providers.

    Returns:
        Dict mapping provider name to instance
    """
    return _secondary_active.copy()


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

    if _primary_active is None:
        raise RuntimeError(f"Primary provider '{primary_name}' not activated.")

    caps = _primary_active.get_capabilities()

    if not getattr(caps, "provides_role_info", False):
        raise RuntimeError(
            f"Primary provider '{primary_name}' does not advertise provides_role_info=True."
        )

    total_active = len(_secondary_active) + (1 if _primary_active else 0)
    logger.info(
        "provider_startup_validated",
        primary=primary_name,
        secondaries=list(_secondary_active.keys()),
        total_active=total_active,
    )
