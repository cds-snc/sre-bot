"""The incident Google adapter acts as the bot: no delegation subject, no credentials of its own.

Every Docs and Drive service the adapter builds goes through the Google Workspace
gateway factories with scopes only, so who the calls run as stays the gateway's
decision (decisions/workplace-systems.md; TASK-181 decides delegation). The
factories are replaced by recorders that fail on any argument but ``scopes``,
then each report operation and each Drive function runs once. A source scan
pins that no module under ``core/adapters`` imports Google's credential packages.
"""

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import IncidentCoreSettings
from features.incident.core.adapters import google_docs
from features.incident.core.api import ReportReference, SectionDraft

pytestmark = pytest.mark.unit

ADAPTERS_DIR = Path(google_docs.__file__).parent
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="D0REPORT")


class _ScopesOnly:
    """A gateway factory stand-in that records each call and refuses anything but ``scopes``."""

    def __init__(self, service: MagicMock) -> None:
        self.calls: list[dict[str, Any]] = []
        self._service = service

    def __call__(self, *args: Any, **kwargs: Any) -> MagicMock:
        assert not args, f"positional arguments {args!r}"
        assert set(kwargs) == {"scopes"}, f"called with {sorted(kwargs)}"
        self.calls.append(kwargs)
        return self._service


@pytest.fixture
def factories(monkeypatch: pytest.MonkeyPatch) -> list[_ScopesOnly]:
    docs = MagicMock()
    docs.documents.return_value.get.return_value.execute.return_value = {"revisionId": "r1", "body": {"content": []}}
    drive = MagicMock()
    drive.files.return_value.list.return_value.execute.return_value = {"files": []}
    drive.files.return_value.list_next.return_value = None
    drive.files.return_value.copy.return_value.execute.return_value = {"id": "D0NEW", "name": "n"}
    drive.files.return_value.create.return_value.execute.return_value = {"id": "F0NEW", "name": "n"}
    drive.files.return_value.get.return_value.execute.return_value = {"id": "D0REPORT", "name": "n", "parents": ["F0"]}
    drive.files.return_value.update.return_value.execute.return_value = {"id": "D0REPORT"}
    recorders = [_ScopesOnly(docs), _ScopesOnly(docs), _ScopesOnly(drive)]
    monkeypatch.setattr(google_docs, "get_docs_service", recorders[0])
    monkeypatch.setattr(google_docs.google_workspace_client, "get_docs_service", recorders[1])
    monkeypatch.setattr(google_docs.google_workspace_client, "get_drive_service", recorders[2])
    monkeypatch.setattr(
        google_docs, "get_incident_core_settings", lambda: IncidentCoreSettings(folder_id="F0", report_template_id="T0")
    )
    monkeypatch.setattr(
        google_docs, "get_google_workspace_settings", lambda: SimpleNamespace(tenant=SimpleNamespace(customer_id="C0GOOGLE"))
    )
    return recorders


def test_every_report_operation_builds_its_services_with_scopes_only(factories: list[_ScopesOnly]) -> None:
    report = google_docs.GoogleDocsIncidentReport()

    report.create_from_template("Incident")
    report.replace_placeholders(REPORT, {"a": "b"})
    report.read_sections(REPORT)
    report.write_draft_copy(REPORT, [SectionDraft("Summary", "x", True)], (), {})

    assert sum(len(factory.calls) for factory in factories) >= 4


def test_every_drive_function_builds_its_service_with_scopes_only(factories: list[_ScopesOnly]) -> None:
    google_docs.list_folder_files("F0")
    google_docs.list_child_folders("F0")
    google_docs.create_folder("name", "F0")
    google_docs.create_document_from_template("name", "F0", "T0")
    google_docs.find_document_by_channel_name("incident-1")
    google_docs.add_metadata("D0", "k", "v")
    google_docs.delete_metadata("D0", "k")
    google_docs.get_metadata("D0")

    assert len(factories[2].calls) >= 8


def test_no_core_adapter_imports_google_credential_packages() -> None:
    offenders: list[str] = []
    for path in sorted(ADAPTERS_DIR.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            offenders += [
                f"{path.name}: {name}" for name in names if name.split(".")[:2] in (["google", "oauth2"], ["google", "auth"])
            ]

    assert offenders == []
