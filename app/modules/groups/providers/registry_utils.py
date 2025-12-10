"""Registry utilities: Pure helper functions for provider activation.

This module contains pure functions extracted from activate_providers()
for improved testability and readability. Functions in this module have
no side effects and return new data structures rather than mutating state.

Usage:
  These helpers are called from __init__.activate_providers() during
  the activation orchestration phase.
"""

from typing import Dict, Type, Any, Optional

from infrastructure.observability import get_module_logger

logger = get_module_logger()


def filter_disabled_providers(
    discovered: Dict[str, Type], config: Dict[str, Any]
) -> Dict[str, Type]:
    """Filter out providers explicitly disabled in config.

    Args:
        discovered: Dict of {provider_name: provider_class} from discovery
        config: Provider config dict from settings.groups.providers

    Returns:
        Filtered dict excluding disabled providers
    """
    enabled = {}
    for name, provider_cls in discovered.items():
        provider_cfg = config.get(name, {})
        if not provider_cfg.get("enabled", True):
            logger.info("provider_disabled_by_config", provider=name)
            continue
        enabled[name] = provider_cls
    return enabled


def instantiate_provider(
    provider_cls: Type, name: str, config: Optional[Dict[str, Any]] = None
) -> Any:
    """Instantiate a provider class with single-stage config passing.

    Priority:
    1. Try passing config dict to __init__
    2. Try parameterless __init__
    3. Try from_config() classmethod if available
    4. Explicit error if none work

    Args:
        provider_cls: The provider class to instantiate
        name: Provider name (for logging/errors)
        config: Provider config dict (from settings.groups.providers[name])

    Returns:
        Instantiated provider instance

    Raises:
        RuntimeError: If provider cannot be instantiated
    """
    if config is None:
        config = {}

    # Try with config dict first (single-stage activation)
    try:
        return provider_cls(config=config)
    except TypeError:
        pass

    # Try parameterless construction
    try:
        return provider_cls()
    except TypeError:
        pass

    # Try from_config() classmethod
    if hasattr(provider_cls, "from_config") and callable(
        getattr(provider_cls, "from_config")
    ):
        try:
            return provider_cls.from_config()
        except Exception as e:
            raise RuntimeError(f"Provider {name} from_config() failed: {str(e)}") from e

    # No construction strategy worked
    raise RuntimeError(
        f"Provider {name} cannot be instantiated: "
        "no __init__(config=...), parameterless __init__, or from_config() classmethod"
    )


def resolve_prefix(instance: Any, config: Dict[str, Any], provider_name: str) -> str:
    """Resolve a provider's prefix with config override support.

    Priority:
    1. explicit default_prefix attribute on instance
    2. instance.prefix property
    3. provider_name as fallback

    Then:
    - Apply config override if provided

    Args:
        instance: The provider instance
        config: Provider config dict
        provider_name: Name the provider was registered as

    Returns:
        The resolved prefix string

    Raises:
        ValueError: If resolution fails
    """
    # Step 1: Check for explicit default_prefix attribute
    default_prefix = getattr(instance, "default_prefix", None)

    # Step 2: Check for prefix property
    if default_prefix is None:
        try:
            default_prefix = instance.prefix
        except (AttributeError, NotImplementedError):
            default_prefix = None

    # Step 3: Use registration name as fallback
    if default_prefix is None:
        default_prefix = provider_name

    if not isinstance(default_prefix, str):
        raise ValueError(
            f"Prefix for {provider_name} must be string, got {type(default_prefix)}"
        )

    # Step 4: Apply config override if provided
    config_prefix = config.get("prefix")
    if config_prefix and isinstance(config_prefix, str):
        return config_prefix.strip()

    return default_prefix.strip()


def apply_capability_overrides(instance: Any, config: Dict[str, Any]) -> None:
    """Apply config-driven capability overrides to a provider instance.

    Imports from capabilities module to avoid circular dependency.

    Args:
        instance: The provider instance
        config: Provider config dict (from settings.groups.providers[name])
    """
    # Import here to avoid circular dependency
    from modules.groups.providers.capabilities import (
        apply_capability_overrides as apply_caps,
    )

    apply_caps(instance, config)


def apply_domain_config(instance: Any, config: Dict[str, Any]) -> None:
    """Call provider's _set_domain_from_config hook if available.

    Note: This is for backwards compatibility. With single-stage activation,
    providers should handle domain config in their __init__ method.

    Args:
        instance: The provider instance
        config: Provider config dict
    """
    if hasattr(instance, "_set_domain_from_config") and callable(
        getattr(instance, "_set_domain_from_config")
    ):
        # pylint: disable=protected-access
        instance._set_domain_from_config(config)
        logger.debug(
            "provider_domain_configured",
            provider=getattr(instance, "name", "unknown"),
        )


def collect_prefixes(registry: Dict[str, Any]) -> Dict[str, list]:
    """Collect all non-empty prefixes from activated providers.

    Args:
        registry: Dict of {provider_name: provider_instance}

    Returns:
        Dict mapping prefix -> list of provider names with that prefix
    """
    prefixes: Dict[str, list] = {}
    for provider_name, instance in registry.items():
        prefix = getattr(instance, "_prefix", None)
        if prefix:
            if prefix not in prefixes:
                prefixes[prefix] = []
            prefixes[prefix].append(provider_name)
    return prefixes


def validate_prefix_uniqueness(prefix_map: Dict[str, list]) -> None:
    """Validate that no prefix is claimed by multiple providers.

    Args:
        prefix_map: Dict from collect_prefixes()

    Raises:
        RuntimeError: If any prefix has multiple providers
    """
    dupes = {p: names for p, names in prefix_map.items() if len(names) > 1}
    if dupes:
        logger.error("duplicate_provider_prefixes", duplicates=dupes)
        raise RuntimeError(f"Duplicate provider prefixes detected: {dupes}")
