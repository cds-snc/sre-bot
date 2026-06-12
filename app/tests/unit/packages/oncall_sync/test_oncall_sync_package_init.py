"""Unit tests for ``packages.oncall_sync`` hookimpl wiring."""

import importlib
from datetime import timedelta

import pytest


def _reload_pkg():
    module = importlib.import_module("packages.oncall_sync")
    return importlib.reload(module)


class _Registry:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def register_interval(self, *, job_name, every, job) -> None:
        self.calls.append({"job_name": job_name, "every": every, "job": job})


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def info(self, event, **kw) -> None:
        self.events.append(("info", {"event": event, **kw}))

    def warning(self, event, **kw) -> None:
        self.events.append(("warning", {"event": event, **kw}))


@pytest.mark.unit
def test_register_background_jobs_with_rotations(monkeypatch) -> None:
    pkg = _reload_pkg()
    settings_mod = importlib.import_module("packages.oncall_sync.settings")
    monkeypatch.setattr(settings_mod, "get_oncall_rotations", lambda: [object()])

    registry = _Registry()
    pkg.register_background_jobs(registry=registry)

    assert len(registry.calls) == 1
    assert registry.calls[0]["job_name"] == "oncall_sync"
    assert registry.calls[0]["every"] == timedelta(minutes=5)
    assert callable(registry.calls[0]["job"])


@pytest.mark.unit
def test_register_background_jobs_noop_when_no_rotations(monkeypatch) -> None:
    pkg = _reload_pkg()
    settings_mod = importlib.import_module("packages.oncall_sync.settings")
    monkeypatch.setattr(settings_mod, "get_oncall_rotations", lambda: [])

    registry = _Registry()
    pkg.register_background_jobs(registry=registry)

    assert registry.calls == []


@pytest.mark.unit
def test_startup_warmup_logs_rotation_count(monkeypatch) -> None:
    pkg = _reload_pkg()
    settings_mod = importlib.import_module("packages.oncall_sync.settings")
    monkeypatch.setattr(
        settings_mod, "get_oncall_rotations", lambda: [object(), object()]
    )

    logger = _Logger()
    pkg.startup_warmup(logger=logger)

    loaded = next(
        evt
        for lvl, evt in logger.events
        if evt["event"] == "oncall_sync_settings_loaded"
    )
    assert loaded["rotation_count"] == 2
    assert loaded["sync_interval_seconds"] == 300


@pytest.mark.unit
def test_startup_warmup_warns_when_no_rotations(monkeypatch) -> None:
    pkg = _reload_pkg()
    settings_mod = importlib.import_module("packages.oncall_sync.settings")
    monkeypatch.setattr(settings_mod, "get_oncall_rotations", lambda: [])

    logger = _Logger()
    pkg.startup_warmup(logger=logger)

    assert any(
        lvl == "warning" and evt["event"] == "oncall_sync_no_rotations"
        for lvl, evt in logger.events
    )
