"""Tests for the per-call time budget enforced by `SlackShield.execute()`.

Verifies that the executor wraps the awaitable in `asyncio.wait_for(...)`
using `REQUEST_TIMEOUT_SECONDS` from settings, and that an awaitable
that never resolves classifies as `TRANSIENT_ERROR` once the budget
elapses.
"""

from __future__ import annotations

import asyncio

import pytest

from infrastructure.operations.status import OperationStatus
from integrations.slack.settings import SlackSettings
from integrations.slack.shield import SlackShield

pytestmark = pytest.mark.unit


@pytest.fixture
def shield_with_short_budget() -> SlackShield:
    return SlackShield(
        settings=SlackSettings(
            SLACK_BOT_TOKEN="xoxb-test",
            SLACK_REQUEST_TIMEOUT_SECONDS=1,
        )
    )


class TestPerCallTimeBudget:
    async def test_awaitable_that_exceeds_budget_returns_transient_error(
        self, shield_with_short_budget: SlackShield
    ) -> None:
        async def too_slow():
            await asyncio.sleep(5)
            return {"ok": True}

        result = await shield_with_short_budget.execute(too_slow())

        assert result.status == OperationStatus.TRANSIENT_ERROR

    async def test_timeout_classifies_with_request_timeout_error_code(
        self, shield_with_short_budget: SlackShield
    ) -> None:
        async def too_slow():
            await asyncio.sleep(5)
            return {"ok": True}

        result = await shield_with_short_budget.execute(too_slow())

        assert result.error_code == "request_timeout"

    async def test_fast_awaitable_does_not_time_out(
        self, shield_with_short_budget: SlackShield
    ) -> None:
        async def fast():
            return {"ok": True, "id": "1"}

        result = await shield_with_short_budget.execute(fast())

        assert result.is_success
        assert result.data == {"ok": True, "id": "1"}
