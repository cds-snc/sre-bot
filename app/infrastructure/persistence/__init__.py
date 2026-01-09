"""Persistence layer for audit trail and operational data.

Provides storage backends for audit events and other operational data
that need to be queried or retained beyond the SIEM system.

Recommended Usage (Service Pattern with DI):
    from infrastructure.services import PersistenceServiceDep

    @router.post("/audit/write")
    def write_audit(
        persistence: PersistenceServiceDep,
        event: AuditEvent
    ):
        success = persistence.write_audit_event(event)
        return {"written": success}
"""

from infrastructure.persistence.service import PersistenceService

__all__ = [
    "PersistenceService",
]
