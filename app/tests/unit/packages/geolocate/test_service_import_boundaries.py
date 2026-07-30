"""Behavior tests for geolocate service import boundaries."""

import ast
from pathlib import Path


def test_service_uses_feature_adapter_for_maxmind_import() -> None:
    """The service imports MaxMind via the feature adapter, not infrastructure clients."""
    service_path = Path(__file__).resolve().parents[4] / "packages" / "geolocate" / "service.py"
    tree = ast.parse(service_path.read_text())

    import_from_modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}

    assert "packages.geolocate.adapters.maxmind" in import_from_modules
    assert "infrastructure.clients.maxmind" not in import_from_modules
