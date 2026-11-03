"""Unit tests for the scheduler's startup log levels and job count.

The schedule library is replaced by a mock, so registering a job schedules nothing. The
per-job and per-init lines are debug (the lifespan logs one info event with the job
count), and job_count reports how many jobs the library holds.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from structlog.testing import capture_logs

from jobs import scheduled_tasks
from jobs.scheduled_tasks import _ScheduleBackgroundJobRegistry, init, job_count

pytestmark = pytest.mark.unit


def test_job_count_returns_the_number_of_scheduled_jobs() -> None:
    """job_count counts the jobs the schedule library currently holds."""
    with patch.object(scheduled_tasks.schedule, "get_jobs", return_value=[object(), object(), object()]):
        assert job_count() == 3


def test_registering_a_feature_job_logs_at_debug_only() -> None:
    """A feature job registered on the scheduler logs one debug line and no info line."""
    registry = _ScheduleBackgroundJobRegistry(MagicMock())

    with patch.object(scheduled_tasks, "schedule_lib"), capture_logs() as entries:
        registry.register_daily(job_name="daily_job", schedule="03:30", job=MagicMock())
        registry.register_interval(job_name="interval_job", every=timedelta(minutes=5), job=MagicMock())

    assert [entry["log_level"] for entry in entries] == ["debug", "debug"]
    assert {entry["event"] for entry in entries} == {"feature_background_job_scheduled"}


def test_init_logs_no_info_event() -> None:
    """Initialising the scheduler logs its start at debug; the lifespan owns the one info event."""
    settings = MagicMock()
    settings.tenant = None

    with (
        patch.object(scheduled_tasks, "schedule"),
        patch.object(scheduled_tasks, "get_slack_settings", return_value=settings),
        capture_logs() as entries,
    ):
        init(MagicMock(), MagicMock())

    assert [entry for entry in entries if entry["log_level"] == "info"] == []
    assert "initializing_scheduled_tasks" in {entry["event"] for entry in entries}
