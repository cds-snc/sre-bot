# modules/groups/providers/__init__.py
from pathlib import Path
from typing import Dict, Optional
import importlib
import types
import asyncio
from core.config import settings
from core.logging import get_module_logger
from modules.groups.providers.base import (
    GroupProvider,
    ProviderCapabilities,
    OperationResult,
    OperationStatus,
)

logger = get_module_logger()

# Provider registry - maps provider names to provider instances
PROVIDER_REGISTRY: Dict[str, GroupProvider] = {}


def register_provider(name: str):
    """Decorator to register a provider class or instance.

    Usage:
        @register_provider("google")
        class GoogleWorkspaceProvider(GroupProvider):
            ...

        or

        register_provider("google")(GoogleWorkspaceProvider())
    """

    def decorator(obj):
        # instantiate classes, accept instances
        instance = obj() if isinstance(obj, type) else obj

        # If a bare function was decorated, resolve its module and wrap it
        if isinstance(instance, types.FunctionType):
            module_name = instance.__module__
            try:
                module = importlib.import_module(module_name)
            except Exception:
                raise TypeError(
                    f"Could not import module for provider function: {module_name}"
                )
            instance = _ModuleAdapter(module)

        # If a module object was passed, wrap it too
        if isinstance(instance, types.ModuleType):
            instance = _ModuleAdapter(instance)

        if not isinstance(instance, GroupProvider):
            raise TypeError(
                f"Registered provider must implement GroupProvider: {name}, got {type(instance)}"
            )

        # Apply per-provider configuration (enable/disable or capability overrides)
        try:

            provider_cfg = {}
            if getattr(settings, "groups", None) and isinstance(
                settings.groups.providers, dict
            ):
                provider_cfg = settings.groups.providers.get(name, {}) or {}
            enabled = provider_cfg.get("enabled", True)
            if not enabled:
                logger.info("provider_disabled_by_config", provider=name)
                return obj
            # if capabilities provided in config, set them on instance if supported
            caps = provider_cfg.get("capabilities")
            if caps and hasattr(instance, "_capabilities"):
                try:
                    instance._capabilities = ProviderCapabilities.from_config(name)
                except Exception:
                    # ignore config errors and keep default capabilities
                    pass
        except Exception:
            # on any config import error, fall back to registering normally
            pass

        PROVIDER_REGISTRY[name] = instance
        logger.info("provider_registered", provider=name, type=type(instance).__name__)
        return obj

    return decorator


def get_provider(provider_name: str) -> GroupProvider:
    """Get provider instance by name (raises ValueError if unknown)."""
    if provider_name not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider_name}")
    return PROVIDER_REGISTRY[provider_name]


def get_active_providers(provider_filter: Optional[str] = None) -> Dict:
    """Get all active providers or filtered by name."""
    if provider_filter:
        return {provider_filter: get_provider(provider_filter)}
    return PROVIDER_REGISTRY


def load_providers():
    """Auto-discover and load all provider modules found in this package."""
    providers_dir = Path(__file__).parent

    for file_path in providers_dir.glob("*.py"):
        if file_path.name.startswith("__"):
            continue

        module_name = f"modules.groups.providers.{file_path.stem}"
        try:
            importlib.import_module(module_name)
            logger.info(f"Loaded provider module: {module_name}")
        except ImportError as e:
            logger.warning(f"Failed to load provider {module_name}: {e}")


class _ModuleAdapter(GroupProvider):
    """Adapter that exposes module-level functions as an async GroupProvider.

    It looks for common function names in the module and calls them in a
    thread pool (via asyncio.to_thread) to avoid blocking the event loop.
    """

    def __init__(self, module: types.ModuleType):
        self.module = module
        # default capabilities; module may optionally provide `CAPABILITIES`
        self._capabilities = getattr(module, "CAPABILITIES", ProviderCapabilities())

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    async def list_group_members(self, group_id: str) -> OperationResult:
        fn = getattr(self.module, "get_group_members", None) or getattr(
            self.module, "list_members", None
        )
        if fn is None:
            return OperationResult(
                status=OperationStatus.PERMANENT_ERROR,
                message="list_group_members not implemented",
            )
        try:
            result = await asyncio.to_thread(fn, group_id)
            return _wrap_op_result(result)
        except Exception as e:
            return OperationResult(
                status=OperationStatus.TRANSIENT_ERROR, message=str(e)
            )

    async def add_group_member(
        self, group_id: str, member_id: str, **metadata
    ) -> OperationResult:
        fn = getattr(self.module, "add_member", None) or getattr(
            self.module, "insert_member", None
        )
        if fn is None:
            return OperationResult(
                status=OperationStatus.PERMANENT_ERROR,
                message="add_group_member not implemented",
            )
        try:
            result = await asyncio.to_thread(fn, group_id, member_id)
            return _wrap_op_result(result)
        except Exception as e:
            return OperationResult(
                status=OperationStatus.TRANSIENT_ERROR, message=str(e)
            )

    async def remove_group_member(
        self, group_id: str, member_id: str, **metadata
    ) -> OperationResult:
        fn = getattr(self.module, "remove_member", None) or getattr(
            self.module, "delete_member", None
        )
        if fn is None:
            return OperationResult(
                status=OperationStatus.PERMANENT_ERROR,
                message="remove_group_member not implemented",
            )
        try:
            result = await asyncio.to_thread(fn, group_id, member_id)
            return _wrap_op_result(result)
        except Exception as e:
            return OperationResult(
                status=OperationStatus.TRANSIENT_ERROR, message=str(e)
            )


def _wrap_op_result(resp) -> OperationResult:
    """Normalize a variety of legacy return shapes into OperationResult."""
    # IntegrationResponse-like object
    if resp is None:
        return OperationResult(status=OperationStatus.NOT_FOUND, message="no result")
    if hasattr(resp, "success"):
        # try to map success/failure
        if getattr(resp, "success"):
            return OperationResult(
                status=OperationStatus.SUCCESS,
                message="ok",
                data=getattr(resp, "data", None) or resp,
            )
        else:
            return OperationResult(
                status=OperationStatus.PERMANENT_ERROR,
                message="integration error",
                data={"response": resp},
            )
    # raw list/dict
    if isinstance(resp, (list, dict)):
        return OperationResult(
            status=OperationStatus.SUCCESS, message="ok", data={"result": resp}
        )
    # fallback
    return OperationResult(
        status=OperationStatus.SUCCESS, message="ok", data={"result": resp}
    )


# Auto-load providers when module is imported
load_providers()
