"""Base plugin discovery utilities."""

import importlib
import pkgutil
from pathlib import Path
from typing import List

import pluggy
import structlog

logger = structlog.get_logger()


def auto_discover_plugins(
    pm: pluggy.PluginManager,
    base_paths: List[str],
) -> None:
    """Auto-discover and register plugins from base paths.

    This function scans the specified base paths (e.g., "packages", "modules")
    for Python packages and imports them. If a package has functions decorated
    with @hookimpl, they are automatically registered with the plugin manager.

    Args:
        pm: Plugin manager to register plugins with.
        base_paths: List of base paths to search (e.g., ["packages", "modules"]).

    Example:
        >>> pm = pluggy.PluginManager("sre_bot")
        >>> pm.add_hookspecs(hookspecs.platforms)
        >>> auto_discover_plugins(pm, base_paths=["packages", "modules"])
        # Now pm has all @hookimpl functions from all packages
    """
    for base_path in base_paths:
        path = Path(base_path)
        if not path.exists():
            logger.warning("base_path_not_found", path=str(path))
            continue

        logger.debug("scanning_base_path", path=str(path))

        # Discover all packages in this base path
        for pkg_info in pkgutil.iter_modules([str(path)]):
            if pkg_info.ispkg:
                module_name = f"{base_path}.{pkg_info.name}"
                try:
                    # Import the package - this executes __init__.py
                    # If __init__.py has @hookimpl functions, they get registered
                    module = importlib.import_module(module_name)
                    pm.register(module)
                    logger.debug("plugin_registered", module=module_name)
                except Exception as e:
                    logger.error(
                        "plugin_registration_failed",
                        module=module_name,
                        error=str(e),
                        exc_info=True,
                    )
