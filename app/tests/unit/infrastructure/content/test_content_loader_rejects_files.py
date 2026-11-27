"""Behaviour of the content loader on invalid files, over real files in a temporary root.

Every problem is collected into one ContentLoadError; each names the kind, file and field
and never the input value.
"""

from pathlib import Path

import pytest

from contracts.content import ContentLoadError, ContentProblem
from infrastructure.content.loader import ContentLoader
from tests.factories.content import WIDGETS, widget_text, write_item

pytestmark = pytest.mark.unit

SECRET = "s3cr3t-value-never-logged"


def _problems(root: Path) -> tuple[ContentProblem, ...]:
    loader = ContentLoader(root, max_file_bytes=16_384, max_items_per_kind=200)
    loader.register(WIDGETS)
    with pytest.raises(ContentLoadError) as raised:
        loader.load()
    return raised.value.problems


def _only(root: Path) -> ContentProblem:
    problems = _problems(root)
    assert len(problems) == 1
    return problems[0]


def test_the_same_id_in_two_folders_is_refused_naming_the_second_file(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "a/same.yaml", widget_text("same"))
    write_item(tmp_path, WIDGETS, "b/same.yaml", widget_text("same"))

    problem = _only(tmp_path)

    assert (problem.file, problem.field) == ("probe/widgets/b/same.yaml", "id")
    assert "probe/widgets/a/same.yaml" in problem.message


def test_a_file_name_that_differs_from_its_id_is_refused(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "name.yaml", widget_text("other"))

    problem = _only(tmp_path)

    assert (problem.file, problem.field) == ("probe/widgets/name.yaml", "id")


def test_invalid_yaml_is_refused_with_its_line(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "bad.yaml", "kind: [unclosed\n")

    problem = _only(tmp_path)

    assert problem.file == "probe/widgets/bad.yaml"
    assert "invalid YAML at line" in problem.message


def test_a_python_tag_is_refused_by_the_safe_loader(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "tag.yaml", widget_text("tag") + "extra: !!python/object/apply:os.getcwd []\n")

    assert _only(tmp_path).file == "probe/widgets/tag.yaml"


def test_a_duplicate_mapping_key_is_refused_naming_the_file(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "dup.yaml", widget_text("dup") + "title: Again\n")

    problem = _only(tmp_path)

    assert problem.file == "probe/widgets/dup.yaml"
    assert "duplicate mapping key" in problem.message


def test_a_kind_that_differs_from_the_directory_is_refused(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "x.yaml", widget_text("x", kind="probe/gadgets"))

    problem = _only(tmp_path)

    assert (problem.file, problem.field) == ("probe/widgets/x.yaml", "kind")


@pytest.mark.parametrize("version", [2, 0, "1", True])
def test_an_unknown_version_is_refused(tmp_path: Path, version: object) -> None:
    write_item(tmp_path, WIDGETS, "x.yaml", f"kind: probe/widgets\nversion: {version!r}\nid: x\ntitle: T\n".replace("'", '"'))

    problem = _only(tmp_path)

    assert (problem.file, problem.field) == ("probe/widgets/x.yaml", "version")


def test_a_yml_file_is_refused(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "x.yml", widget_text("x"))

    problem = _only(tmp_path)

    assert problem.file == "probe/widgets/x.yml"
    assert ".yaml" in problem.message


def test_a_symlink_to_a_file_outside_the_root_is_refused_and_not_read(tmp_path: Path) -> None:
    outside = tmp_path / "outside.yaml"
    outside.write_text(widget_text("link"), encoding="utf-8")
    root = tmp_path / "root"
    (root / "probe" / "widgets").mkdir(parents=True)
    (root / "probe" / "widgets" / "link.yaml").symlink_to(outside)

    problem = _only(root)

    assert problem.file == "probe/widgets/link.yaml"
    assert "symlinks" in problem.message


def test_a_symlinked_kind_directory_outside_the_root_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "x.yaml").write_text(widget_text("x"), encoding="utf-8")
    root = tmp_path / "root"
    (root / "probe").mkdir(parents=True)
    (root / "probe" / "widgets").symlink_to(outside, target_is_directory=True)

    assert "symlinks" in _only(root).message


def test_a_field_error_names_the_file_and_field_and_not_the_input_value(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "x.yaml", f"kind: probe/widgets\nversion: 1\nid: x\ntitle: [{SECRET}]\n")

    problem = _only(tmp_path)

    assert (problem.file, problem.field) == ("probe/widgets/x.yaml", "title")
    assert SECRET not in f"{problem.message} {problem.file} {problem.field}"


def test_an_unknown_field_is_refused_by_name(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "x.yaml", widget_text("x") + f"{'surprise'}: {SECRET}\n")

    problem = _only(tmp_path)

    assert problem.field == "surprise"
    assert SECRET not in problem.message


def test_every_problem_is_reported_in_one_error(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "bad.yaml", "kind: [unclosed\n")
    write_item(tmp_path, WIDGETS, "wrong.yaml", widget_text("other"))
    write_item(tmp_path, WIDGETS, "x.yml", widget_text("x"))

    files = {problem.file for problem in _problems(tmp_path)}

    assert files == {"probe/widgets/bad.yaml", "probe/widgets/wrong.yaml", "probe/widgets/x.yml"}


def test_an_unhashable_mapping_key_is_refused_naming_the_file(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "complex.yaml", "? [a, b]\n: 1\n")

    problem = _only(tmp_path)

    assert problem.file == "probe/widgets/complex.yaml"
    assert "invalid YAML" in problem.message


def test_a_kind_path_that_is_a_file_is_refused_naming_the_kind(tmp_path: Path) -> None:
    (tmp_path / "probe").mkdir()
    (tmp_path / "probe" / "widgets").write_text("not a directory\n")

    problem = _only(tmp_path)

    assert (problem.kind, problem.file) == ("probe/widgets", "probe/widgets")
    assert "directory" in problem.message
