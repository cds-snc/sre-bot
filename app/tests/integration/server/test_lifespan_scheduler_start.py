"""Integration tests for when the lifespan starts the scheduler.

Every startup service is stubbed and the lifespan logger is replaced by a mock.
The scheduler's init and run loop are stubbed, so starting it spawns no thread
and registers no job; the stop event they return is observed instead. The
[scheduler] slice is switched with SCHEDULER__ENABLED, which overrides the
configuration files. The Slack provider is a mock whose app is either present
or None (its initialisation failed), so the scheduler start is observed with
and without a Slack app. The environment name never decides the start.
"""

import threading
from collections.abc import Iterator
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from jobs.settings import get_scheduler_settings
from tests.factories.lifespan import lifespan


@pytest.fixture
def logger() -> MagicMock:
    return MagicMock()


@pytest.fixture
def provider() -> MagicMock:
    provider = MagicMock()
    provider.app = None
    return provider


@pytest.fixture
def stop_event() -> threading.Event:
    return threading.Event()


@pytest.fixture
def init() -> MagicMock:
    return MagicMock()


@pytest.fixture
def stubbed_startup(logger: MagicMock, provider: MagicMock, stop_event: threading.Event, init: MagicMock) -> Iterator[None]:
    get_scheduler_settings.cache_clear()
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
        stack.enter_context(patch("server.lifespan._register_legacy_handlers"))
        stack.enter_context(patch("server.lifespan.scheduled_tasks.init", init))
        stack.enter_context(patch("server.lifespan.scheduled_tasks.run_continuously", return_value=stop_event))
        yield
    get_scheduler_settings.cache_clear()


def _events(log_method: MagicMock) -> list[str]:
    return [call.args[0] for call in log_method.call_args_list]


@pytest.mark.integration
@pytest.mark.usefixtures("stubbed_startup")
async def test_the_scheduler_starts_when_enabled_with_the_slack_transport_off(
    logger: MagicMock, init: MagicMock, stop_event: threading.Event, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULER__ENABLED", "true")
    monkeypatch.setenv("SLACK_TRANSPORT__ENABLED", "false")

    app = FastAPI()
    async with lifespan(app):
        assert app.state.scheduled_stop_event is stop_event

    init.assert_called_once()
    assert len(init.call_args.args) == 2
    assert "scheduled_tasks_started" in _events(logger.info)
    assert stop_event.is_set()


@pytest.mark.integration
@pytest.mark.usefixtures("stubbed_startup")
async def test_the_scheduler_starts_when_enabled_and_the_slack_app_failed_to_initialise(
    logger: MagicMock, init: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULER__ENABLED", "true")

    async with lifespan(FastAPI()):
        pass

    assert "slack_provider_app_unavailable" in _events(logger.warning)
    init.assert_called_once()
    assert "scheduled_tasks_started" in _events(logger.info)


@pytest.mark.integration
@pytest.mark.usefixtures("stubbed_startup")
async def test_the_scheduler_starts_alongside_an_available_slack_app_without_receiving_it(
    provider: MagicMock, init: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULER__ENABLED", "true")
    provider.app = MagicMock(name="bolt_app")

    async with lifespan(FastAPI()):
        pass

    init.assert_called_once()
    assert provider.app not in init.call_args.args


@pytest.mark.integration
@pytest.mark.usefixtures("stubbed_startup")
async def test_the_scheduler_is_not_started_when_disabled_and_the_skip_is_logged(
    logger: MagicMock, init: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCHEDULER__ENABLED", "false")

    app = FastAPI()
    async with lifespan(app):
        assert app.state.scheduled_stop_event is None

    init.assert_not_called()
    logger.info.assert_any_call("scheduled_tasks_skipped", reason="scheduler_disabled")


@pytest.mark.integration
@pytest.mark.usefixtures("stubbed_startup")
async def test_a_production_host_with_the_scheduler_off_does_not_start_it(
    init: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The environment name never decides the start: production's files with the switch overridden off."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SCHEDULER__ENABLED", "false")
    monkeypatch.setenv("SLACK__BOT_TOKEN", "xoxb-scheduler-test")
    monkeypatch.setenv("SLACK__APP_TOKEN", "xapp-scheduler-test")

    async with lifespan(FastAPI()):
        pass

    init.assert_not_called()
