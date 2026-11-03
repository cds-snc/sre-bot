"""Integration tests for the Slack provider start logs emitted by the lifespan.

Every startup service is stubbed and the lifespan logger is replaced by a mock,
so the only behaviour observed is whether the provider is started and which start
event is logged. The provider is started only when it has a Bolt app, which means
Slack is enabled and initialised; otherwise the start is skipped with a debug event
and a boot with Slack off logs no start failure.
"""

from collections.abc import Iterator
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from tests.factories.lifespan import lifespan


@pytest.fixture
def logger() -> MagicMock:
    return MagicMock()


@pytest.fixture
def provider() -> MagicMock:
    provider = MagicMock()
    provider.app = MagicMock(name="bolt_app")
    return provider


@pytest.fixture
def stubbed_startup(logger: MagicMock, provider: MagicMock) -> Iterator[None]:
    with ExitStack() as stack:
        stack.enter_context(patch("server.lifespan._get_logger_from_app", return_value=logger))
        stack.enter_context(patch("server.lifespan.initialize_core_services"))
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

    async with lifespan(FastAPI()):
        pass

    provider.start.assert_called_once_with()
    assert "slack_provider_start_skipped" not in _events(logger.debug)
    assert "slack_provider_start_failed" not in _events(logger.warning)


@pytest.mark.integration
@pytest.mark.usefixtures("stubbed_startup")
async def test_failed_slack_start_logs_the_failure(logger: MagicMock, provider: MagicMock) -> None:
    provider.start.return_value.is_success = False
    provider.start.return_value.message = "socket refused"

    async with lifespan(FastAPI()):
        pass

    logger.warning.assert_any_call("slack_provider_start_failed", error="socket refused")
    assert "slack_provider_start_skipped" not in _events(logger.debug)


@pytest.mark.integration
@pytest.mark.usefixtures("stubbed_startup")
async def test_a_provider_without_an_app_is_not_started_and_the_skip_is_logged_at_debug(
    logger: MagicMock, provider: MagicMock
) -> None:
    provider.app = None

    async with lifespan(FastAPI()):
        pass

    provider.start.assert_not_called()
    logger.debug.assert_any_call("slack_provider_start_skipped", reason="slack_disabled")
    assert "slack_provider_start_failed" not in _events(logger.warning)
