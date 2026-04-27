"""Guards for access test filename conventions."""

from pathlib import Path

import pytest


@pytest.mark.unit
def test_access_catalog_and_sync_tests_use_feature_prefix_filenames() -> None:
    access_tests_root = Path(__file__).parent
    forbidden_names = {"test_routes.py", "test_service.py", "test_parsers.py"}
    scoped_dirs = [
        access_tests_root / "catalog",
        access_tests_root / "sync",
    ]

    offenders: list[str] = []
    for directory in scoped_dirs:
        for file_path in directory.glob("*.py"):
            if file_path.name in forbidden_names:
                offenders.append(str(file_path.relative_to(access_tests_root)))

    assert offenders == []
