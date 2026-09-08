from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[5]


def test_incident_documents_package_exposes_extract_google_doc_id():
    from packages.incident.documents import utils

    assert callable(utils.extract_google_doc_id)


def test_extract_google_doc_id_is_not_left_in_google_workspace_sources():
    package_dir = APP_ROOT / "integrations" / "google_workspace"
    offenders = [path.name for path in package_dir.glob("*.py") if "extract_google_doc_id" in path.read_text(encoding="utf-8")]
    assert offenders == []


def test_incident_documents_package_ships_no_hookimpls():
    package_dir = APP_ROOT / "packages" / "incident" / "documents"
    offenders = [path.name for path in package_dir.rglob("*.py") if "hookimpl" in path.read_text(encoding="utf-8")]
    assert offenders == []
