"""Unit tests for SyncRunRepository.get_recent_runs.

Runs the repository over the in-memory record store and asserts the
returned runs: scoped to one platform and user, newest first, and capped
at the requested limit.
"""

from datetime import UTC, datetime

import pytest

from infrastructure.records.in_memory import InMemoryRecordStore
from packages.access.sync.domain import SyncRunRecord
from packages.access.sync.store import SyncRunRepository

pytestmark = pytest.mark.unit


def _run(run_id: str, day: int, platform: str = "aws", user: str = "alice@example.com") -> SyncRunRecord:
    return SyncRunRecord(
        run_id=run_id,
        user_email=user,
        platform=platform,
        actions_applied=[],
        status="success",
        created_at=datetime(2026, 1, day, tzinfo=UTC),
    )


@pytest.fixture
def repository() -> SyncRunRepository:
    repo = SyncRunRepository(storage=InMemoryRecordStore())
    for run_id, day in (("r1", 1), ("r3", 3), ("r2", 2)):
        repo.save(_run(run_id, day))
    repo.save(_run("other-platform", 4, platform="gcp"))
    repo.save(_run("other-user", 5, user="bob@example.com"))
    return repo


def test_recent_runs_are_newest_first_for_one_platform_and_user(repository: SyncRunRepository) -> None:
    runs = repository.get_recent_runs("aws", "alice@example.com")

    assert [run.run_id for run in runs] == ["r3", "r2", "r1"]


def test_recent_runs_are_capped_at_limit(repository: SyncRunRepository) -> None:
    runs = repository.get_recent_runs("aws", "alice@example.com", limit=2)

    assert [run.run_id for run in runs] == ["r3", "r2"]


def test_recent_runs_for_unknown_user_is_empty(repository: SyncRunRepository) -> None:
    assert repository.get_recent_runs("aws", "nobody@example.com") == []
