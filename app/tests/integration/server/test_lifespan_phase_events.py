"""Integration tests for the one INFO event each lifespan phase logs.

Each phase function runs with a real structlog logger under capture_logs and stubbed
services, so the observable result is the level, name and counts of every event. The
started and per-item lines are debug; the phase's single completion event is info and
carries the phase name and the counts that prove it completed.
"""

from unittest.mock import MagicMock

import pytest
import structlog
from structlog.testing import capture_logs

from server import lifespan as lifespan_module

pytestmark = pytest.mark.integration


def _by_level(entries: list[dict[str, object]], level: str) -> list[dict[str, object]]:
    return [entry for entry in entries if entry["log_level"] == level]


def _names(entries: list[dict[str, object]]) -> list[object]:
    return [entry["event"] for entry in entries]


def _security_settings(issuers: dict[str, object]) -> MagicMock:
    settings = MagicMock()
    settings.issuer_config = issuers
    return settings


def test_security_phase_logs_one_info_event_with_the_issuer_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured issuer list yields the warmup and one info event carrying issuer_count; the start is debug."""
    manager = MagicMock()
    monkeypatch.setattr(lifespan_module, "get_jwks_manager", lambda: manager)

    with capture_logs() as entries:
        lifespan_module._initialize_security_services(_security_settings({"a": 1, "b": 2}), structlog.stdlib.get_logger())

    manager.warmup.assert_called_once_with()
    assert _names(_by_level(entries, "info")) == ["security_services_initialized"]
    assert _by_level(entries, "info")[0]["issuer_count"] == 2
    assert _by_level(entries, "info")[0]["phase"] == "security"
    assert _names(_by_level(entries, "debug")) == ["security_services_initialization_started"]


def test_security_phase_with_no_issuer_still_logs_its_info_event_with_a_zero_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no issuer configured the warmup is skipped and the phase still logs issuer_count=0."""
    manager = MagicMock()
    monkeypatch.setattr(lifespan_module, "get_jwks_manager", lambda: manager)

    with capture_logs() as entries:
        lifespan_module._initialize_security_services(_security_settings({}), structlog.stdlib.get_logger())

    manager.warmup.assert_not_called()
    info = _by_level(entries, "info")
    assert _names(info) == ["security_services_initialized"]
    assert info[0]["issuer_count"] == 0


@pytest.mark.parametrize("warmup_required", [True, False])
def test_directory_phase_logs_one_info_event_naming_whether_it_warmed_up(
    monkeypatch: pytest.MonkeyPatch, warmup_required: bool
) -> None:
    """The directory phase logs directory_provider_initialized once, with warmup telling if the remote warmup ran."""
    provider = MagicMock()
    provider.warmup.return_value = MagicMock(is_success=True, message="ok")
    monkeypatch.setattr(lifespan_module, "get_directory_provider", lambda: provider)
    settings = MagicMock()
    settings.require_startup_warmup = warmup_required

    with capture_logs() as entries:
        lifespan_module._initialize_directory_provider(MagicMock(), settings, structlog.stdlib.get_logger())

    info = _by_level(entries, "info")
    assert _names(info) == ["directory_provider_initialized"]
    assert info[0]["warmup"] is warmup_required
    assert info[0]["phase"] == "directory"
    assert "directory_provider_initialization_started" in _names(_by_level(entries, "debug"))


def test_i18n_phase_logs_one_info_event_with_resource_and_locale_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Collection and health are debug; i18n_initialized is the single info event, counting resources and locales."""
    service = MagicMock()
    service.initialize.return_value = MagicMock(is_success=True)
    service.health_check.return_value = MagicMock(is_success=True)
    service.translator.get_available_locales.return_value = ["en", "fr"]
    monkeypatch.setattr(lifespan_module, "get_translation_service", lambda: service)
    monkeypatch.setattr(lifespan_module, "call_hook_per_plugin", lambda *args, **kwargs: {})

    with capture_logs() as entries:
        lifespan_module._initialize_translation_service(MagicMock(), structlog.stdlib.get_logger())

    info = _by_level(entries, "info")
    assert _names(info) == ["i18n_initialized"]
    assert info[0]["locale_count"] == 2
    assert info[0]["resource_count"] == len(service.initialize.call_args.kwargs["resources"])
    assert info[0]["phase"] == "i18n"
    assert "i18n_resources_collected" in _names(_by_level(entries, "debug"))


def test_i18n_phase_failure_is_still_logged_as_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed initialization logs its error and raises, and no i18n_initialized event is logged."""
    service = MagicMock()
    service.initialize.return_value = MagicMock(is_success=False, message="missing catalog")
    monkeypatch.setattr(lifespan_module, "get_translation_service", lambda: service)
    monkeypatch.setattr(lifespan_module, "call_hook_per_plugin", lambda *args, **kwargs: {})

    with capture_logs() as entries, pytest.raises(RuntimeError, match="i18n initialization failed"):
        lifespan_module._initialize_translation_service(MagicMock(), structlog.stdlib.get_logger())

    assert "i18n_initialization_failed" in _names(_by_level(entries, "error"))
    assert "i18n_initialized" not in _names(entries)


def test_legacy_registration_lines_are_debug() -> None:
    """The legacy handler and command registration lines are debug; the registration phase event comes from the manager."""
    registrar = MagicMock()
    bot = MagicMock()

    with capture_logs() as entries:
        logger = structlog.stdlib.get_logger()
        lifespan_module._register_legacy_slack_commands(registrar, logger)
        lifespan_module._register_legacy_handlers(bot, logger)

    assert _by_level(entries, "info") == []
    assert {"legacy_slack_commands_registered", "registering_legacy_handlers"} <= set(_names(_by_level(entries, "debug")))
