"""Unit tests for packages.access.request package initialization behavior."""

import importlib

import pytest

from infrastructure.events import clear_handlers, get_handlers_for_event
from packages.access.common.events import SYNC_COMPLETED, SYNC_FAILED


def _reload_request_package():
    module = importlib.import_module("packages.access.request")
    return importlib.reload(module)


@pytest.mark.unit
def test_request_package_import_has_no_event_registration_side_effects():
    clear_handlers()

    _reload_request_package()

    assert get_handlers_for_event(SYNC_COMPLETED) == []
    assert get_handlers_for_event(SYNC_FAILED) == []


@pytest.mark.unit
def test_request_startup_warmup_registers_handlers_and_warms_runtime_config(
    monkeypatch,
):
    clear_handlers()
    request_pkg = _reload_request_package()

    runtime_config_called = False
    provider_warm_called = False

    def _runtime_config() -> object:
        nonlocal runtime_config_called
        runtime_config_called = True
        return object()

    class _Settings:
        enabled = True
        manager_group_slug = "sg-managers"
        fallback_approver_slug = "sg-org-admins"
        min_approver_count = 1
        request_ttl_hours = 72

    def _warm_provider() -> object:
        nonlocal provider_warm_called
        provider_warm_called = True
        return object()

    monkeypatch.setattr(
        request_pkg, "get_access_runtime_config", _runtime_config, raising=False
    )
    monkeypatch.setattr(request_pkg, "get_access_request_settings", lambda: _Settings())
    monkeypatch.setattr(request_pkg, "get_access_request_service", _warm_provider)

    request_pkg.startup_warmup(
        logger=type(
            "L",
            (),
            {
                "info": lambda *a, **k: None,
                "warning": lambda *a, **k: None,
                "error": lambda *a, **k: None,
            },
        )()
    )

    assert runtime_config_called is True
    assert provider_warm_called is True
    assert len(get_handlers_for_event(SYNC_COMPLETED)) == 1
    assert len(get_handlers_for_event(SYNC_FAILED)) == 1


@pytest.mark.unit
def test_request_startup_warmup_registers_handlers_via_event_dispatcher(monkeypatch):
    request_pkg = _reload_request_package()

    class _Settings:
        enabled = True
        manager_group_slug = "sg-managers"
        fallback_approver_slug = "sg-org-admins"
        min_approver_count = 1
        request_ttl_hours = 72

    class _Dispatcher:
        def __init__(self) -> None:
            self._handlers: dict[str, list[object]] = {}

        def get_handlers_for_event(self, event_type: str):
            return self._handlers.get(event_type, [])

        def register_handler(self, event_type: str):
            def _decorator(handler):
                self._handlers.setdefault(event_type, []).append(handler)
                return handler

            return _decorator

    dispatcher = _Dispatcher()

    monkeypatch.setattr(request_pkg, "get_access_runtime_config", lambda: object())
    monkeypatch.setattr(request_pkg, "get_access_request_settings", lambda: _Settings())
    monkeypatch.setattr(request_pkg, "get_access_request_service", lambda: object())
    monkeypatch.setattr(request_pkg, "get_event_dispatcher", lambda: dispatcher)

    # Enforce DI boundary: package code must not call module-level registration.
    monkeypatch.setattr(
        request_pkg,
        "register_event_handler",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("direct register_event_handler usage is forbidden")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        request_pkg,
        "get_handlers_for_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("direct get_handlers_for_event usage is forbidden")
        ),
        raising=False,
    )

    request_pkg.startup_warmup(
        logger=type(
            "L",
            (),
            {
                "info": lambda *a, **k: None,
                "warning": lambda *a, **k: None,
                "error": lambda *a, **k: None,
            },
        )()
    )

    assert len(dispatcher.get_handlers_for_event(SYNC_COMPLETED)) == 1
    assert len(dispatcher.get_handlers_for_event(SYNC_FAILED)) == 1


@pytest.mark.unit
def test_request_startup_warmup_raises_when_enabled_runtime_config_is_invalid(
    monkeypatch,
):
    request_pkg = _reload_request_package()

    class _Settings:
        enabled = True
        manager_group_slug = "sg-managers"
        fallback_approver_slug = "sg-org-admins"
        min_approver_count = 1
        request_ttl_hours = 72

    monkeypatch.setattr(request_pkg, "get_access_request_settings", lambda: _Settings())
    monkeypatch.setattr(
        request_pkg,
        "get_access_runtime_config",
        lambda: (_ for _ in ()).throw(RuntimeError("invalid runtime config")),
        raising=False,
    )

    with pytest.raises(RuntimeError, match="invalid runtime config"):
        request_pkg.startup_warmup(
            logger=type(
                "L",
                (),
                {
                    "info": lambda *a, **k: None,
                    "warning": lambda *a, **k: None,
                    "error": lambda *a, **k: None,
                },
            )()
        )
