"""Unit tests for blinker-backed event dispatcher facade."""

from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest

from infrastructure.events.service import EventDispatcher

pytestmark = pytest.mark.unit


class _ImmediateExecutor:
    """Executor test double that runs work immediately."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def submit(self, fn, *args, **kwargs) -> Future:
        self.calls.append((fn, args, kwargs))
        fn(*args, **kwargs)
        future: Future = Future()
        future.set_result(None)
        return future


class _FailingExecutor:
    """Executor test double that fails on submit."""

    def submit(self, _fn, *_args, **_kwargs):
        raise RuntimeError("submit failed")


def test_register_handler_and_dispatch(dispatcher, event_factory, mock_handler) -> None:
    event = event_factory(event_type="access.requested")
    dispatcher.register_handler("access.requested", mock_handler)

    dispatcher.dispatch(event)

    mock_handler.assert_called_once_with(event)


def test_dispatch_calls_multiple_handlers(dispatcher, event_factory) -> None:
    first = MagicMock()
    second = MagicMock()
    event = event_factory(event_type="sync.completed")

    dispatcher.register_handler("sync.completed", first)
    dispatcher.register_handler("sync.completed", second)

    dispatcher.dispatch(event)

    first.assert_called_once_with(event)
    second.assert_called_once_with(event)


def test_dispatch_error_isolation(dispatcher, event_factory) -> None:
    calls: list[str] = []

    def first(_event) -> None:
        calls.append("first")

    def second(_event) -> None:
        calls.append("second")
        raise ValueError("boom")

    def third(_event) -> None:
        calls.append("third")

    event = event_factory(event_type="request.approved")
    dispatcher.register_handler("request.approved", first)
    dispatcher.register_handler("request.approved", second)
    dispatcher.register_handler("request.approved", third)

    dispatcher.dispatch(event)

    assert sorted(calls) == ["first", "second", "third"]


def test_dispatch_no_handlers_does_not_raise(dispatcher, event_factory) -> None:
    event = event_factory(event_type="no.handlers")

    dispatcher.dispatch(event)


def test_dispatch_logs_handler_failure(dispatcher, event_factory, monkeypatch) -> None:
    def bad_handler(_event) -> None:
        raise RuntimeError("failed")

    event = event_factory(event_type="sync.failed")
    dispatcher.register_handler("sync.failed", bad_handler)

    bound_logger = MagicMock()
    service_logger = MagicMock()
    service_logger.bind.return_value = bound_logger
    monkeypatch.setattr("infrastructure.events.service.logger", service_logger)

    dispatcher.dispatch(event)

    bound_logger.exception.assert_called_once()
    assert bound_logger.exception.call_args.args[0] == "event_handler_failed"
    assert bound_logger.exception.call_args.kwargs["handler"] == "bad_handler"


def test_dispatch_does_not_propagate_handler_exception(dispatcher, event_factory) -> None:
    def bad_handler(_event) -> None:
        raise RuntimeError("failed")

    event = event_factory(event_type="request.rejected")
    dispatcher.register_handler("request.rejected", bad_handler)

    dispatcher.dispatch(event)


def test_register_handler_logs_registration(dispatcher, mock_handler, monkeypatch) -> None:
    bound_logger = MagicMock()
    service_logger = MagicMock()
    service_logger.bind.return_value = bound_logger
    monkeypatch.setattr("infrastructure.events.service.logger", service_logger)

    dispatcher.register_handler("audit.logged", mock_handler)

    bound_logger.info.assert_called_once()
    assert bound_logger.info.call_args.args[0] == "event_handler_registered"
    assert bound_logger.info.call_args.kwargs["handler_count"] == 1


def test_dispatch_background_submits_to_executor(dispatcher: EventDispatcher, event_factory) -> None:
    event = event_factory(event_type="background.event")
    executor = _ImmediateExecutor()
    dispatcher._get_or_create_executor = MagicMock(return_value=executor)  # type: ignore[method-assign]

    dispatcher.dispatch_background(event)

    assert len(executor.calls) == 1


def test_dispatch_background_error_isolation(dispatcher, event_factory, monkeypatch) -> None:
    def bad_handler(_event) -> None:
        raise RuntimeError("failed")

    event = event_factory(event_type="background.failed")
    dispatcher.register_handler("background.failed", bad_handler)

    bound_logger = MagicMock()
    service_logger = MagicMock()
    service_logger.bind.return_value = bound_logger
    monkeypatch.setattr("infrastructure.events.service.logger", service_logger)

    executor = _ImmediateExecutor()
    dispatcher._get_or_create_executor = MagicMock(return_value=executor)  # type: ignore[method-assign]

    dispatcher.dispatch_background(event)

    bound_logger.exception.assert_called_once()
    assert bound_logger.exception.call_args.args[0] == "event_handler_failed"


def test_start_executor_creates_pool(dispatcher: EventDispatcher) -> None:
    assert dispatcher._executor is None

    dispatcher.start_executor(max_workers=1)

    assert dispatcher._executor is not None


def test_shutdown_executor_stops_pool(dispatcher: EventDispatcher) -> None:
    dispatcher.start_executor(max_workers=1)

    dispatcher.shutdown_executor(wait=True)

    assert dispatcher._executor is None


def test_shutdown_executor_idempotent(dispatcher: EventDispatcher) -> None:
    dispatcher.start_executor(max_workers=1)

    dispatcher.shutdown_executor(wait=False)
    dispatcher.shutdown_executor(wait=False)


def test_dispatch_background_after_shutdown_logs_error(dispatcher, event_factory, monkeypatch) -> None:
    event = event_factory(event_type="post.shutdown")
    dispatcher.start_executor(max_workers=1)
    dispatcher.shutdown_executor(wait=True)

    bound_logger = MagicMock()
    service_logger = MagicMock()
    service_logger.bind.return_value = bound_logger
    monkeypatch.setattr("infrastructure.events.service.logger", service_logger)

    dispatcher.dispatch_background(event)

    bound_logger.error.assert_called_once()
    assert bound_logger.error.call_args.args[0] == "event_executor_unavailable"


def test_dispatch_background_logs_submit_failure(dispatcher, event_factory, monkeypatch) -> None:
    event = event_factory(event_type="submit.error")

    bound_logger = MagicMock()
    service_logger = MagicMock()
    service_logger.bind.return_value = bound_logger
    monkeypatch.setattr("infrastructure.events.service.logger", service_logger)

    dispatcher._get_or_create_executor = MagicMock(return_value=_FailingExecutor())  # type: ignore[method-assign]

    dispatcher.dispatch_background(event)

    bound_logger.exception.assert_called_once()
    assert bound_logger.exception.call_args.args[0] == "failed_to_submit_event_to_executor"


def test_get_registered_event_types(dispatcher, mock_handler) -> None:
    dispatcher.register_handler("event.one", mock_handler)
    dispatcher.register_handler("event.two", mock_handler)

    registered = dispatcher.get_registered_event_types()

    assert set(registered) == {"event.one", "event.two"}


def test_get_handler_count(dispatcher, mock_handler) -> None:
    dispatcher.register_handler("event.counted", mock_handler)

    count = dispatcher.get_handler_count("event.counted")

    assert count == 1


def test_get_handler_count_unregistered(dispatcher: EventDispatcher) -> None:
    assert dispatcher.get_handler_count("missing.event") == 0


def test_different_event_types_isolated(dispatcher, event_factory) -> None:
    first = MagicMock()
    second = MagicMock()

    dispatcher.register_handler("type.a", first)
    dispatcher.register_handler("type.b", second)

    dispatcher.dispatch(event_factory(event_type="type.a"))

    first.assert_called_once()
    second.assert_not_called()


def test_handlers_isolated_between_instances(event_factory, mock_handler) -> None:
    first_dispatcher = EventDispatcher()
    second_dispatcher = EventDispatcher()
    event = event_factory(event_type="instance.isolation")

    first_dispatcher.register_handler("instance.isolation", mock_handler)
    second_dispatcher.dispatch(event)

    mock_handler.assert_not_called()

    first_dispatcher.shutdown_executor(wait=False)
    second_dispatcher.shutdown_executor(wait=False)
