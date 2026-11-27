"""Every shipped content example validates against its kind.

A test-only kind with a fixture example proves the path; the shipped examples directory
is validated against the kinds the installed plugins register.
"""

from pathlib import Path

import pytest

from bin.check_content_schemas import APP_ROOT, DEFAULT_ROOTS, SCHEMAS_DIRECTORY, check_content, collect_kinds
from infrastructure.content.schema import schema_drift
from tests.factories.content import WIDGETS, widget_text, write_item

pytestmark = pytest.mark.unit


def test_a_valid_example_for_a_registered_kind_validates(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "example-widget.yaml", widget_text("example-widget", "Example"))

    assert check_content([WIDGETS], [tmp_path]) == []


def test_an_invalid_example_is_reported_with_its_file(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "example-widget.yaml", widget_text("example-widget", "Example", version=9))

    (line,) = check_content([WIDGETS], [tmp_path])

    assert "probe/widgets/example-widget.yaml" in line


def test_the_shipped_content_roots_and_schemas_agree_with_the_registered_kinds() -> None:
    kinds = collect_kinds()

    assert check_content(kinds, DEFAULT_ROOTS) == []
    assert schema_drift(kinds, SCHEMAS_DIRECTORY) == []
    assert (APP_ROOT / "content" / "examples" / "README.md").is_file()
