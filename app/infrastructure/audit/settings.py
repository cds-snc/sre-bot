"""Audit trail settings owned by the audit package."""

from functools import lru_cache

from infrastructure.configuration.base import InfrastructureSettings


class AuditSettings(InfrastructureSettings):
    """Configuration for the audit trail store.

    Environment Variables:
        AUDIT_TABLE_NAME: Record table holding audit events (default: sre_bot_audit_trail)
    """

    audit_table_name: str = "sre_bot_audit_trail"


@lru_cache(maxsize=1)
def get_audit_settings() -> AuditSettings:
    """Singleton provider for audit settings."""
    return AuditSettings()
