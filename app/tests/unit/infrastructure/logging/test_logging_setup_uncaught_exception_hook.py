"""Unit tests for the uncaught-exception hook installed by the configuration phase.

The production pipeline is forced on with its root handler writing to a buffer, and
the hook is invoked directly. A real traceback is built by raising and catching.
"""

import io
import json
import logging
import sys

import pytest

from infrastructure.logging import setup as logging_setup
from infrastructure.logging.settings import LoggingSettings
from infrastructure.logging.setup import configure_logging, install_uncaught_exception_hook


class _AlreadyLogged(Exception):
    pass


@pytest.fixture
def production_stream(monkeypatch, process_logging_state) -> io.StringIO:
    """The real production pipeline writing to a buffer, with the pytest guard switched off."""
    monkeypatch.setattr(logging_setup, "_is_test_environment", lambda: False)
    configure_logging("production", LoggingSettings())
    stream = io.StringIO()
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.setStream(stream)
    return stream


def _raise_and_capture(error: BaseException) -> tuple[type[BaseException], BaseException, object]:
    try:
        raise error
    except BaseException as caught:
        return type(caught), caught, caught.__traceback__


@pytest.mark.unit
def test_hook_logs_one_critical_json_line_holding_the_traceback(production_stream):
    """An exception reaching sys.excepthook is one CRITICAL uncaught_exception object with the traceback in exception."""
    install_uncaught_exception_hook(reported=(_AlreadyLogged,))

    sys.excepthook(*_raise_and_capture(RuntimeError("boom")))

    lines = production_stream.getvalue().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "uncaught_exception"
    assert record["level"] == "critical"
    assert "RuntimeError: boom" in record["exception"]
    assert "Traceback (most recent call last)" in record["exception"]


@pytest.mark.unit
def test_hook_does_not_log_a_type_already_reported(production_stream):
    """An exception type the caller already logged is not logged a second time."""
    install_uncaught_exception_hook(reported=(_AlreadyLogged,))

    sys.excepthook(*_raise_and_capture(_AlreadyLogged("seen")))

    assert production_stream.getvalue() == ""


@pytest.mark.unit
def test_hook_delegates_keyboard_interrupt_to_the_default_hook(production_stream, monkeypatch):
    """Ctrl-C keeps the interpreter's default handling and produces no log line."""
    delegated: list[type[BaseException]] = []
    monkeypatch.setattr(sys, "__excepthook__", lambda exc_type, exc, tb: delegated.append(exc_type))
    install_uncaught_exception_hook(reported=())

    sys.excepthook(*_raise_and_capture(KeyboardInterrupt()))

    assert delegated == [KeyboardInterrupt]
    assert production_stream.getvalue() == ""


@pytest.mark.unit
def test_hook_is_not_installed_under_pytest(process_logging_state):
    """Under pytest installing the hook leaves sys.excepthook as it was."""
    before = sys.excepthook

    install_uncaught_exception_hook(reported=())

    assert sys.excepthook is before
