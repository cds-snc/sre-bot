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


def activate_providers() -> str:
    """Instantiate discovered providers with activation-time defaults and optional
    config overrides.

    Behavior:
    - Read config once.
    - Instantiate discovered provider classes preferring a no-config
      instantiation (providers should expose sensible defaults).
    - Apply provider-provided defaults (e.g. default_prefix / prefix) to the
      instance as activation-time metadata (instance._prefix).
    - If config contains an explicit override for a provider (cfg["prefix"]),
      normalize and apply that override after defaults.
    - Populate PROVIDER_REGISTRY and validate uniqueness of activated prefixes.
    - Determine and return the primary provider name.

    Raises:
        RuntimeError: on duplicate prefix collisions or when provider
            instantiation/validation fails.
    """
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
            # Prefer parameterless construction so providers supply sensible defaults
            try:
                instance = provider_cls()
            except TypeError:
                # Provider requires args — fall back to lightweight init:
                # - Prefer from_config if present (last resort)
                # - Else use init_kwargs from config
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
                        # Final fallback: attempt parameterless construction again
                        instance = provider_cls()

            if not isinstance(instance, GroupProvider):
                raise TypeError(f"Provider must be a GroupProvider instance: {name}")

            # Attach registration name to the instance for clarity
            setattr(instance, "name", name)

            # Apply provider-provided defaults (activation metadata).
            # Providers may expose `default_prefix` or `prefix`; prefer explicit
            # provider attribute, then fall back to the registration name.
            default_prefix = None
            if hasattr(instance, "default_prefix"):
                default_prefix = getattr(instance, "default_prefix")
            elif getattr(instance, "prefix", None) is not None:
                default_prefix = getattr(instance, "prefix")

            if isinstance(default_prefix, str):
                default_prefix = default_prefix.strip() or None

            # Ensure a sensible default exists (use registration name)
            if default_prefix is None:
                default_prefix = name

            # Set activation-time canonical prefix
            setattr(instance, "_prefix", default_prefix)

            # Now apply explicit config override if present (config wins)
            if isinstance(cfg, dict) and "prefix" in cfg:
                raw = cfg.get("prefix")
                override = None
                if isinstance(raw, str):
                    raw = raw.strip()
                    override = raw if raw else None
                # If override provided (non-empty), apply it
                if override:
                    setattr(instance, "_prefix", override)
                    logger.info(
                        "provider_prefix_overridden",
                        provider=name,
                        prefix=override,
                    )

            PROVIDER_REGISTRY[name] = instance
            logger.info(
                "provider_activated", provider=name, type=type(instance).__name__
            )
        except Exception as e:  # noqa: B902 - log and re-raise activation errors
            logger.error("provider_activation_failed", provider=name, error=str(e))
            raise

    # Validate uniqueness of non-empty prefixes (fail fast on collisions)
    prefixes: Dict[str, list] = {}
    for n, inst in PROVIDER_REGISTRY.items():
        p = getattr(inst, "_prefix", None)
        if p:
            prefixes.setdefault(p, []).append(n)
    dupes = {p: names for p, names in prefixes.items() if len(names) > 1}
    if dupes:
        logger.error("duplicate_provider_prefixes", duplicates=dupes)
        raise RuntimeError(f"Duplicate provider prefixes detected: {dupes}")

    # Determine primary provider
    provider_name = _determine_primary(provs_cfg)
    logger.info("primary_provider_set", provider=provider_name)
    return provider_name


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
