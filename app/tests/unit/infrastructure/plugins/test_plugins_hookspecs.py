"""Unit tests for infrastructure.plugins.specs.FeatureLifecycleSpecs.

Aim: exercise the module surface to ensure the public contract is stable
and the hookspecs are exposed to pluggy's PluginManager.
"""

import inspect

import pluggy
import pytest

from contracts.slack.registrar import SlackCommandRegistrar
from infrastructure.plugins import specs
from infrastructure.plugins.specs import FeatureLifecycleSpecs, hookspec

EXPECTED_HOOKS = [
    "register_slack_commands",
    "register_routes",
    "register_i18n_resources",
    "register_event_handlers",
    "register_background_jobs",
    "startup_warmup",
]


EXPECTED_PARAMS = {
    "register_slack_commands": ["self", "registrar"],
    "register_routes": ["self", "app"],
    "register_i18n_resources": ["self", "registry"],
    "register_event_handlers": ["self", "dispatcher"],
    "register_background_jobs": ["self", "registry"],
    "startup_warmup": ["self", "logger"],
}

pytestmark = pytest.mark.unit


def test_module_docstring_and_hookspec_marker_callable() -> None:
    # Importing the module should expose a useful docstring
    assert specs.__doc__ is not None
    assert "Hook specifications" in specs.__doc__

    # The module exposes a pluggy hookspec marker and it is callable
    assert callable(hookspec)

    # Applying the hookspec marker to a function returns the function
    def _dummy() -> None:
        """Dummy function"""

    decorated = hookspec(_dummy)
    assert decorated is _dummy


def test_feature_lifecycle_specs_define_expected_hooks_and_docs() -> None:
    # The FeatureLifecycleSpecs class should define the expected hook names
    for name in EXPECTED_HOOKS:
        assert hasattr(FeatureLifecycleSpecs, name), f"Missing hook: {name}"
        attr = getattr(FeatureLifecycleSpecs, name)
        assert callable(attr)
        # Ensure each hook has a non-trivial docstring
        assert attr.__doc__ and len(attr.__doc__.strip()) > 10


def test_feature_lifecycle_specs_method_signatures() -> None:
    # Verify each method has the expected parameter names (including self)
    for name, expected_params in EXPECTED_PARAMS.items():
        func = getattr(FeatureLifecycleSpecs, name)
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        assert params == expected_params, f"{name} params: {params} != {expected_params}"


def test_slack_hookspecs_expose_no_sdk_runtime_object() -> None:
    # Features register through the registrar Protocol; no hookspec hands out the Bolt app.
    assert not hasattr(FeatureLifecycleSpecs, "register_slack_listeners")
    annotation = inspect.signature(FeatureLifecycleSpecs.register_slack_commands).parameters["registrar"].annotation
    assert annotation is SlackCommandRegistrar
    assert not any(name in vars(specs) for name in ("AsyncApp", "App", "SlackPlatformProvider"))


def test_plugin_manager_exposes_hooks_after_adding_specs() -> None:
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(FeatureLifecycleSpecs)

    for name in EXPECTED_HOOKS:
        hook = getattr(pm.hook, name, None)
        assert hook is not None, f"PluginManager.hook missing {name}"
        assert callable(hook)
