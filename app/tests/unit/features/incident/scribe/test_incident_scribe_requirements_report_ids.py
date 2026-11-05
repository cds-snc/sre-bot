"""The scribe plugin cannot boot without the incident document ids it drafts from.

scribe is registered on a fresh plugin manager under its entry-point name and the
host resolves its declarations. Every tenant is configured (the OpenAI slice and
the configured-systems read are stand-ins), and the built [incident_core] slice is
a real ``IncidentCoreSettings`` with one id left empty, as the configuration phase
builds it from the environment. Boot must stop with one CRITICAL
``plugin_boot_failed`` event naming exactly that key, and no value is logged.
"""

from collections.abc import Mapping
from types import SimpleNamespace

import pluggy
import pytest
import structlog
from structlog.testing import capture_logs

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from features.incident import scribe
from features.incident.common.settings import IncidentCoreSettings
from server.plugins import requirements as host
from server.plugins.requirements import PluginRequirementsUnmetError, resolve_requirements

pytestmark = pytest.mark.unit


class _AllSystems(ConfiguredSystems):
    def tenants(self) -> Mapping[WorkplaceSystem, str]:
        return {WorkplaceSystem.SLACK: "T0SLACK", WorkplaceSystem.GOOGLE: "C0GOOGLE"}


def _boot(monkeypatch: pytest.MonkeyPatch, settings: IncidentCoreSettings) -> None:
    monkeypatch.setattr(host, "SETTINGS_SLICES", {"openai": lambda: SimpleNamespace(tenant=SimpleNamespace(api_key="k"))})
    monkeypatch.setattr(host, "built_slices", lambda: (settings,))
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    pm.register(scribe, name="incident.scribe")
    resolve_requirements(pm, structlog.get_logger(), _AllSystems())


@pytest.mark.parametrize(
    ("configured", "key"),
    [
        pytest.param({"folder_id": "", "report_template_id": "T0TEMPLATE"}, "incident_core.folder_id", id="folder"),
        pytest.param({"folder_id": "F0INCIDENTS", "report_template_id": ""}, "incident_core.report_template_id", id="template"),
    ],
)
def test_an_empty_document_id_stops_boot_with_one_event_naming_the_key(
    monkeypatch: pytest.MonkeyPatch, configured: dict[str, str], key: str
) -> None:
    with capture_logs() as events, pytest.raises(PluginRequirementsUnmetError) as raised:
        _boot(monkeypatch, IncidentCoreSettings(**configured))

    failures = [event for event in events if event["event"] == "plugin_boot_failed"]
    assert [(event["plugin"], event["setting"], event["log_level"]) for event in failures] == [
        ("incident.scribe", key, "critical")
    ]
    assert [failure.setting for failure in raised.value.failures] == [key]
    assert all(value not in str(failures) for value in configured.values() if value)


def test_both_document_ids_set_boot_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    with capture_logs() as events:
        _boot(monkeypatch, IncidentCoreSettings(folder_id="F0INCIDENTS", report_template_id="T0TEMPLATE"))

    assert [event for event in events if event["event"] == "plugin_boot_failed"] == []
