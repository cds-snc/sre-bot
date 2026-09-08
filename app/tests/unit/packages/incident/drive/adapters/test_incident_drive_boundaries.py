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
