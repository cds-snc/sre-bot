"""Unit tests for infrastructure.slack.lifecycle helpers.

Covers initialize_slack_bot, start_slack_bot, and stop_slack_bot.
All branches — success, failure, and None guard — are exercised.
"""

import pytest
from unittest.mock import MagicMock

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.slack.lifecycle import (
    initialize_slack_bot,
    start_slack_bot,
    stop_slack_bot,
)
from infrastructure.slack.service import SlackBot

pytestmark = pytest.mark.unit


def _logger() -> MagicMock:
    return MagicMock()


def _bot_with_result(result: OperationResult, method: str) -> MagicMock:
    bot = MagicMock(spec=SlackBot)
    getattr(bot, method).return_value = result
    return bot


# ─────────────────────────────────────────────────────────────────────────────
# initialize_slack_bot
# ─────────────────────────────────────────────────────────────────────────────


class TestInitializeSlackBot:
    def test_returns_success_result_on_success(self):
        ok = OperationResult.success(message="ready")
        bot = _bot_with_result(ok, "initialize_app")

        result = initialize_slack_bot(bot, _logger())

        assert result.is_success

    def test_logs_info_on_success(self):
        ok = OperationResult.success(message="ready")
        bot = _bot_with_result(ok, "initialize_app")
        log = _logger()

        initialize_slack_bot(bot, log)

        log.info.assert_called_once_with("slack_bot_initialized")

    def test_returns_failure_result_on_error(self):
        err = OperationResult.permanent_error(
            message="bad token", error_code="MISSING_BOT_TOKEN"
        )
        bot = _bot_with_result(err, "initialize_app")

        result = initialize_slack_bot(bot, _logger())

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR

    def test_logs_warning_on_failure(self):
        err = OperationResult.permanent_error(
            message="bad token", error_code="MISSING_BOT_TOKEN"
        )
        bot = _bot_with_result(err, "initialize_app")
        log = _logger()

        initialize_slack_bot(bot, log)

        log.warning.assert_called_once()
        call_kwargs = log.warning.call_args
        assert "slack_bot_initialization_failed" in call_kwargs[0]


# ─────────────────────────────────────────────────────────────────────────────
# start_slack_bot
# ─────────────────────────────────────────────────────────────────────────────


class TestStartSlackBot:
    def test_returns_success_result_on_success(self):
        ok = OperationResult.success(message="started")
        bot = _bot_with_result(ok, "start")

        result = start_slack_bot(bot, _logger())

        assert result.is_success

    def test_logs_info_on_success(self):
        ok = OperationResult.success(message="started")
        bot = _bot_with_result(ok, "start")
        log = _logger()

        start_slack_bot(bot, log)

        log.info.assert_called_once_with("slack_bot_started")

    def test_returns_failure_result_on_error(self):
        err = OperationResult.permanent_error(
            message="no handler", error_code="SOCKET_MODE_HANDLER_MISSING"
        )
        bot = _bot_with_result(err, "start")

        result = start_slack_bot(bot, _logger())

        assert not result.is_success

    def test_logs_warning_on_failure(self):
        err = OperationResult.permanent_error(
            message="no handler", error_code="SOCKET_MODE_HANDLER_MISSING"
        )
        bot = _bot_with_result(err, "start")
        log = _logger()

        start_slack_bot(bot, log)

        log.warning.assert_called_once()
        assert "slack_bot_start_failed" in log.warning.call_args[0]


# ─────────────────────────────────────────────────────────────────────────────
# stop_slack_bot
# ─────────────────────────────────────────────────────────────────────────────


class TestStopSlackBot:
    def test_stops_bot_and_logs_stopped(self):
        bot = MagicMock(spec=SlackBot)
        log = _logger()

        stop_slack_bot(bot, log)

        bot.stop.assert_called_once()
        log.info.assert_called_once_with("slack_bot_stopped")

    def test_none_bot_does_not_call_stop(self):
        log = _logger()

        stop_slack_bot(None, log)  # Must not raise

        log.info.assert_not_called()
        log.warning.assert_not_called()
