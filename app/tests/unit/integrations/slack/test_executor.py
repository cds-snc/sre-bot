"""Tests for `SlackShield.execute()` exception classification.

Verifies that the async executor takes an `Awaitable`, returns
`OperationResult.success` on the awaitable's return value, classifies
every `SlackApiError` code into the closed five-status set, surfaces
`Retry-After` from rate-limit responses, and never raises an SDK
exception above the boundary.
"""

from __future__ import annotations

import asyncio
from typing import Optional
from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus
from integrations.slack.settings import SlackSettings
from integrations.slack.shield import SlackShield

pytestmark = pytest.mark.unit


def _slack_api_error(
    error_code: str,
    status_code: int = 200,
    retry_after: Optional[str] = None,
) -> SlackApiError:
    response = MagicMock()
    response.data = {"ok": False, "error": error_code}
    response.status_code = status_code
    response.headers = {"Retry-After": retry_after} if retry_after else {}
    return SlackApiError(error_code, response=response)


@pytest.fixture
def shield() -> SlackShield:
    return SlackShield(settings=SlackSettings(SLACK_BOT_TOKEN="xoxb-test"))


class TestExecuteSuccess:
    async def test_success_wraps_awaitable_return_in_operation_result(
        self, shield: SlackShield
    ) -> None:
        async def ok():
            return {"ok": True, "ts": "12345.67"}

        result = await shield.execute(ok())

        assert isinstance(result, OperationResult)
        assert result.is_success
        assert result.data == {"ok": True, "ts": "12345.67"}

    async def test_success_records_provider_name(self, shield: SlackShield) -> None:
        async def ok():
            return {"ok": True}

        result = await shield.execute(ok())

        assert result.provider == "slack"


class TestExecuteSlackErrorClassification:
    """Each known Slack error code maps to the right `OperationStatus`."""

    @pytest.mark.parametrize(
        "code",
        [
            "channel_not_found",
            "user_not_found",
            "message_not_found",
            "view_not_found",
        ],
    )
    async def test_not_found_codes(self, shield: SlackShield, code: str) -> None:
        async def raises():
            raise _slack_api_error(code)

        result = await shield.execute(raises())

        assert result.status == OperationStatus.NOT_FOUND
        assert result.error_code == code

    @pytest.mark.parametrize(
        "code",
        [
            "not_authed",
            "invalid_auth",
            "account_inactive",
            "token_revoked",
            "token_expired",
            "missing_scope",
        ],
    )
    async def test_unauthorized_codes(self, shield: SlackShield, code: str) -> None:
        async def raises():
            raise _slack_api_error(code)

        result = await shield.execute(raises())

        assert result.status == OperationStatus.UNAUTHORIZED
        assert result.error_code == code

    async def test_ratelimited_is_transient_and_carries_retry_after(
        self, shield: SlackShield
    ) -> None:
        async def raises():
            raise _slack_api_error("ratelimited", status_code=429, retry_after="7")

        result = await shield.execute(raises())

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ratelimited"
        assert result.retry_after == 7

    async def test_ratelimited_without_header_still_transient(
        self, shield: SlackShield
    ) -> None:
        async def raises():
            raise _slack_api_error("ratelimited", status_code=429)

        result = await shield.execute(raises())

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.retry_after is None

    @pytest.mark.parametrize(
        "code",
        ["fatal_error", "internal_error", "service_unavailable"],
    )
    async def test_other_transient_codes(self, shield: SlackShield, code: str) -> None:
        async def raises():
            raise _slack_api_error(code)

        result = await shield.execute(raises())

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == code

    async def test_unknown_code_falls_back_to_permanent_error(
        self, shield: SlackShield
    ) -> None:
        async def raises():
            raise _slack_api_error("some_brand_new_error")

        result = await shield.execute(raises())

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "some_brand_new_error"


class TestExecuteContainsExceptions:
    """No SDK exception ever propagates above `execute()`."""

    @pytest.mark.parametrize(
        "code",
        ["channel_not_found", "ratelimited", "missing_scope", "invalid_request"],
    )
    async def test_known_sdk_exceptions_do_not_escape(
        self, shield: SlackShield, code: str
    ) -> None:
        async def raises():
            raise _slack_api_error(code)

        # Should not raise — every shield-known exception is converted.
        result = await shield.execute(raises())

        assert not result.is_success

    async def test_unexpected_exception_classes_return_permanent_error(
        self, shield: SlackShield
    ) -> None:
        async def raises():
            raise RuntimeError("logic bug")

        result = await shield.execute(raises())

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "unexpected_error"


class TestExecuteUsesSettingsCatalogues:
    """The shield classifies against the catalogues carried on `SlackSettings`."""

    async def test_custom_not_found_code_routes_to_not_found(self) -> None:
        shield = SlackShield(
            settings=SlackSettings(
                SLACK_BOT_TOKEN="xoxb-x",
                SLACK_NOT_FOUND_CODES=["custom_missing"],
            )
        )

        async def raises():
            raise _slack_api_error("custom_missing")

        result = await shield.execute(raises())

        assert result.status == OperationStatus.NOT_FOUND

    async def test_default_code_is_no_longer_classified_when_overridden(self) -> None:
        shield = SlackShield(
            settings=SlackSettings(
                SLACK_BOT_TOKEN="xoxb-x",
                SLACK_NOT_FOUND_CODES=["only_this_one"],
            )
        )

        async def raises():
            raise _slack_api_error("channel_not_found")

        result = await shield.execute(raises())

        assert result.status == OperationStatus.PERMANENT_ERROR


# Silence unused-import warning if asyncio is not referenced elsewhere.
_ = asyncio
