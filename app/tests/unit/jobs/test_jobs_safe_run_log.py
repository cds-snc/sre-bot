"""Unit tests for the safe_run error boundary's log of a failed job.

structlog's capture_logs records the event dict the boundary emits; nothing
else is stubbed. The boundary is the one place a failed run is logged
(decisions/reliability.md), so the event must carry the exception itself, which
the logging pipeline renders as the traceback inside the structured event.
"""

import pytest
from structlog.testing import capture_logs

from jobs.scheduled_tasks import safe_run

pytestmark = pytest.mark.unit


def _failing_job() -> None:
    raise ValueError("run failed")


def test_a_failed_job_is_logged_once_with_its_exception() -> None:
    with capture_logs() as events:
        safe_run(_failing_job)()

    errors = [event for event in events if event["log_level"] == "error"]
    assert [(event["event"], event["error"], event["function"]) for event in errors] == [
        ("safe_run_error", "run failed", "_failing_job")
    ]
    exc_info = errors[0]["exc_info"]
    assert isinstance(exc_info, ValueError) and exc_info.__traceback__ is not None


def test_a_successful_job_logs_no_error() -> None:
    with capture_logs() as events:
        safe_run(lambda: None)()

    assert [event for event in events if event["log_level"] == "error"] == []
