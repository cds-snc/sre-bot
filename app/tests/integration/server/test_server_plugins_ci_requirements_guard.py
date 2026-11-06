"""Guard that the ci configuration switches off every plugin that states a requirement.

CI configures no vendor tenant or token, so an enabled plugin whose ``register_requirements``
returns a requirement would abort every CI boot; one returning none (the generator's
template) boots anywhere. Every installed entry point is loaded on a throwaway pluggy
manager (none blocked) and each hookimpl is called to find the plugins that state one;
the plugin tables of base.toml and ci.toml are read straight from the files and
merged key by key, as the loader does, so the pytest-env pin of
[plugins.incident_response] cannot hide a missing switch-off in ci.toml.
"""

import tomllib

import pluggy
import pytest

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from server.configuration.loader import CONFIG_DIR

pytestmark = pytest.mark.integration


def _plugins_stating_requirements() -> set[str]:
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    pm.load_setuptools_entrypoints(PLUGIN_NAMESPACE)
    return {impl.plugin_name for impl in pm.hook.register_requirements.get_hookimpls() if impl.function()}


def _ci_enablement() -> dict[str, bool]:
    enabled: dict[str, bool] = {}
    for name in ("base.toml", "ci.toml"):
        areas = tomllib.loads((CONFIG_DIR / name).read_text(encoding="utf-8")).get("plugins", {})
        for keys in areas.values():
            enabled.update(keys)
    return enabled


def test_ci_files_switch_off_every_plugin_that_states_a_requirement() -> None:
    stating = _plugins_stating_requirements()
    enabled = _ci_enablement()

    assert {"incident.response", "incident.scribe", "oncall_sync", "rant", "user_rotations"} <= stating
    assert sorted(name for name in stating if enabled.get(name, False)) == []
