"""Unit tests for the per-plugin hook runner that attributes a boot failure to its plugin.

Two module-like plugins are registered on a real pluggy manager under entry-point
style names; structlog's ``capture_logs`` records the events. The runner must call
each plugin once with the hook's arguments, stop at the first plugin that raises,
re-raise its own exception unchanged, and log exactly one CRITICAL
``plugin_boot_failed`` naming that plugin, the phase, the error type and the
setting at fault, never the error text (a validation message can hold the value).
"""

from types import ModuleType

import pluggy
import pytest
import structlog
from pydantic import BaseModel, ValidationError
from structlog.testing import capture_logs

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl
from contracts.plugins.requirements import RequiredDependencyError
from server.plugins.boot import call_hook_per_plugin, log_plugin_boot_failed

pytestmark = pytest.mark.unit


class _Slice(BaseModel):
    channel_id: int


def _plugin(**hookimpls: object) -> ModuleType:
    """Return a module-like plugin object: pluggy keys plugins by identity, so they must be hashable."""
    plugin = ModuleType("fake_plugin")
    plugin.__dict__.update(hookimpls)
    return plugin


def _manager(**plugins: object) -> pluggy.PluginManager:
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    for name, plugin in plugins.items():
        pm.register(plugin, name=name)
    return pm


def _recording(calls: list[str], name: str) -> object:
    @hookimpl
    def startup_warmup(logger: object) -> None:
        calls.append(name)

    return _plugin(startup_warmup=startup_warmup)


def _raising(error: Exception) -> object:
    @hookimpl
    def register_requirements() -> None:
        raise error

    return _plugin(register_requirements=register_requirements)


def test_runner_calls_every_plugin_once_with_the_hook_arguments() -> None:
    calls: list[str] = []
    pm = _manager(first=_recording(calls, "first"), second=_recording(calls, "second"))

    call_hook_per_plugin(pm, "startup_warmup", structlog.get_logger(), logger=structlog.get_logger())

    assert sorted(calls) == ["first", "second"]


def test_runner_attributes_a_required_dependency_to_the_raising_plugin() -> None:
    error = RequiredDependencyError("openai.tenant")
    pm = _manager(quiet=_plugin(), needy=_raising(error))

    with capture_logs() as events, pytest.raises(RequiredDependencyError) as raised:
        call_hook_per_plugin(pm, "register_requirements", structlog.get_logger())

    assert raised.value is error
    assert [event for event in events if event["event"] == "plugin_boot_failed"] == [
        {
            "event": "plugin_boot_failed",
            "log_level": "critical",
            "plugin": "needy",
            "phase": "register_requirements",
            "error_type": "RequiredDependencyError",
            "setting": "openai.tenant",
        }
    ]


def test_runner_stops_at_the_first_plugin_that_raises() -> None:
    calls: list[str] = []

    @hookimpl
    def register_requirements() -> None:
        calls.append("later")

    pm = _manager(needy=_raising(RuntimeError("boom")), later=_plugin(register_requirements=register_requirements))

    with pytest.raises(RuntimeError, match="boom"):
        call_hook_per_plugin(pm, "register_requirements", structlog.get_logger())

    assert calls == []


def test_boot_failure_names_the_failing_settings_without_the_value() -> None:
    with pytest.raises(ValidationError) as raised:
        _Slice.model_validate({"channel_id": "not-a-number-s3cr3t"})

    with capture_logs() as events:
        log_plugin_boot_failed(structlog.get_logger(), plugin="rant", phase="startup_warmup", error=raised.value)

    (event,) = events
    assert event["setting"] == "_Slice.channel_id"
    assert event["error_type"] == "ValidationError"
    assert "s3cr3t" not in repr(event)


def test_boot_failure_without_a_setting_at_fault_logs_none() -> None:
    with capture_logs() as events:
        log_plugin_boot_failed(structlog.get_logger(), plugin="rant", phase="routes", error=RuntimeError("detail"))

    (event,) = events
    assert event["setting"] is None
    assert "detail" not in repr(event)
