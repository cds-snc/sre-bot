"""Audit trail settings owned by the audit package."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class AuditSettings(InfrastructureSettings):
    """Configuration for the audit trail store.

    Environment Variables:
        AUDIT_TABLE_NAME: Record table holding audit events (default: sre_bot_audit_trail)
    """

    AUDIT_TABLE_NAME: str = Field(default="sre_bot_audit_trail", alias="AUDIT_TABLE_NAME")


@lru_cache(maxsize=1)
def get_audit_settings() -> AuditSettings:
    """Singleton provider for audit settings."""
    return AuditSettings()
