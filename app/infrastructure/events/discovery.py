"""Event handler auto-discovery and registration.

Provides mechanisms to automatically discover and register event handlers
from module structures, ensuring handlers are loaded at startup without
explicit imports.

Usage:

    from infrastructure.events.discovery import discover_and_register_handlers

    # Scan modules and auto-register all handlers
    summary = discover_and_register_handlers(base_path="modules")

    # Log summary for visibility
    logger.info("event_handlers_discovered", summary=summary)

Features:
- Automatic module scanning by pattern
- Graceful error handling with per-module logging
- Discovery summary with handler counts and status
- No-op if already registered (idempotent)
"""

import importlib
from pathlib import Path
from typing import Dict, List, Any

from core.logging import get_module_logger

logger = get_module_logger()

# Track discovered modules to avoid re-discovery
_DISCOVERED_MODULES: set = set()


def discover_and_register_handlers(
    base_path: str = "modules",
    handler_module_name: str = "events.handlers",
    package_root: str = "",
) -> Dict[str, Any]:
    """Discover and register event handlers from module structure.

    Scans the module tree for `events.handlers` submodules and imports them,
    which triggers `@register_event_handler` decorators.

    Args:
        base_path: Relative path to scan (e.g., "modules")
        handler_module_name: Submodule to search for (e.g., "events.handlers")
        package_root: Package root for discovery (e.g., "modules")

    Returns:
        Dictionary with discovery summary:
        {
            "total_modules_scanned": int,
            "handlers_discovered": List[str],
            "handlers_registered": Dict[str, List[str]],
            "errors": Dict[str, str],
        }
    """
    from infrastructure.events.dispatcher import get_registered_events

    # Get absolute path to scan
    base_dir = Path(base_path)
    if not base_dir.is_absolute():
        base_dir = Path(__file__).parent.parent.parent / base_path

    if not base_dir.exists():
        logger.warning(
            "handler_discovery_path_not_found",
            path=str(base_dir),
        )
        return {
            "total_modules_scanned": 0,
            "handlers_discovered": [],
            "handlers_registered": {},
            "errors": {"path": f"Path not found: {base_dir}"},
        }

    # Scan and import
    discovered = []
    errors = {}

    try:
        _discover_handlers_recursive(
            base_path=str(base_dir),
            package_prefix=package_root or base_path.replace("/", "."),
            handler_module_name=handler_module_name,
            discovered_list=discovered,
            errors_dict=errors,
        )
    except Exception as e:
        logger.error(
            "handler_discovery_failed",
            error=str(e),
        )
        errors["discovery"] = str(e)

    # Get registered handlers
    registered = get_registered_events()

    summary = {
        "total_modules_scanned": len(discovered),
        "handlers_discovered": discovered,
        "handlers_registered": registered,
        "errors": errors if errors else None,
    }

    # Log summary
    logger.info(
        "event_handlers_auto_registered",
        total_scanned=len(discovered),
        total_registered=len(registered),
        error_count=len(errors),
    )

    return summary


def _discover_handlers_recursive(
    base_path: str,
    package_prefix: str,
    handler_module_name: str,
    discovered_list: List[str],
    errors_dict: Dict[str, str],
    _recursion_depth: int = 0,
) -> None:
    """Recursively discover and import handler modules.

    Args:
        base_path: Absolute filesystem path to scan
        package_prefix: Package prefix for imports
        handler_module_name: Submodule name to look for
        discovered_list: List to accumulate discovered module names
        errors_dict: Dict to accumulate error messages
        _recursion_depth: Current recursion depth (safety limit)
    """
    # Safety: limit recursion depth to prevent infinite loops
    if _recursion_depth > 10:
        logger.warning(
            "handler_discovery_max_depth_reached",
            depth=_recursion_depth,
        )
        return

    base_path_obj = Path(base_path)
    if not base_path_obj.is_dir():
        return

    # Check if this exact module was already discovered
    if base_path in _DISCOVERED_MODULES:
        return

    _DISCOVERED_MODULES.add(base_path)

    # Try to import handler module in this directory
    handler_full_name = f"{package_prefix}.{handler_module_name}"
    try:
        importlib.import_module(handler_full_name)
        discovered_list.append(handler_full_name)
        logger.debug(
            "event_handlers_module_imported",
            module=handler_full_name,
        )
    except (ImportError, ModuleNotFoundError):
        # No handler module in this package - not an error
        pass
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        errors_dict[handler_full_name] = error_msg
        logger.error(
            "event_handlers_module_import_failed",
            module=handler_full_name,
            error=error_msg,
        )

    # Recursively scan subdirectories
    try:
        for item in base_path_obj.iterdir():
            if item.is_dir() and not item.name.startswith(("_", ".")):
                sub_package = f"{package_prefix}.{item.name}"
                _discover_handlers_recursive(
                    base_path=str(item),
                    package_prefix=sub_package,
                    handler_module_name=handler_module_name,
                    discovered_list=discovered_list,
                    errors_dict=errors_dict,
                    _recursion_depth=_recursion_depth + 1,
                )
    except Exception as e:
        logger.warning(
            "handler_discovery_directory_scan_failed",
            path=base_path,
            error=str(e),
        )


def get_registered_handlers_by_event_type() -> Dict[str, List[str]]:
    """Get mapping of event types to registered handler names.

    Returns:
        Dict mapping event_type to list of handler function names.

    Example:
        {
            "group.member.added": ["handle_member_added"],
            "group.member.removed": ["handle_member_removed"],
            "group.listed": ["handle_group_listed"],
        }
    """
    from infrastructure.events.dispatcher import EVENT_HANDLERS

    result = {}
    for event_type, handlers in EVENT_HANDLERS.items():
        result[event_type] = [getattr(h, "__name__", "unknown") for h in handlers]

    return result


def log_registered_handlers() -> None:
    """Log all registered event handlers for visibility."""
    handlers_by_event = get_registered_handlers_by_event_type()

    if not handlers_by_event:
        logger.warning("no_event_handlers_registered")
        return

    for event_type in sorted(handlers_by_event.keys()):
        handler_names = handlers_by_event[event_type]
        logger.info(
            "event_handlers_registered",
            event_type=event_type,
            handler_count=len(handler_names),
            handlers=", ".join(handler_names),
        )
