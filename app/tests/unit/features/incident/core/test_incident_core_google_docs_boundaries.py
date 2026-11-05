from pathlib import Path

from features.incident.core.adapters import google_docs

APP_ROOT = Path(__file__).resolve().parents[5]
ADAPTER_PATH = APP_ROOT / "features" / "incident" / "core" / "adapters" / "google_docs.py"


def test_incident_google_docs_adapter_exposes_extract_google_doc_id():
    assert callable(google_docs.extract_google_doc_id)


def test_extract_google_doc_id_is_not_left_in_google_workspace_sources():
    package_dir = APP_ROOT / "integrations" / "google_workspace"
    offenders = [path.name for path in package_dir.glob("*.py") if "extract_google_doc_id" in path.read_text(encoding="utf-8")]
    assert offenders == []


def test_incident_google_docs_adapter_exists_and_has_no_hookimpls():
    assert ADAPTER_PATH.is_file()
    assert "hookimpl" not in ADAPTER_PATH.read_text(encoding="utf-8")


def test_module_incident_sources_do_not_import_google_drive_directly():
    incident_dir = APP_ROOT / "modules" / "incident"
    jobs_dir = APP_ROOT / "jobs"
    offenders = []
    for base in (incident_dir, jobs_dir):
        for path in base.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "integrations.google_workspace import google_drive" in text:
                offenders.append(str(path.relative_to(APP_ROOT)))
    assert offenders == []


def test_incident_google_docs_adapter_imports_client_not_legacy_google_drive():
    """The adapter accesses the SDK through integrations.google_workspace.client, not the legacy google_drive module."""
    adapter_text = ADAPTER_PATH.read_text(encoding="utf-8")

    # Must NOT import the legacy google_drive module
    assert "integrations.google_workspace import google_drive" not in adapter_text

    # Must import the client module (the correct Path B boundary)
    assert "from integrations.google_workspace import client" in adapter_text
