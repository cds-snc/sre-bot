"""Content loading at plugin-loading time: catalogue registration, boot failure and plugin enablement.

A real pluggy PluginManager holds module-like plugins; the registry is a real svcs registry.
Content files are real files under ``tmp_path``.
"""

from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pluggy
import pytest
import structlog
import svcs
from structlog.testing import capture_logs

from contracts.content import ContentCatalogue, ContentKind, ContentKindRegistrar, ContentLoadError
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl
from infrastructure.content.settings import ContentSettings
from server.lifespan import load_provisioned_content
from tests.factories.content import GADGETS, WIDGETS, Widget, widget_text, write_item

pytestmark = pytest.mark.unit

SECRET = "s3cr3t-value-never-logged"


@pytest.fixture
def pm() -> pluggy.PluginManager:
    manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    manager.add_hookspecs(FeatureLifecycleSpecs)
    return manager


@pytest.fixture
def registry() -> Iterator[svcs.Registry]:
    with svcs.Registry() as registry:
        yield registry


def _plugin(kind: ContentKind) -> ModuleType:
    @hookimpl
    def register_content_kinds(registrar: ContentKindRegistrar) -> None:
        registrar.register(kind)

    module = ModuleType(f"plugin_{kind.name}")
    module.__dict__["register_content_kinds"] = register_content_kinds
    return module


def _load(pm: pluggy.PluginManager, registry: svcs.Registry, root: Path) -> None:
    load_provisioned_content(pm, registry, structlog.get_logger(), ContentSettings(root=root), Path("/unused"))


def test_a_plugins_kind_is_loaded_and_the_catalogue_resolves_from_the_registry(pm, registry, tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "first.yaml", widget_text("first", "One"))
    pm.register(_plugin(WIDGETS), name="probe")

    _load(pm, registry, tmp_path)

    catalogue = svcs.Container(registry).get(ContentCatalogue)
    assert dict(catalogue.items(WIDGETS)) == {"first": Widget("first", "One")}


def test_no_registered_kind_boots_unchanged_without_reading_the_root(pm, registry, tmp_path: Path) -> None:
    _load(pm, registry, tmp_path / "missing")

    assert dict(svcs.Container(registry).get(ContentCatalogue).items(WIDGETS)) == {}


def test_an_invalid_file_aborts_with_one_critical_event_naming_file_and_field_but_not_the_value(
    pm, registry, tmp_path: Path
) -> None:
    write_item(tmp_path, WIDGETS, "bad.yaml", f"kind: probe/widgets\nversion: 1\nid: bad\ntitle: [{SECRET}]\n")
    pm.register(_plugin(WIDGETS), name="probe")

    with capture_logs() as logs, pytest.raises(ContentLoadError):
        _load(pm, registry, tmp_path)

    events = [entry for entry in logs if entry["event"] == "content_load_failed"]
    assert len(events) == 1
    assert events[0]["log_level"] == "critical"
    assert (events[0]["kind"], events[0]["file"], events[0]["field"]) == ("probe/widgets", "probe/widgets/bad.yaml", "title")
    assert SECRET not in repr(events)
    with pytest.raises(svcs.exceptions.ServiceNotFoundError):
        svcs.Container(registry).get(ContentCatalogue)


def test_each_problem_is_one_critical_event(pm, registry, tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "a.yaml", "kind: [unclosed\n")
    write_item(tmp_path, WIDGETS, "b.yaml", "kind: [unclosed\n")
    pm.register(_plugin(WIDGETS), name="probe")

    with capture_logs() as logs, pytest.raises(ContentLoadError):
        _load(pm, registry, tmp_path)

    assert len([entry for entry in logs if entry["event"] == "content_load_failed"]) == 2


def test_a_disabled_plugins_hook_is_never_called_and_its_directory_never_read(pm, registry, tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "first.yaml", widget_text("first"))
    write_item(tmp_path, GADGETS, "broken.yaml", "not: [valid")
    pm.set_blocked("off")
    assert pm.register(_plugin(GADGETS), name="off") is None
    pm.register(_plugin(WIDGETS), name="on")

    _load(pm, registry, tmp_path)

    catalogue = svcs.Container(registry).get(ContentCatalogue)
    assert set(catalogue.items(WIDGETS)) == {"first"}
    assert dict(catalogue.items(GADGETS)) == {}
