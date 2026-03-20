"""Bootstrap for infrastructure event handlers.

The event system is currently disabled pending a design decision on durable
event delivery (SQS-backed).  Audit records are written synchronously via
``AuditTrailService.write_from_payload()`` in each feature service.

This module is kept so the lifespan import chain does not break and can be
re-enabled without touching call sites.
"""

import structlog

logger = structlog.get_logger()


def register_infrastructure_handlers() -> None:
    """No-op — event system is temporarily disabled.

    When re-enabled, register audit and other infrastructure handlers here
    and restore the call in ``server/lifespan.py``.
    """
    logger.info("infrastructure_event_handlers_disabled")
