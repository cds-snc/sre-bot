"""Bootstrap and register infrastructure event handlers at startup.

This module registers system-level event handlers like audit that should
be active for all event types.
"""

from core.logging import get_module_logger
from infrastructure.events.dispatcher import register_event_handler
from infrastructure.events.handlers import handle_audit_event

logger = get_module_logger()


def register_infrastructure_handlers() -> None:
    """Register all infrastructure event handlers.

    Registers handlers for all event types via the wildcard "*" event type.
    These handlers are infrastructure-level and should be active regardless
    of specific event types.

    This should be called once at application startup before any events
    are dispatched.
    """
    # Register audit handler for all events via wildcard
    register_event_handler("*")(handle_audit_event)
    logger.info("infrastructure_handlers_registered", handlers=["audit"])
