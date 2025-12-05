"""Audit infrastructure for compliance and SIEM integration.

This package provides:
- AuditEvent: Pydantic model for structured audit events
- Sentinel integration utilities
- Standard audit fields for compliance
"""

from infrastructure.audit.models import AuditEvent

__all__ = ["AuditEvent"]
