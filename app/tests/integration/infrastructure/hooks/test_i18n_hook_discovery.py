"""Test plugin discovery and i18n hook invocation."""

from infrastructure.i18n.resources import I18nResourceRegistry
from infrastructure.plugins.base import auto_discover_plugins
from infrastructure.plugins.manager import get_plugin_manager


def test_plugin_discovery_finds_geolocate() -> None:
    """Test that plugin discovery system finds geolocate hookimpls."""
    pm = get_plugin_manager()

    # Auto-discover plugins (same as in lifespan)

    auto_discover_plugins(pm, base_paths=["packages", "modules"])

    plugins = pm.get_plugins()
    assert len(plugins) > 0, "No plugins discovered"

    # Check if geolocate is among discovered plugins.
    # Plugins registered by auto_discover_plugins are Python module objects;
    # use p.__name__ (the module's dotted name) not type(p).__module__ (which
    # always returns 'builtins' for ModuleType objects).
    plugin_names = [getattr(p, "__name__", "") for p in plugins]
    geolocate_found = any("geolocate" in name for name in plugin_names)
    assert geolocate_found, f"geolocate not found in plugins: {plugin_names}"


def test_i18n_hook_registers_geolocate_resources() -> None:
    """Test that register_i18n_resources hook is called and geolocate registers."""
    pm = get_plugin_manager()

    auto_discover_plugins(pm, base_paths=["packages", "modules"])

    # Call the hook
    registry = I18nResourceRegistry()
    pm.hook.register_i18n_resources(registry=registry)

    # Verify geolocate registered its resources
    specs = registry.list_specs()
    geolocate_specs = [s for s in specs if "geolocate" in s.owner.lower()]

    assert len(geolocate_specs) > 0, f"geolocate resources not registered. All specs: {specs}"

    # Verify geolocate spec details
    geolocate_spec = geolocate_specs[0]
    assert geolocate_spec.owner == "packages.geolocate"
    assert geolocate_spec.domain == "geolocate"
    assert "locales" in geolocate_spec.path
    assert geolocate_spec.required is False
