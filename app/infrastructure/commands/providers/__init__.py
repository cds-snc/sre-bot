"""Command provider registry and activation system.

Explicit provider management with direct imports.
- Registration: @register_command_provider decorator
- Activation: Instantiate enabled providers from config
- Lookup: Retrieve active provider instances
"""

from typing import Dict
import importlib
import pkgutil
import structlog
from infrastructure.commands.providers.base import CommandProvider
from infrastructure.services.providers import get_settings

logger = structlog.get_logger()
settings = get_settings()
# Registry of discovered command providers (populated by provider modules)
_discovered: Dict[str, type] = {}

# Active provider instances
_active: Dict[str, CommandProvider] = {}


def register_command_provider(name: str):
    """Register a command provider adapter.

    Args:
        name: Unique identifier for this provider (e.g., 'slack', 'teams')

    Returns:
        Decorator function

    Example:
        @register_command_provider("slack")
        class SlackCommandProvider(CommandProvider):
            ...
    """

    def decorator(cls):
        if not isinstance(cls, type):
            raise TypeError("register_command_provider must be applied to a class")

        if not issubclass(cls, CommandProvider):
            raise TypeError(f"Command provider must subclass CommandProvider: {name}")

        if name in _discovered:
            raise RuntimeError(f"Command provider already registered: {name}")

        _discovered[name] = cls
        logger.debug(
            "command_provider_discovered",
            provider=name,
            class_name=cls.__name__,
        )
        return cls

    return decorator


def activate_providers() -> Dict[str, CommandProvider]:
    """Activate command providers based on configuration.

    Reads core.config.settings.commands.providers and instantiates
    enabled providers.

    Returns:
        Dict mapping provider name to adapter instance

    Raises:
        RuntimeError: If provider activation fails
        ValueError: If configuration is invalid
    """
    try:
        provider_configs = settings.commands.providers or {}
    except AttributeError:
        logger.info("no_command_providers_configured")
        return {}

    # Filter to enabled providers that are registered
    enabled = {
        name: cfg
        for name, cfg in provider_configs.items()
        if cfg.get("enabled", True) and name in _discovered
    }

    if not enabled:
        logger.info("no_command_providers_enabled_api_only_mode")
        return {}

    new_active: Dict[str, CommandProvider] = {}

    for name, provider_cfg in enabled.items():
        adapter_class = _discovered[name]

        try:
            # Instantiate with config
            instance = adapter_class(provider_cfg)
            new_active[name] = instance

            logger.info(
                "command_provider_activated",
                provider=name,
                type=adapter_class.__name__,
            )

        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "command_provider_activation_failed",
                provider=name,
                error=str(e),
            )
            raise

    global _active  # pylint: disable=global-statement
    _active = new_active

    logger.info(
        "command_providers_activated",
        count=len(new_active),
        providers=list(new_active.keys()),
    )

    return new_active


def get_active_providers() -> Dict[str, CommandProvider]:
    """Get all active command provider instances.

    Returns:
        Dict mapping provider name to adapter instance
    """
    return _active.copy()


def get_provider(name: str) -> CommandProvider:
    """Get command provider by name.

    Args:
        name: Provider name (e.g., 'slack')

    Returns:
        CommandProvider instance

    Raises:
        ValueError: If provider not active
    """
    if name not in _active:
        raise ValueError(f"Command provider not active: {name}")

    return _active[name]


def load_providers() -> Dict[str, CommandProvider]:
    """Initialize and activate command providers.

    Explicitly imports provider modules to trigger registration,
    then activates enabled providers from configuration.

    Returns:
        Dict of active provider instances
    """

    for module_info in pkgutil.iter_modules(__path__):
        module_name = module_info.name
        full_module_name = f"{__name__}.{module_name}"
        try:
            importlib.import_module(full_module_name)
            logger.debug("provider_module_imported", module=full_module_name)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "provider_module_import_failed",
                module=full_module_name,
                error=str(e),
            )
    # Activate providers from config
    return activate_providers()


def reset_registry() -> None:
    """Reset provider registry. Used for testing."""
    global _active  # pylint: disable=global-statement
    _active = {}
    logger.debug("command_provider_registry_reset")
