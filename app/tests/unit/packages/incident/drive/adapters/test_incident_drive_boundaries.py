from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[6]


def test_incident_drive_package_exists_and_has_no_hookimpls():
    package_dir = APP_ROOT / "packages" / "incident" / "drive"
    assert package_dir.is_dir()
    offenders = [path.name for path in package_dir.rglob("*.py") if "hookimpl" in path.read_text(encoding="utf-8")]
    assert offenders == []


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


def test_incident_drive_adapter_imports_client_not_legacy_google_drive():
    """The adapter accesses the SDK through integrations.google_workspace.client, not the legacy google_drive module."""
    adapter_path = APP_ROOT / "packages" / "incident" / "drive" / "adapters" / "google_drive.py"
    adapter_text = adapter_path.read_text(encoding="utf-8")

    # Must NOT import the legacy google_drive module
    assert "integrations.google_workspace import google_drive" not in adapter_text

    # Must import the client module (the correct Path B boundary)
    assert (
        "from integrations.google_workspace import client" in adapter_text
        or "integrations.google_workspace import client" in adapter_text
    )
