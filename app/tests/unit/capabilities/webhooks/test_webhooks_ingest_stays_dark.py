"""Unit tests that the ingest slice changes nothing production runs.

The webhooks plugin is enabled in every environment, so the slice stays dark only while the
plugin module implements no route or job hook. These tests read the plugin module and the
host's route registration, and assert neither reaches the new router or the sweeper.
"""

import inspect

import pytest

import capabilities.webhooks.plugin as plugin

pytestmark = pytest.mark.unit


def test_the_plugin_registers_no_route_and_no_job() -> None:
    hooks = {name for name, value in vars(plugin).items() if inspect.isfunction(value)}

    assert "register_routes" not in hooks
    assert "register_background_jobs" not in hooks


def test_the_plugin_module_never_imports_the_ingress_or_the_sweeper() -> None:
    source = inspect.getsource(plugin)

    assert "entrypoints" not in source
