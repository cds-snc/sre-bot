"""Unit tests for the audit trail's table-name setting and its provider wiring.

The table name defaults to the provisioned table, can be overridden through
the environment, and is what the provider-built service writes to; the
service is built over the in-memory record store so the write is observed
in the configured table.
"""

import pytest

from infrastructure.audit import service as audit_service
from infrastructure.audit.models import AuditEvent
from infrastructure.audit.settings import AuditSettings, get_audit_settings
from infrastructure.records.in_memory import InMemoryRecordStore
from infrastructure.records.protocol import RecordQuery

pytestmark = pytest.mark.unit


def test_table_name_defaults_to_provisioned_table() -> None:
    assert AuditSettings(_env_file=None).AUDIT_TABLE_NAME == "sre_bot_audit_trail"


def test_table_name_reads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_TABLE_NAME", "audit_elsewhere")

    assert AuditSettings(_env_file=None).AUDIT_TABLE_NAME == "audit_elsewhere"


def test_settings_provider_is_a_singleton() -> None:
    get_audit_settings.cache_clear()

    assert get_audit_settings() is get_audit_settings()

    get_audit_settings.cache_clear()


def test_provider_built_service_writes_to_configured_table(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryRecordStore()
    monkeypatch.setenv("AUDIT_TABLE_NAME", "audit_elsewhere")
    monkeypatch.setattr(audit_service, "get_record_store", lambda: store)
    get_audit_settings.cache_clear()
    audit_service.get_audit_trail_service.cache_clear()
    try:
        service = audit_service.get_audit_trail_service()
        service.write_audit_event(
            AuditEvent(
                correlation_id="c1",
                timestamp="2026-01-01T00:00:00+00:00",
                action="group_member_added",
                user_email="alice@example.com",
                result="success",
                resource_id="eng@example.com",
            )
        )
    finally:
        audit_service.get_audit_trail_service.cache_clear()
        get_audit_settings.cache_clear()

    written = store.query(audit_service.audit_table("audit_elsewhere"), RecordQuery(partition="eng@example.com"))
    assert [item["correlation_id"] for item in written.data] == ["c1"]
