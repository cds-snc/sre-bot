"""Audit infrastructure for compliance and SIEM integration.

This package provides:
- AuditEvent: Pydantic model for structured audit events. Use
  ``AuditEvent.from_metadata()`` to construct events from feature data.
- AuditTrailService: Service for writing/querying the audit trail in DynamoDB.
  Inject via ``AuditTrailServiceDep`` from ``infrastructure.audit``.
"""

from infrastructure.audit.models import AuditEvent
from infrastructure.audit.protocol import AuditTrailService

__all__ = ["AuditEvent", "AuditTrailService"]
