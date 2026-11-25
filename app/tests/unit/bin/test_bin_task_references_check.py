"""Behavior of the task-reference guard: which task ids it reports and its verdict against a baseline.

Each test writes a throwaway tree under ``tmp_path`` and passes it to the guard's
functions, or points the guard's module constants at it, so nothing depends on the
real repository. Assertions read the reported entries and the exit code, the
guard's whole interface in CI.
"""

from pathlib import Path

import pytest

from bin import check_task_references as guard

pytestmark = pytest.mark.unit


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_a_todo_marker_is_allowed_and_every_other_mention_is_reported() -> None:
    text = '''"""Moved by TASK-12.3; see TASK-7."""
# TODO(TASK-9): delete with the legacy flow.
x = 1  # TODO(TASK-9.1) then TASK-10 owns it
'''

    assert guard.bare_task_ids(text) == {"TASK-12.3", "TASK-7", "TASK-10"}


def test_a_sentence_ending_after_an_id_keeps_the_id_whole() -> None:
    assert guard.bare_task_ids("until TASK-83.6. Then") == {"TASK-83.6"}


def test_entries_name_the_app_relative_file_and_skip_excluded_files(tmp_path: Path) -> None:
    _write(tmp_path / "features" / "a.py", "# owned by TASK-1\n")
    _write(tmp_path / "tests" / "test_a.py", '"""Pins TASK-2."""\n')
    skipped = _write(tmp_path / "bin" / "guard.py", "# TASK-3\n")
    _write(tmp_path / "features" / "b.py", "# TODO(TASK-4): remove\n")

    entries = guard.current_entries(tmp_path, excluded=frozenset({skipped.resolve()}))

    assert entries == {"features/a.py:TASK-1", "tests/test_a.py:TASK-2"}


@pytest.mark.parametrize(
    ("baseline", "expected_exit"),
    [("features/a.py:TASK-1\n", 0), ("", 1), ("features/a.py:TASK-1\nfeatures/gone.py:TASK-5\n", 0)],
    ids=["baselined", "net_new_fails", "stale_never_fails"],
)
def test_the_verdict_fails_only_on_net_new_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], baseline: str, expected_exit: int
) -> None:
    app_root = tmp_path / "app"
    _write(app_root / "features" / "a.py", "# owned by TASK-1\n")
    baseline_path = _write(app_root / "bin" / "baselines" / "task_references.txt", f"# header\n{baseline}")
    monkeypatch.setattr(guard, "APP_ROOT", app_root)
    monkeypatch.setattr(guard, "BASELINE_PATH", baseline_path)

    exit_code = guard.main([])

    assert exit_code == expected_exit
    if expected_exit:
        assert "features/a.py:TASK-1" in capsys.readouterr().out


def test_print_entries_lists_the_current_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "features" / "a.py", "# TASK-2 and TASK-1\n")
    monkeypatch.setattr(guard, "APP_ROOT", tmp_path)

    assert guard.main(["--print-entries"]) == 0
    assert capsys.readouterr().out.splitlines() == ["features/a.py:TASK-1", "features/a.py:TASK-2"]
