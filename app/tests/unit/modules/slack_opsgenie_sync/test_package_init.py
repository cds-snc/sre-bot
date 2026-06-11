"""Unit tests for the slack_opsgenie_sync hookimpl wiring."""

import importlib
from datetime import timedelta

import pytest


def _reload_pkg():
    module = importlib.import_module("modules.slack_opsgenie_sync")
    return importlib.reload(module)


class _Registry:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def register_interval(self, *, job_name: str, every: timedelta, job) -> None:
        self.calls.append({"job_name": job_name, "every": every, "job": job})


class _Settings:
    def __init__(self, *, rotations: list) -> None:
        self.rotations = rotations


@pytest.mark.unit
def test_register_background_jobs_when_rotations_configured(monkeypatch) -> None:
    pkg = _reload_pkg()
    settings_mod = importlib.import_module(
        "infrastructure.configuration.features.slack_opsgenie_sync"
    )
    monkeypatch.setattr(
        settings_mod,
        "get_slack_opsgenie_sync_settings",
        lambda: _Settings(rotations=[object()]),
    )

    registry = _Registry()
    pkg.register_background_jobs(registry=registry)

    assert len(registry.calls) == 1
    assert registry.calls[0]["job_name"] == "slack_opsgenie_sync"
    assert registry.calls[0]["every"] == timedelta(minutes=5)
    assert callable(registry.calls[0]["job"])


@pytest.mark.unit
def test_register_background_jobs_noop_when_no_rotations(monkeypatch) -> None:
    pkg = _reload_pkg()
    settings_mod = importlib.import_module(
        "infrastructure.configuration.features.slack_opsgenie_sync"
    )
    monkeypatch.setattr(
        settings_mod,
        "get_slack_opsgenie_sync_settings",
        lambda: _Settings(rotations=[]),
    )

    registry = _Registry()
    pkg.register_background_jobs(registry=registry)

    assert registry.calls == []


@pytest.mark.unit
def test_startup_warmup_logs_settings(monkeypatch) -> None:
    pkg = _reload_pkg()
    settings_mod = importlib.import_module(
        "infrastructure.configuration.features.slack_opsgenie_sync"
    )
    monkeypatch.setattr(
        settings_mod,
        "get_slack_opsgenie_sync_settings",
        lambda: _Settings(rotations=[object(), object()]),
    )

    logged: list[tuple] = []

    class _Logger:
        def info(self, *args, **kwargs) -> None:
            logged.append((args, kwargs))

    pkg.startup_warmup(logger=_Logger())

    assert len(logged) == 1
    args, kwargs = logged[0]
    assert args[0] == "slack_opsgenie_sync_settings_loaded"
    assert kwargs["rotation_count"] == 2
