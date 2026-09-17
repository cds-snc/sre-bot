"""Behavior of the plumbing shared by the freeze-baseline guardrails under bin/.

Every helper takes its paths as arguments, so each test builds a throwaway tree
under ``tmp_path`` and passes it in; nothing is monkeypatched and no test depends
on the real repository. The report tests assert on captured stdout because the
printed block is the guard's whole interface to a developer reading CI output,
and on the return value because that is what becomes the process exit code.
"""

from pathlib import Path

import pytest

from bin import freeze_guard

OK_TEMPLATE = "no net-new widgets ({count} baselined widget(s) remain)."
STALE_LABEL = "baseline entries with no remaining widget (safe to remove)"
FAIL_LABEL = "files contain widgets but are not in the baseline"
REMEDIATION = "Baselines only ratchet down; migrate the consumer instead of widening the baseline."


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _report(tmp_path: Path, current: set[str], baseline: set[str]) -> int:
    """Run the report against a fake app tree, so the printed Baseline line is deterministic."""
    app_root = tmp_path / "app"
    baseline_path = app_root / "bin" / "baselines" / "widgets.txt"
    _write(baseline_path, "# widgets\n")
    return freeze_guard.report(
        current=current,
        baseline=baseline,
        baseline_path=baseline_path,
        app_root=app_root,
        stale_label=STALE_LABEL,
        fail_label=FAIL_LABEL,
        remediation=REMEDIATION,
        ok_template=OK_TEMPLATE,
    )


class TestIterPythonFiles:
    def test_python_files_are_yielded_and_other_files_are_not(self, tmp_path):
        """The guards reason about Python source, so a README mentioning a forbidden name must not be scanned."""
        module = _write(tmp_path / "vendor" / "client.py")
        _write(tmp_path / "vendor" / "README.md", "OperationResult\n")

        assert list(freeze_guard.iter_python_files(tmp_path)) == [module]

    @pytest.mark.parametrize("excluded_name", ["__pycache__", ".mypy_cache", ".pytest_cache", ".venv", "node_modules"])
    def test_files_inside_an_excluded_directory_are_skipped(self, tmp_path, excluded_name):
        """A stale .pyc-adjacent copy or a vendored dependency is not the tree under review."""
        kept = _write(tmp_path / "vendor" / "client.py")
        _write(tmp_path / "vendor" / excluded_name / "client.py")

        assert list(freeze_guard.iter_python_files(tmp_path)) == [kept]

    def test_an_excluded_name_above_the_scan_root_does_not_empty_the_scan(self, tmp_path):
        """Matching exclusions on the absolute path skipped every file whenever the checkout sat under such a directory.

        That silently turned a guard into a no-op: it reported a clean tree because it
        had scanned nothing. Exclusions are therefore matched relative to the scan root.
        """
        root = tmp_path / ".venv" / "project" / "integrations"
        module = _write(root / "vendor" / "client.py")

        assert list(freeze_guard.iter_python_files(root)) == [module]

    def test_a_file_root_yields_itself(self, tmp_path):
        """Shipped roots include main.py, so a root that is not a directory still has to be scanned."""
        main = _write(tmp_path / "main.py")

        assert list(freeze_guard.iter_python_files(main)) == [main]

    def test_results_are_sorted(self, tmp_path):
        """Stable ordering keeps a guard's failure list diffable between runs."""
        _write(tmp_path / "b.py")
        _write(tmp_path / "a.py")
        _write(tmp_path / "sub" / "c.py")

        assert list(freeze_guard.iter_python_files(tmp_path)) == [
            tmp_path / "a.py",
            tmp_path / "b.py",
            tmp_path / "sub" / "c.py",
        ]

    def test_an_explicit_excluded_set_replaces_the_default(self, tmp_path):
        """A caller passing its own set gets exactly that set, not the default widened by it."""
        cached = _write(tmp_path / "__pycache__" / "client.py")
        _write(tmp_path / "skipme" / "client.py")

        assert list(freeze_guard.iter_python_files(tmp_path, excluded={"skipme"})) == [cached]


class TestLoadBaseline:
    def test_blank_lines_and_comments_are_ignored_and_entries_are_stripped(self, tmp_path):
        baseline_path = _write(
            tmp_path / "baseline.txt",
            "# header\n\nmodule:integrations/aws/sqs.py\n  \n# another comment\noperation-result:integrations/aws/shield.py\n",
        )

        assert freeze_guard.load_baseline(baseline_path) == {
            "module:integrations/aws/sqs.py",
            "operation-result:integrations/aws/shield.py",
        }

    def test_a_missing_baseline_file_is_an_empty_set(self, tmp_path):
        """Running a new guard against no baseline is how its first baseline is seeded."""
        assert freeze_guard.load_baseline(tmp_path / "does-not-exist.txt") == set()


class TestReport:
    def test_a_tree_matching_its_baseline_passes_and_reports_the_count(self, tmp_path, capsys):
        entries = {"integrations/aws/client.py", "integrations/aws/sqs.py"}

        exit_code = _report(tmp_path, current=entries, baseline=entries)

        out = capsys.readouterr().out
        assert exit_code == 0
        assert out == "OK: no net-new widgets (2 baselined widget(s) remain).\n"

    def test_stale_baseline_entries_are_reported_without_failing(self, tmp_path, capsys):
        """The baseline only ratchets down, so an entry whose violation is gone is news, not a failure."""
        exit_code = _report(tmp_path, current=set(), baseline={"integrations/aws/dynamodb.py"})

        out = capsys.readouterr().out
        assert exit_code == 0
        assert f"INFO: {STALE_LABEL}:" in out
        assert "  - integrations/aws/dynamodb.py" in out
        assert "FAIL" not in out

    def test_an_unbaselined_violation_fails_and_names_the_baseline_and_the_fix(self, tmp_path, capsys):
        """This is the check's whole purpose, and the output has to tell the author what to do instead."""
        exit_code = _report(tmp_path, current={"integrations/aws/new.py"}, baseline=set())

        out = capsys.readouterr().out
        assert exit_code == 1
        assert f"FAIL: {FAIL_LABEL}:" in out
        assert "  - integrations/aws/new.py" in out
        assert "Baseline: app/bin/baselines/widgets.txt" in out
        assert REMEDIATION in out

    def test_stale_entries_are_reported_before_a_failure(self, tmp_path, capsys):
        """A failing run still shows what can be pruned, and the failure stays the last thing read."""
        exit_code = _report(tmp_path, current={"new.py"}, baseline={"gone.py"})

        out = capsys.readouterr().out
        assert exit_code == 1
        assert out.index("INFO:") < out.index("FAIL:")

    def test_entries_are_printed_sorted(self, tmp_path, capsys):
        """Set iteration order would make CI output churn between otherwise identical runs."""
        _report(tmp_path, current={"c.py", "a.py", "b.py"}, baseline=set())

        listed = [line.removeprefix("  - ") for line in capsys.readouterr().out.splitlines() if line.startswith("  - ")]
        assert listed == ["a.py", "b.py", "c.py"]
