"""Unit tests for the access feature's record-table names and provider wiring.

Each table name defaults to the provisioned table, is overridable through
its ACCESS_* environment variable, and is what the provider-built repository
writes to; repositories are built over the in-memory record store so each
write is observed in the configured table.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from infrastructure.records.in_memory import InMemoryRecordStore
from infrastructure.records.protocol import RecordQuery
from packages.access.common import settings as access_settings
from packages.access.common.settings import AccessSettings
from packages.access.request import providers as request_providers
from packages.access.request.domain import ApprovalDecision
from packages.access.request.store import access_requests_table
from packages.access.sync import providers as sync_providers
from packages.access.sync.domain import SyncRunRecord
from packages.access.sync.job_status_store import job_status_table
from packages.access.sync.store import sync_runs_table

pytestmark = pytest.mark.unit


def test_table_names_default_to_provisioned_tables() -> None:
    settings = AccessSettings(_env_file=None)

    assert settings.requests.table_name == "sre_bot_access_requests"
    assert settings.sync.table_name == "sre_bot_access"
    assert settings.sync.job_status_table_name == "sre_bot_idempotency"


def test_table_names_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCESS_REQUESTS_TABLE_NAME", "requests_elsewhere")
    monkeypatch.setenv("ACCESS_SYNC_TABLE_NAME", "sync_elsewhere")
    monkeypatch.setenv("ACCESS_SYNC_JOB_STATUS_TABLE_NAME", "jobs_elsewhere")

    settings = AccessSettings(_env_file=None)

    assert settings.requests.table_name == "requests_elsewhere"
    assert settings.sync.table_name == "sync_elsewhere"
    assert settings.sync.job_status_table_name == "jobs_elsewhere"


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> Iterator[InMemoryRecordStore]:
    fake = InMemoryRecordStore()
    monkeypatch.setenv("ACCESS_REQUESTS_TABLE_NAME", "requests_elsewhere")
    monkeypatch.setenv("ACCESS_SYNC_TABLE_NAME", "sync_elsewhere")
    monkeypatch.setenv("ACCESS_SYNC_JOB_STATUS_TABLE_NAME", "jobs_elsewhere")
    monkeypatch.setattr(request_providers, "get_record_store", lambda: fake)
    monkeypatch.setattr(sync_providers, "get_record_store", lambda: fake)
    caches = (
        access_settings.get_access_settings,
        request_providers.get_access_request_repository,
        sync_providers.get_sync_run_repository,
        sync_providers.get_access_sync_job_status_store,
    )
    for provider in caches:
        provider.cache_clear()
    yield fake
    for provider in caches:
        provider.cache_clear()


def test_request_repository_writes_to_configured_table(store: InMemoryRecordStore) -> None:
    request_providers.get_access_request_repository().save_decision(
        ApprovalDecision(
            request_id="r1",
            actor_email="bob@example.com",
            decision="approved",
            comment="",
            decided_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )

    result = store.query(access_requests_table("requests_elsewhere"), RecordQuery(partition="ACCESS_REQUEST#r1"))

    assert [item["actor_email"] for item in result.data] == ["bob@example.com"]


def test_sync_run_repository_writes_to_configured_table(store: InMemoryRecordStore) -> None:
    sync_providers.get_sync_run_repository().save(
        SyncRunRecord(
            run_id="run-1",
            user_email="alice@example.com",
            platform="aws",
            actions_applied=[],
            status="success",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )

    result = store.query(sync_runs_table("sync_elsewhere"), RecordQuery(partition="SYNC_RUN#aws#alice@example.com"))

    assert [item["run_id"] for item in result.data] == ["run-1"]


def test_job_status_store_writes_to_configured_table(store: InMemoryRecordStore) -> None:
    sync_providers.get_access_sync_job_status_store().put("job-1", {"status": "running"}, ttl_seconds=60)

    result = store.get(job_status_table("jobs_elsewhere"), {"idempotency_key": "job-1"})

    assert result.is_success
