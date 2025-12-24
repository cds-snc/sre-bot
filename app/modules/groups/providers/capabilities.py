"""Provider capability loading with config-driven overrides.

This module handles loading provider capabilities from settings, applying
config-driven overrides, and providing convenience helper functions.

Separation of concerns:
  - contracts.py: Pure capability data structure (ProviderCapabilities)
  - capabilities.py: Config-driven loading and merging logic
  - base.py: Capability-aware provider lifecycle
"""

import dataclasses
from typing import Dict, Any

import structlog
from infrastructure.configuration import settings
from modules.groups.providers.contracts import ProviderCapabilities

logger = structlog.get_logger()


def load_capabilities(provider_name: str) -> ProviderCapabilities:
    """Load provider capabilities from settings with config-driven overrides.

    Priority:
    1. Provider's advertised default capabilities (from __init__)
    2. Config-based overrides from settings.groups.providers[provider_name].capabilities

    Args:
        provider_name: Name of the provider (e.g., 'google', 'aws')

    Returns:
        ProviderCapabilities with merged settings

    Raises:
        ValueError: If settings or provider config is malformed
    """
    # Start with default capabilities
    base_capabilities = ProviderCapabilities()

    # Fetch config if available
    try:
        cfg = getattr(settings, "groups", None)
        if not cfg:
            return base_capabilities

        provider_cfg = (
            cfg.providers.get(provider_name, {})
            if isinstance(cfg.providers, dict)
            else {}
        )

        if not isinstance(provider_cfg, dict):
            return base_capabilities

        caps_override = provider_cfg.get("capabilities", {})
        if not isinstance(caps_override, dict):
            return base_capabilities

    except (AttributeError, TypeError) as e:
        logger.warning(
            "capability_load_failed",
            provider=provider_name,
            error=str(e),
        )
        return base_capabilities

    # Merge overrides into base
    merged_dict = dataclasses.asdict(base_capabilities)
    merged_dict.update(caps_override)

    return ProviderCapabilities(**merged_dict)


def apply_capability_overrides(instance: Any, config: Dict[str, Any]) -> None:
    """Apply config-driven capability overrides to a provider instance.

    Mutates the instance by setting _capability_override attribute with
    merged capabilities. This allows instances to advertise capabilities
    from their __init__ but be overridden at activation time via config.

    Args:
        instance: The provider instance
        config: The provider's config dict (from settings.groups.providers[name])
    """
    config_caps = config.get("capabilities")
    if not config_caps or not isinstance(config_caps, dict):
        return

    # Get provider's default capabilities
    base_caps = dataclasses.asdict(instance.capabilities)

    # Merge with config overrides
    base_caps.update(config_caps)
    merged = ProviderCapabilities(**base_caps)

    # Store on instance for get_capabilities() to use
    instance._capability_override = merged

    logger.debug(
        "capability_override_applied",
        provider=getattr(instance, "name", "unknown"),
        overrides=list(config_caps.keys()),
    )


def provider_supports(provider_name: str, capability: str) -> bool:
    """Return whether the named provider advertises a given capability.

    Args:
        provider_name: Name of the provider
        capability: Name of the capability flag (e.g., 'provides_role_info')

    Returns:
        True if capability is supported, False otherwise
    """
    try:
        caps = load_capabilities(provider_name)
        return bool(getattr(caps, capability, False))
    except Exception:
        return False


def provider_provides_role_info(provider_name: str) -> bool:
    """Convenience wrapper for the common 'provides_role_info' check.

    Args:
        provider_name: Name of the provider

    Returns:
        True if provider provides role information
    """
    return provider_supports(provider_name, "provides_role_info")
