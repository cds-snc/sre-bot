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
    from core.config import settings  # Import at function level to avoid circular deps

    provider_configs = settings.groups.providers or {}

    # Filter discovered providers based on config
    new_registry: Dict[str, GroupProvider] = {}
    for name, provider_cls in DISCOVERED_PROVIDER_CLASSES.items():
        # Check if provider is explicitly disabled
        provider_cfg = provider_configs.get(name, {})
        if not provider_cfg.get("enabled", True):  # Default to enabled if not specified
            logger.info("provider_disabled_by_config", provider=name)
            continue
        try:
            # Prefer parameterless construction so providers supply sensible
            # defaults. If the provider requires custom construction, it may
            # provide a no-arg `from_config()` classmethod to be invoked here.
            try:
                instance = provider_cls()
            except TypeError as e:
                # Provider's __init__ requires args. Try explicit, no-arg
                # fallback constructors.
                if hasattr(provider_cls, "from_config") and callable(
                    getattr(provider_cls, "from_config")
                ):
                    # Call from_config with no args (explicit opt-in)
                    instance = provider_cls.from_config()
                elif hasattr(provider_cls, "from_empty_config") and callable(
                    getattr(provider_cls, "from_empty_config")
                ):
                    instance = provider_cls.from_empty_config()
                else:
                    raise RuntimeError(
                        f"Provider '{name}' cannot be constructed without "
                        "activation config. Implement a no-arg __init__ or "
                        "a no-arg classmethod 'from_config'/'from_empty_config'."
                    ) from e

            if not isinstance(instance, GroupProvider):
                raise TypeError(f"Provider must be a GroupProvider instance: {name}")

            # Attach registration name to the instance for clarity
            setattr(instance, "name", name)

            # Apply provider-provided defaults for prefix (activation-time
            # metadata). Prefer explicit `default_prefix` attribute, then the
            # provider's `prefix` property, and finally the registration name.
            default_prefix = None
            if hasattr(instance, "default_prefix"):
                default_prefix = getattr(instance, "default_prefix")
            elif getattr(instance, "prefix", None) is not None:
                default_prefix = getattr(instance, "prefix")

            if isinstance(default_prefix, str):
                default_prefix = default_prefix.strip() or None

            if default_prefix is None:
                default_prefix = name

            # Apply prefix from config if provided
            config_prefix = provider_cfg.get("prefix")
            if config_prefix and isinstance(config_prefix, str):
                setattr(instance, "_prefix", config_prefix.strip())
                logger.debug(
                    "provider_prefix_overridden", provider=name, prefix=config_prefix
                )
            else:
                setattr(instance, "_prefix", default_prefix)

            # Apply capability overrides from config if provided
            config_capabilities = provider_cfg.get("capabilities")
            if config_capabilities and isinstance(config_capabilities, dict):
                # Get current capabilities from provider
                original_capabilities = instance.capabilities

                # Create a new ProviderCapabilities instance with merged values
                # Config overrides take precedence over provider defaults
                from dataclasses import asdict

                caps_dict = asdict(original_capabilities)
                caps_dict.update(config_capabilities)

                # Create merged capabilities and store on instance
                merged_caps = type(original_capabilities)(**caps_dict)

                # Store override on the instance - the instance will check this
                # in its capabilities property getter
                setattr(instance, "_capability_override", merged_caps)

                logger.debug(
                    "provider_capabilities_overridden",
                    provider=name,
                    overrides=config_capabilities,
                )

            new_registry[name] = instance
            logger.info(
                "provider_activated",
                provider=name,
                type=type(instance).__name__,
                prefix=getattr(instance, "_prefix"),
            )
        except Exception as e:  # noqa: B902 - log and re-raise activation errors
            logger.error("provider_activation_failed", provider=name, error=str(e))
            raise

    # Validate uniqueness of non-empty prefixes (fail fast on collisions)
    prefixes: Dict[str, list] = {}
    for n, inst in new_registry.items():
        p = getattr(inst, "_prefix", None)
        if p:
            prefixes.setdefault(p, []).append(n)
    dupes = {p: names for p, names in prefixes.items() if len(names) > 1}
    if dupes:
        logger.error("duplicate_provider_prefixes", duplicates=dupes)
        raise RuntimeError(f"Duplicate provider prefixes detected: {dupes}")

    # Determine primary provider based on the freshly-built registry.
    provider_name = _determine_primary(registry=new_registry)

    # Atomically swap the active provider registry and record primary
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
