"""Unit tests for the log level of the webhook pattern registration lines.

Pattern registration is per-item detail, so each pattern line is debug, while the
notification module's one completion line stays info. The register functions are stubbed
so the module-level pattern registries are untouched, and structlog's capture_logs
records the events.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from structlog.testing import capture_logs

from modules.webhooks import aws_sns_notification, simple_text

pytestmark = pytest.mark.unit


def test_simple_text_pattern_registration_logs_at_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each discovered simple-text pattern is logged at debug and nothing at info."""
    monkeypatch.setattr(simple_text, "register_pattern", MagicMock())

    with capture_logs() as entries:
        simple_text.init_pattern_handlers()

    registered = [entry for entry in entries if entry["event"] == "registered_pattern"]
    assert registered
    assert {entry["log_level"] for entry in registered} == {"debug"}
    assert [entry for entry in entries if entry["log_level"] == "info"] == []


def test_notification_pattern_registration_logs_at_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registered notification pattern and a module with no handler are debug lines."""
    monkeypatch.setattr(aws_sns_notification, "register_notification_pattern", MagicMock())
    with_handler = SimpleNamespace(PROBE_HANDLER=SimpleNamespace(name="probe"))

    with capture_logs() as entries:
        aws_sns_notification._register_handlers_from_module(with_handler, "probe_module")
        aws_sns_notification._register_handlers_from_module(SimpleNamespace(), "empty_module")

    assert [(entry["event"], entry["log_level"]) for entry in entries] == [
        ("registered_notification_pattern", "debug"),
        ("no_handlers_found_in_module", "debug"),
    ]


def test_notification_initialization_complete_stays_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """The notification module keeps its one summary line at info."""
    monkeypatch.setattr(aws_sns_notification, "_load_pattern_module", lambda mod_name, fname: (1, 0))

    with capture_logs() as entries:
        aws_sns_notification.init_notification_handlers()

    summary = [entry for entry in entries if entry["event"] == "notification_handlers_initialization_complete"]
    assert [entry["log_level"] for entry in summary] == ["info"]
