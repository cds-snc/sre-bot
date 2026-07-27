"""Unit tests for access sync Slack status command handling."""

from unittest.mock import MagicMock, patch

import pytest

from integrations.slack.models import CommandPayload, CommandResponse
from packages.access.sync.interactions.slack import handle_sync_status_command


@pytest.mark.unit
def test_handle_sync_status_command_returns_status_message_when_job_found() -> None:
    """Status command should render a presenter-backed message when a job exists."""
    payload = CommandPayload(text="status job-123", user_id="U123", channel_id="C123")
    parsed_args = {"job_id": "job-123"}
    fake_store = MagicMock()
    fake_store.get.return_value = {
        "job_id": "job-123",
        "sync_type": "platform",
        "platform": "aws",
        "dry_run": False,
        "status": "completed",
        "started_at": "2026-07-27T12:00:00+00:00",
        "completed_at": "2026-07-27T12:10:00+00:00",
        "users_synced": 3,
        "users_converged": 3,
        "orphans_found": 0,
        "requires_manual_action_count": 0,
        "changed_user_count": 1,
        "unchanged_user_count": 2,
        "action_counts": {},
        "lifecycle_actions": {},
        "entitlements_by_action": {},
    }

    with patch(
        "packages.access.sync.interactions.slack.get_access_sync_job_status_store",
        return_value=fake_store,
    ):
        result = handle_sync_status_command(payload, parsed_args)

    assert isinstance(result, CommandResponse)
    assert result.ephemeral is True
    assert "job-123" in result.message
    assert "completed" in result.message.lower()


@pytest.mark.unit
def test_handle_sync_status_command_returns_not_found_message_when_job_missing() -> None:
    """Status command should return a clear not-found message when no record exists."""
    payload = CommandPayload(text="status missing-job", user_id="U123", channel_id="C123")
    parsed_args = {"job_id": "missing-job"}
    fake_store = MagicMock()
    fake_store.get.return_value = None

    with patch(
        "packages.access.sync.interactions.slack.get_access_sync_job_status_store",
        return_value=fake_store,
    ):
        result = handle_sync_status_command(payload, parsed_args)

    assert isinstance(result, CommandResponse)
    assert result.ephemeral is True
    assert "No sync job found" in result.message
    assert "missing-job" in result.message
