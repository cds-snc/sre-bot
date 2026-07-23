"""Unit tests for packages.access.sync package initialization behavior."""

import importlib

import pytest

from infrastructure.events import get_event_dispatcher
from packages.access.common.events import REQUEST_APPROVED


def _reload_sync_package():
    module = importlib.import_module("packages.access.sync")
    return importlib.reload(module)


@pytest.mark.unit
def test_sync_package_import_has_no_event_registration_side_effects():
    get_event_dispatcher.cache_clear()

    _reload_sync_package()
    dispatcher = get_event_dispatcher()

    assert dispatcher.get_handler_count(REQUEST_APPROVED) == 0


@pytest.mark.unit
def test_sync_startup_warmup_registers_handlers_and_warms_runtime_config(monkeypatch):
    get_event_dispatcher.cache_clear()
    sync_pkg = _reload_sync_package()

    runtime_config_called = False
    provider_warm_called = False

    def _runtime_config() -> object:
        nonlocal runtime_config_called
        runtime_config_called = True
        return object()

    class _Settings:
        enabled = True
        reconciliation_enabled = False
        reconciliation_schedule = "03:00"

    def _warm_provider() -> object:
        nonlocal provider_warm_called
        provider_warm_called = True
        return object()

    monkeypatch.setattr(sync_pkg, "get_access_runtime_config", _runtime_config, raising=False)
    monkeypatch.setattr(sync_pkg, "get_access_sync_settings", lambda: _Settings())
    monkeypatch.setattr(sync_pkg, "get_access_sync_coordinator", _warm_provider)

    sync_pkg.startup_warmup(
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
    dispatcher = get_event_dispatcher()
    assert dispatcher.get_handler_count(REQUEST_APPROVED) == 1


@pytest.mark.unit
def test_sync_startup_warmup_registers_handlers_via_event_dispatcher(monkeypatch):
    sync_pkg = _reload_sync_package()

    class _Settings:
        enabled = True
        reconciliation_enabled = False
        reconciliation_schedule = "03:00"

    class _Dispatcher:
        def __init__(self) -> None:
            self._handlers: dict[str, list[object]] = {}

        def get_handler_count(self, event_type: str) -> int:
            return len(self._handlers.get(event_type, []))

        def register_handler(self, event_type: str, handler) -> None:
            self._handlers.setdefault(event_type, []).append(handler)

    dispatcher = _Dispatcher()

    monkeypatch.setattr(sync_pkg, "get_access_runtime_config", lambda: object())
    monkeypatch.setattr(sync_pkg, "get_access_sync_settings", lambda: _Settings())
    monkeypatch.setattr(sync_pkg, "get_access_sync_coordinator", lambda: object())
    monkeypatch.setattr(sync_pkg, "get_event_dispatcher", lambda: dispatcher)

    # Enforce DI boundary: package code must not call module-level registration.
    monkeypatch.setattr(
        sync_pkg,
        "register_event_handler",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("direct register_event_handler usage is forbidden")),
        raising=False,
    )
    monkeypatch.setattr(
        sync_pkg,
        "get_handlers_for_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("direct get_handlers_for_event usage is forbidden")),
        raising=False,
    )

    sync_pkg.startup_warmup(
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

    assert dispatcher.get_handler_count(REQUEST_APPROVED) == 1


@pytest.mark.unit
def test_sync_startup_warmup_raises_when_enabled_runtime_config_is_invalid(monkeypatch):
    sync_pkg = _reload_sync_package()

    class _Settings:
        enabled = True
        reconciliation_enabled = False
        reconciliation_schedule = "03:00"

    monkeypatch.setattr(sync_pkg, "get_access_sync_settings", lambda: _Settings())
    monkeypatch.setattr(
        sync_pkg,
        "get_access_runtime_config",
        lambda: (_ for _ in ()).throw(RuntimeError("invalid runtime config")),
        raising=False,
    )

    with pytest.raises(RuntimeError, match="invalid runtime config"):
        sync_pkg.startup_warmup(
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


@pytest.mark.unit
def test_sync_register_background_job_registers_reconciliation_when_enabled(
    monkeypatch,
) -> None:
    sync_pkg = _reload_sync_package()

    class _Settings:
        enabled = True
        reconciliation_enabled = True
        reconciliation_schedule = "03:30"

    registrations: list[dict[str, object]] = []

    class _BackgroundJobRegistry:
        def register(self, *, job_name: str, schedule: str, job) -> None:
            registrations.append({"job_name": job_name, "schedule": schedule, "job": job})

    monkeypatch.setattr(sync_pkg, "get_access_sync_settings", lambda: _Settings())

    sync_pkg.register_background_jobs(registry=_BackgroundJobRegistry())

    assert len(registrations) == 1
    assert registrations[0]["job_name"] == "access_sync_reconciliation"
    assert registrations[0]["schedule"] == "03:30"
    assert callable(registrations[0]["job"])


@pytest.mark.unit
@pytest.mark.parametrize(
    ("enabled", "reconciliation_enabled"),
    [(False, True), (True, False), (False, False)],
)
def test_sync_register_background_job_skips_registration_when_disabled(
    monkeypatch,
    enabled: bool,
    reconciliation_enabled: bool,
) -> None:
    sync_pkg = _reload_sync_package()

    class _Settings:
        reconciliation_schedule = "03:30"

    _Settings.enabled = enabled
    _Settings.reconciliation_enabled = reconciliation_enabled

    registrations: list[dict[str, object]] = []

    class _BackgroundJobRegistry:
        def register(self, *, job_name: str, schedule: str, job) -> None:
            registrations.append({"job_name": job_name, "schedule": schedule, "job": job})

    monkeypatch.setattr(sync_pkg, "get_access_sync_settings", lambda: _Settings())

    sync_pkg.register_background_jobs(registry=_BackgroundJobRegistry())

    assert registrations == []
