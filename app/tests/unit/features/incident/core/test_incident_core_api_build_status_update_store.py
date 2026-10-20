"""Behavior tests for build_status_update_store, the StatusUpdateStore builder in core/api.py.

The builder runs over InMemoryRecordStore with IncidentCoreSettings built from
explicit values. Updates are appended through the built store and read back
from the records, so each test observes the table name taken from the
settings and the store interface the entry points receive.
"""

from datetime import UTC, datetime

import pytest

from features.incident.common.settings import IncidentCoreSettings
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateStore,
    StatusUpdateText,
    build_status_update_store,
)
from features.incident.core.store import status_updates_table
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

TABLE_NAME = "status-updates-under-test"
INCIDENT_ID = "inc-builder"
PK = f"INCIDENT#{INCIDENT_ID}"
AT = datetime(2026, 10, 7, 14, 0, tzinfo=UTC)
TEXT = StatusUpdateText(affected_service="GC Notify", impact="Delayed.", current_action="Restarting.", workaround="")
DRAFT = StatusUpdate(
    incident_id=INCIDENT_ID,
    sequence=1,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.INVESTIGATING,
    en=TEXT,
    fr=TEXT,
    next_update_at=AT,
    author="U0AUTHOR",
    transcript_cutoff=AT,
    transcript_fingerprint="fp-1",
    created_at=AT,
)


def _settings() -> IncidentCoreSettings:
    return IncidentCoreSettings(INCIDENT_CORE__STATUS_UPDATES_TABLE=TABLE_NAME)


def test_build_returns_a_status_update_store() -> None:
    assert isinstance(build_status_update_store(InMemoryRecordStore(), _settings()), StatusUpdateStore)


def test_build_writes_to_the_table_named_in_the_settings() -> None:
    records = InMemoryRecordStore()

    assert build_status_update_store(records, _settings()).append(DRAFT).is_success

    key = {"PK": PK, "SK": "UPDATE#000001"}
    assert records.get(status_updates_table(TABLE_NAME), key).is_success
    assert not records.get(status_updates_table("sre_bot_incident_status_updates"), key).is_success


def test_builder_is_a_plain_function_returning_a_new_store_per_call() -> None:
    """No process-wide cache: each entry point scope builds its own store."""
    records = InMemoryRecordStore()

    assert not hasattr(build_status_update_store, "cache_clear")
    assert build_status_update_store(records, _settings()) is not build_status_update_store(records, _settings())
