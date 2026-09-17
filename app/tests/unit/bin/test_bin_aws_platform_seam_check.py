"""Behavior tests for the packages/aws_platform transition-seam freeze-baseline checker.

Each test writes a throwaway app tree under ``tmp_path`` and points the
checker's path constants at it, so no test depends on the real repository or on
which files happen to import the seam today. Detection is asserted through
``references_seam`` on single files (one detection form per test, so a failure
names the form that broke) and through ``find_current_consumers`` for the scan
scope. The ``main`` tests assert on captured stdout and on the return value,
because the printed block and the exit code are the whole interface the guard
presents to CI and to the developer reading it.
"""

from pathlib import Path

import pytest

from bin import check_aws_platform_seam as checker


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _use_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str],
    baseline: str = "# empty baseline\n",
    pyproject: str = "[project]\nname = 'fake'\n",
) -> Path:
    """Write ``files`` under a fake app root and aim every checker constant at it."""
    app_root = tmp_path / "app"
    for relative_path, content in files.items():
        _write(app_root / relative_path, content)
    baseline_path = _write(app_root / "bin" / "baselines" / "seam.txt", baseline)
    pyproject_path = _write(app_root / "pyproject.toml", pyproject)

    monkeypatch.setattr(checker, "APP_ROOT", app_root)
    monkeypatch.setattr(checker, "SEAM_TREE", app_root / "packages" / "aws_platform")
    monkeypatch.setattr(checker, "TESTS_TREE", app_root / "tests")
    monkeypatch.setattr(checker, "SELF_PATH", app_root / "bin" / "check_aws_platform_seam.py")
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(checker, "PYPROJECT_PATH", pyproject_path)
    return app_root


def _references(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative_path: str, source: str) -> bool:
    """Run the single-file detector over one throwaway module."""
    app_root = _use_tree(tmp_path, monkeypatch, {relative_path: source})
    return checker.references_seam(app_root / relative_path)


class TestReferencesSeam:
    """One detection form per test, so a regression names the form it broke."""

    @pytest.mark.parametrize(
        "source",
        [
            "import packages.aws_platform\n",
            "import packages.aws_platform.adapters.dynamodb as ddb\n",
        ],
    )
    def test_an_absolute_import_of_the_seam_is_a_reference(self, tmp_path, monkeypatch, source):
        assert _references(tmp_path, monkeypatch, "modules/consumer.py", source) is True

    def test_an_import_from_inside_the_seam_is_a_reference(self, tmp_path, monkeypatch):
        source = "from packages.aws_platform.adapters import dynamodb\n"

        assert _references(tmp_path, monkeypatch, "modules/consumer.py", source) is True

    def test_importing_the_seam_as_a_name_from_its_parent_package_is_a_reference(self, tmp_path, monkeypatch):
        """'from packages import aws_platform' names the seam in the alias, not in the module."""
        source = "from packages import aws_platform\n"

        assert _references(tmp_path, monkeypatch, "modules/consumer.py", source) is True

    def test_a_relative_import_resolved_against_its_package_is_a_reference(self, tmp_path, monkeypatch):
        """A sibling package reaching the seam with '..' must not slip past an absolute-only check."""
        source = "from .. import aws_platform\n"

        assert _references(tmp_path, monkeypatch, "packages/other/consumer.py", source) is True

    @pytest.mark.parametrize(
        "source",
        [
            "import packages.access\n",
            "from packages.access import catalog\n",
            "from . import sibling\n",
        ],
    )
    def test_an_unrelated_import_is_not_a_reference(self, tmp_path, monkeypatch, source):
        assert _references(tmp_path, monkeypatch, "packages/other/consumer.py", source) is False

    @pytest.mark.parametrize(
        "source",
        [
            "import packages.aws_platformer\n",
            "from packages import aws_platformer\n",
            "x = 'packages.aws_platformer'\n",
        ],
    )
    def test_a_longer_name_sharing_the_seam_prefix_is_not_a_reference(self, tmp_path, monkeypatch, source):
        """The dotted-boundary check; a plain startswith would report this package as a consumer."""
        assert _references(tmp_path, monkeypatch, "modules/consumer.py", source) is False

    @pytest.mark.parametrize(
        "source",
        [
            "MODULE = 'packages.aws_platform.adapters.dynamodb'\n",
            "import importlib\nm = importlib.import_module('packages.aws_platform')\n",
            "from unittest import mock\np = mock.patch('packages.aws_platform.adapters.config.build_config_adapter')\n",
        ],
    )
    def test_a_string_constant_naming_the_seam_is_a_reference(self, tmp_path, monkeypatch, source):
        """Dynamic imports and patch targets keep a file dependent on the seam without importing it."""
        assert _references(tmp_path, monkeypatch, "modules/consumer.py", source) is True

    @pytest.mark.parametrize(
        ("relative_path", "source"),
        [
            ("modules/consumer.py", '"""Superseded by packages.aws_platform."""\n'),
            ("modules/consumer.py", 'def f() -> None:\n    """Was packages.aws_platform."""\n'),
            ("modules/consumer.py", 'class C:\n    """Replaces packages.aws_platform."""\n'),
        ],
    )
    def test_a_docstring_mentioning_the_seam_is_not_a_reference(self, tmp_path, monkeypatch, relative_path, source):
        """Prose about the migration must not pin a file into the baseline forever."""
        assert _references(tmp_path, monkeypatch, relative_path, source) is False

    def test_an_unparsable_file_fails_loudly(self, tmp_path, monkeypatch):
        """Silently skipping a broken file is how a real consumer would go unnoticed."""
        app_root = _use_tree(tmp_path, monkeypatch, {"modules/broken.py": "def (:\n"})

        with pytest.raises(SyntaxError):
            checker.references_seam(app_root / "modules" / "broken.py")


class TestFindCurrentConsumers:
    """What the scan covers, and what it deliberately does not."""

    def test_a_consumer_is_reported_as_an_app_relative_posix_path(self, tmp_path, monkeypatch):
        _use_tree(tmp_path, monkeypatch, {"modules/slack/webhooks.py": "import packages.aws_platform\n"})

        assert checker.find_current_consumers() == {"modules/slack/webhooks.py"}

    def test_a_consumer_under_bin_is_in_scope(self, tmp_path, monkeypatch):
        """bin/ is scanned too: a script reaching the seam is a dependent like any other."""
        _use_tree(tmp_path, monkeypatch, {"bin/some_tool.py": "import packages.aws_platform\n"})

        assert checker.find_current_consumers() == {"bin/some_tool.py"}

    def test_tests_are_not_consumers(self, tmp_path, monkeypatch):
        """Tests import the seam by design; baselining them would never ratchet down."""
        _use_tree(tmp_path, monkeypatch, {"tests/unit/test_thing.py": "import packages.aws_platform\n"})

        assert checker.find_current_consumers() == set()

    def test_the_seam_tree_does_not_count_as_its_own_consumer(self, tmp_path, monkeypatch):
        _use_tree(
            tmp_path,
            monkeypatch,
            {"packages/aws_platform/adapters/dynamodb.py": "from packages.aws_platform import shared\n"},
        )

        assert checker.find_current_consumers() == set()

    def test_the_guard_script_does_not_count_as_a_consumer(self, tmp_path, monkeypatch):
        """The script names the seam in its own constants."""
        _use_tree(
            tmp_path,
            monkeypatch,
            {"bin/check_aws_platform_seam.py": "SEAM_MODULE = 'packages.aws_platform'\n"},
        )

        assert checker.find_current_consumers() == set()

    def test_a_non_python_file_naming_the_seam_is_not_a_consumer(self, tmp_path, monkeypatch):
        _use_tree(tmp_path, monkeypatch, {"modules/README.md": "Uses packages.aws_platform.\n"})

        assert checker.find_current_consumers() == set()


class TestPyprojectEntryPoints:
    """An entry-point string keeps the seam loaded at startup with no import in any .py file."""

    def test_an_entry_point_naming_the_seam_is_reported(self, tmp_path, monkeypatch):
        pyproject = (
            '[project]\nname = \'fake\'\n\n[project.entry-points."sre_bot"]\naws = "packages.aws_platform.plugin:register"\n'
        )
        _use_tree(tmp_path, monkeypatch, {}, pyproject=pyproject)

        assert checker.find_current_consumers() == {"pyproject.toml"}

    def test_a_console_script_naming_the_seam_is_reported(self, tmp_path, monkeypatch):
        pyproject = "[project]\nname = 'fake'\n\n[project.scripts]\nseam = \"packages.aws_platform.cli:main\"\n"
        _use_tree(tmp_path, monkeypatch, {}, pyproject=pyproject)

        assert checker.find_current_consumers() == {"pyproject.toml"}

    def test_a_pyproject_without_entry_points_is_not_reported(self, tmp_path, monkeypatch):
        """Today's real pyproject.toml declares no entry-point table at all."""
        _use_tree(tmp_path, monkeypatch, {})

        assert checker.find_current_consumers() == set()


class TestMain:
    """The verdict, its output and its exit code, proving the shared report is wired in."""

    def test_a_tree_matching_its_baseline_passes_and_reports_the_count(self, tmp_path, monkeypatch, capsys):
        _use_tree(
            tmp_path,
            monkeypatch,
            {"modules/slack/webhooks.py": "import packages.aws_platform\n"},
            baseline="# seam consumers\nmodules/slack/webhooks.py\n",
        )

        exit_code = checker.main()

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "OK: no net-new packages.aws_platform consumers (1 baselined consumer(s) remain)." in out
        assert "FAIL" not in out

    def test_an_unbaselined_consumer_fails_and_names_the_baseline_and_the_fix(self, tmp_path, monkeypatch, capsys):
        """Widening the baseline is the one fix the output must not make the obvious one."""
        _use_tree(tmp_path, monkeypatch, {"modules/newcomer.py": "import packages.aws_platform\n"})

        exit_code = checker.main()

        out = capsys.readouterr().out
        assert exit_code == 1
        assert "modules/newcomer.py" in out
        assert "Baseline:" in out
        assert "TASK-88" in out

    def test_a_baselined_file_that_stopped_importing_the_seam_is_reported_without_failing(self, tmp_path, monkeypatch, capsys):
        """The baseline only ratchets down, so a migrated consumer is news, not a failure."""
        _use_tree(tmp_path, monkeypatch, {}, baseline="modules/migrated.py\n")

        exit_code = checker.main()

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "INFO:" in out
        assert "modules/migrated.py" in out
        assert "FAIL" not in out
