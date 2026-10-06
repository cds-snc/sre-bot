"""Integration tests for the Slack provider start logs emitted by the lifespan.

Every startup service is stubbed and the lifespan logger is replaced by a mock,
so the only behaviour observed is which start event is logged. The test
environment check is forced off for the production cases: the provider is
started there, and only a failed start is reported. Under pytest the provider
is never started and the skip is logged instead.
"""

from collections.abc import Iterator
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from server.lifespan import lifespan


@pytest.fixture
def logger() -> MagicMock:
    return MagicMock()


@pytest.fixture
def provider() -> MagicMock:
    provider = MagicMock()
    provider.app = None
    return provider


@pytest.fixture
def stubbed_startup(logger: MagicMock, provider: MagicMock) -> Iterator[None]:
    with ExitStack() as stack:
        stack.enter_context(patch("server.lifespan._get_logger_from_app", return_value=logger))
        stack.enter_context(patch("server.lifespan._initialize_security_services"))
        stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
        stack.enter_context(patch("server.lifespan.get_plugin_manager"))
        stack.enter_context(patch("server.lifespan.load_plugins"))
        stack.enter_context(patch("server.lifespan._initialize_translation_service"))
        stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
        stack.enter_context(patch("server.lifespan.register_feature_integrations"))
        stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))
        yield


def _events(log_method: MagicMock) -> list[str]:
    return [call.args[0] for call in log_method.call_args_list]


@pytest.mark.integration
@pytest.mark.usefixtures("stubbed_startup")
async def test_successful_slack_start_logs_neither_failure_nor_skip(logger: MagicMock, provider: MagicMock) -> None:
    provider.start.return_value.is_success = True

    with patch("server.lifespan._is_test_environment", return_value=False):
        async with lifespan(FastAPI()):
            pass

    provider.start.assert_called_once_with()
    assert "slack_provider_start_skipped" not in _events(logger.info)
    assert "slack_provider_start_failed" not in _events(logger.warning)


@pytest.mark.integration
@pytest.mark.usefixtures("stubbed_startup")
async def test_failed_slack_start_logs_the_failure(logger: MagicMock, provider: MagicMock) -> None:
    provider.start.return_value.is_success = False
    provider.start.return_value.message = "socket refused"

    with patch("server.lifespan._is_test_environment", return_value=False):
        async with lifespan(FastAPI()):
            pass

    logger.warning.assert_any_call("slack_provider_start_failed", error="socket refused")
    assert "slack_provider_start_skipped" not in _events(logger.info)


@pytest.mark.integration
@pytest.mark.usefixtures("stubbed_startup")
async def test_test_environment_skips_the_slack_start_and_logs_the_skip(logger: MagicMock, provider: MagicMock) -> None:
    async with lifespan(FastAPI()):
        pass

    provider.start.assert_not_called()
    logger.info.assert_any_call("slack_provider_start_skipped", reason="test_environment")
