"""Behaviour of schema export and the drift/content check, over a temporary schemas directory.

The test-only kind's model generates the schema; files are written under ``tmp_path``.
"""

import json
from pathlib import Path

import pytest

from bin.check_content_schemas import run
from infrastructure.content.schema import schema_drift, schema_path, schema_text, write_schemas
from tests.factories.content import WIDGETS, widget_text, write_item

pytestmark = pytest.mark.unit


def test_schema_text_is_stable_sorted_indented_and_newline_terminated() -> None:
    text = schema_text(WIDGETS)

    assert text.endswith("}\n")
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    assert "title" in json.loads(text)["properties"]


def test_schema_path_is_owner_then_kind_name(tmp_path: Path) -> None:
    assert schema_path(tmp_path, WIDGETS) == tmp_path / "probe" / "widgets.json"


def test_written_schemas_match_and_a_changed_or_missing_file_is_drift(tmp_path: Path) -> None:
    assert schema_drift([WIDGETS], tmp_path)

    write_schemas([WIDGETS], tmp_path)
    assert schema_drift([WIDGETS], tmp_path) == []

    schema_path(tmp_path, WIDGETS).write_text("{}\n", encoding="utf-8")
    assert "differs" in schema_drift([WIDGETS], tmp_path)[0]


def test_run_with_write_regenerates_then_passes_and_without_it_reports_drift(tmp_path: Path) -> None:
    schemas, root = tmp_path / "schemas", tmp_path / "content"

    assert run([WIDGETS], roots=[root], schemas_directory=schemas)
    assert run([WIDGETS], roots=[root], schemas_directory=schemas, write=True) == []
    assert run([WIDGETS], roots=[root], schemas_directory=schemas) == []


def test_run_exports_the_schemas_to_the_requested_directory(tmp_path: Path) -> None:
    export = tmp_path / "export"

    run([WIDGETS], roots=[], schemas_directory=tmp_path / "schemas", export=export)

    assert schema_path(export, WIDGETS).read_text(encoding="utf-8") == schema_text(WIDGETS)


def test_run_fails_a_content_file_that_fails_its_model(tmp_path: Path) -> None:
    schemas, root = tmp_path / "schemas", tmp_path / "content"
    write_schemas([WIDGETS], schemas)
    write_item(root, WIDGETS, "good.yaml", widget_text("good"))
    write_item(root, WIDGETS, "bad.yaml", "kind: probe/widgets\nversion: 1\nid: bad\n")

    lines = run([WIDGETS], roots=[root], schemas_directory=schemas)

    assert len(lines) == 1
    assert "probe/widgets/bad.yaml" in lines[0]
    assert "title" in lines[0]


def test_with_no_kind_registered_there_is_nothing_to_compare_or_load(tmp_path: Path) -> None:
    assert run([], roots=[tmp_path / "missing"], schemas_directory=tmp_path / "schemas") == []
