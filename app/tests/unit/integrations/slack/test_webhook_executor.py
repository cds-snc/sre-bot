"""Tests for `SlackShield.execute_respond()` webhook classification.

Verifies that the webhook executor classifies HTTP status codes from
`AsyncWebhookClient` responses into the closed five-status set,
surfaces `Retry-After` from 429 responses, and never raises above the
shield boundary. `AsyncWebhookClient` does not raise `SlackApiError`;
classification is HTTP-status-based.
"""

from __future__ import annotations

import asyncio
from typing import Optional
from unittest.mock import MagicMock

import pytest

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus
from integrations.slack.settings import SlackSettings
from integrations.slack.shield import SlackShield

pytestmark = pytest.mark.unit


def _webhook_response(
    status_code: int,
    retry_after: Optional[str] = None,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"Retry-After": retry_after} if retry_after else {}
    return response


async def _coro(response: MagicMock):
    return response


@pytest.fixture
def shield() -> SlackShield:
    return SlackShield(settings=SlackSettings(SLACK_BOT_TOKEN="xoxb-test"))


class TestWebhookExecutorSuccess:
    async def test_http_200_returns_success(self, shield: SlackShield) -> None:
        result = await shield.execute_respond(_coro(_webhook_response(200)))

        assert result.is_success
        assert result.status == OperationStatus.SUCCESS

    async def test_http_200_carries_response_as_data(self, shield: SlackShield) -> None:
        response = _webhook_response(200)
        result = await shield.execute_respond(_coro(response))

        assert result.data is response


class TestWebhookExecutorPermanentErrors:
    async def test_http_404_is_permanent_error(self, shield: SlackShield) -> None:
        result = await shield.execute_respond(_coro(_webhook_response(404)))

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "webhook_not_found"

    async def test_http_400_is_permanent_error(self, shield: SlackShield) -> None:
        result = await shield.execute_respond(_coro(_webhook_response(400)))

        assert result.status == OperationStatus.PERMANENT_ERROR

    async def test_value_error_is_permanent_error(self, shield: SlackShield) -> None:
        async def raises():
            raise ValueError("missing response_url")

        result = await shield.execute_respond(raises())

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "webhook_value_error"

    async def test_unexpected_exception_is_permanent_error(
        self, shield: SlackShield
    ) -> None:
        async def raises():
            raise RuntimeError("unexpected")

        result = await shield.execute_respond(raises())

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "webhook_error"


class TestWebhookExecutorTransientErrors:
    async def test_http_429_is_transient_error(self, shield: SlackShield) -> None:
        result = await shield.execute_respond(_coro(_webhook_response(429)))

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "webhook_ratelimited"

    async def test_http_429_carries_retry_after(self, shield: SlackShield) -> None:
        result = await shield.execute_respond(
            _coro(_webhook_response(429, retry_after="15"))
        )

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.retry_after == 15

    @pytest.mark.parametrize("status_code", [500, 502, 503, 504])
    async def test_http_5xx_is_transient_error(
        self, shield: SlackShield, status_code: int
    ) -> None:
        result = await shield.execute_respond(_coro(_webhook_response(status_code)))

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "webhook_server_error"

    async def test_timeout_is_transient_error(self, shield: SlackShield) -> None:
        async def too_slow():
            await asyncio.sleep(5)
            return _webhook_response(200)

        shield_fast = SlackShield(
            settings=SlackSettings(
                SLACK_BOT_TOKEN="xoxb-test",
                SLACK_REQUEST_TIMEOUT_SECONDS=1,
            )
        )
        result = await shield_fast.execute_respond(too_slow())

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "request_timeout"


class TestWebhookExecutorContainment:
    """No exception propagates above `execute_respond()`."""

    @pytest.mark.parametrize(
        "status_code",
        [200, 404, 429, 500],
    )
    async def test_no_exception_propagates_for_any_status(
        self, shield: SlackShield, status_code: int
    ) -> None:
        result = await shield.execute_respond(_coro(_webhook_response(status_code)))

        assert isinstance(result, OperationResult)
