"""Behavior tests for the vendor-package export contract freeze-baseline checker.

Each test builds a throwaway ``integrations/`` tree under ``tmp_path`` and points
the checker's path constants at it, so no test depends on the real vendor
packages. The only exception is the final test, which inspects the committed
baseline file.
"""

from pathlib import Path

import pytest

from bin import check_vendor_package_contract as checker

COMPLIANT_VENDOR = {
    "__init__.py": "",
    "vendor/__init__.py": "",
    "vendor/client.py": "def build_client() -> object:\n    return object()\n",
    "vendor/settings.py": "class VendorSettings:\n    pass\n",
}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _use_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str],
    baseline: str = "# empty baseline\n",
) -> None:
    """Write ``files`` under a fake integrations root and aim the checker at it."""
    integrations_root = tmp_path / "integrations"
    integrations_root.mkdir()
    for relative_path, content in files.items():
        _write(integrations_root / relative_path, content)
    baseline_path = tmp_path / "baseline.txt"
    _write(baseline_path, baseline)
    monkeypatch.setattr(checker, "APP_ROOT", tmp_path)
    monkeypatch.setattr(checker, "INTEGRATIONS_ROOT", integrations_root)
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)


def test_main_passes_for_compliant_vendor_package(tmp_path, monkeypatch):
    _use_tree(tmp_path, monkeypatch, COMPLIANT_VENDOR)

    assert checker.find_current_violations() == set()
    assert checker.main() == 0


def test_main_fails_on_extra_vendor_module_not_in_baseline(tmp_path, monkeypatch, capsys):
    """A mirror-layer module beside client.py is exactly the drift the check exists to block."""
    _use_tree(tmp_path, monkeypatch, {**COMPLIANT_VENDOR, "vendor/mirror.py": "def list_things() -> list[str]:\n    return []\n"})

    exit_code = checker.main()

    assert exit_code == 1
    assert "module:integrations/vendor/mirror.py" in capsys.readouterr().out


def test_find_current_violations_reports_nested_subpackage_files(tmp_path, monkeypatch):
    """Allowed file names only count directly in the vendor directory, so a nested client.py is still a violation."""
    _use_tree(
        tmp_path,
        monkeypatch,
        {**COMPLIANT_VENDOR, "vendor/sub/__init__.py": "", "vendor/sub/client.py": ""},
    )

    assert checker.find_current_violations() == {
        "module:integrations/vendor/sub/__init__.py",
        "module:integrations/vendor/sub/client.py",
    }


def test_find_current_violations_reports_loose_top_level_module(tmp_path, monkeypatch):
    _use_tree(tmp_path, monkeypatch, {**COMPLIANT_VENDOR, "helpers.py": ""})

    assert checker.find_current_violations() == {"module:integrations/helpers.py"}


def test_find_current_violations_allows_integrations_package_init(tmp_path, monkeypatch):
    _use_tree(tmp_path, monkeypatch, {"__init__.py": ""})

    assert checker.find_current_violations() == set()


def test_main_warns_without_failing_for_non_vendor_directory_modules(tmp_path, monkeypatch, capsys):
    """utils/ is not a vendor package: its modules surface as a warning, never as a violation."""
    _use_tree(
        tmp_path,
        monkeypatch,
        {**COMPLIANT_VENDOR, "utils/__init__.py": "", "utils/api.py": "def helper() -> None:\n    pass\n"},
    )

    exit_code = checker.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "WARN" in output
    assert "integrations/utils/api.py" in output
    assert "integrations/utils/api.py" in checker.find_warnings()
    assert not any("integrations/utils/" in entry for entry in checker.find_current_violations())


def test_main_fails_when_non_vendor_module_references_operation_result(tmp_path, monkeypatch, capsys):
    """The warning path exempts utils/ from the module rule only; the OperationResult rule still applies."""
    _use_tree(
        tmp_path,
        monkeypatch,
        {
            **COMPLIANT_VENDOR,
            "utils/__init__.py": "",
            "utils/api.py": "from infrastructure.operations.result import OperationResult\n",
        },
    )

    exit_code = checker.main()

    assert exit_code == 1
    assert "operation-result:integrations/utils/api.py" in capsys.readouterr().out


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("from infrastructure.operations.result import OperationResult\n", id="from-import"),
        pytest.param("from infrastructure.operations import OperationResult as R\n", id="aliased-import"),
        pytest.param(
            "import infrastructure.operations as ops\n\n\ndef build() -> None:\n    ops.OperationResult\n",
            id="attribute-access",
        ),
        pytest.param("def build() -> OperationResult:\n    raise NotImplementedError\n", id="return-annotation"),
    ],
)
def test_find_current_violations_reports_operation_result_code_reference(tmp_path, monkeypatch, source):
    """client.py is an allowed module, so the only expected entry is the operation-result one."""
    _use_tree(tmp_path, monkeypatch, {**COMPLIANT_VENDOR, "vendor/client.py": source})

    assert checker.find_current_violations() == {"operation-result:integrations/vendor/client.py"}


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("from infrastructure.operations.result import OperationStatus\n", id="operation-status-import"),
        pytest.param('"""Classifies errors; never builds an OperationResult."""\n', id="module-docstring"),
        pytest.param("# Returns a tuple rather than an OperationResult.\nVALUE = 1\n", id="comment"),
    ],
)
def test_find_current_violations_ignores_non_code_operation_result_mentions(tmp_path, monkeypatch, source):
    """Detection is AST-based, so prose mentions and the allowed OperationStatus never count."""
    _use_tree(tmp_path, monkeypatch, {**COMPLIANT_VENDOR, "vendor/client.py": source})

    assert checker.find_current_violations() == set()


def test_main_passes_when_violation_is_baselined(tmp_path, monkeypatch):
    _use_tree(
        tmp_path,
        monkeypatch,
        {**COMPLIANT_VENDOR, "vendor/extra.py": ""},
        baseline="module:integrations/vendor/extra.py\n",
    )

    assert checker.main() == 0


def test_main_reports_stale_baseline_entry_without_failing(tmp_path, monkeypatch, capsys):
    _use_tree(
        tmp_path,
        monkeypatch,
        COMPLIANT_VENDOR,
        baseline="module:integrations/vendor/already_removed.py\n",
    )

    exit_code = checker.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "INFO" in output
    assert "module:integrations/vendor/already_removed.py" in output


def test_main_fails_when_baselined_extra_module_newly_references_operation_result(tmp_path, monkeypatch, capsys):
    """Baseline entries are rule-qualified: grandfathering a file's module violation does not grandfather new rules."""
    _use_tree(
        tmp_path,
        monkeypatch,
        {**COMPLIANT_VENDOR, "vendor/extra.py": "from infrastructure.operations.result import OperationResult\n"},
        baseline="module:integrations/vendor/extra.py\n",
    )

    exit_code = checker.main()

    assert exit_code == 1
    assert "operation-result:integrations/vendor/extra.py" in capsys.readouterr().out
    assert checker.find_current_violations() - checker.load_baseline() == {"operation-result:integrations/vendor/extra.py"}


def test_load_baseline_ignores_blank_and_comment_lines(tmp_path, monkeypatch):
    baseline_path = tmp_path / "baseline.txt"
    _write(
        baseline_path,
        "# header\n\nmodule:integrations/aws/sqs.py\n  \n# another comment\noperation-result:integrations/aws/shield.py\n",
    )
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)

    assert checker.load_baseline() == {
        "module:integrations/aws/sqs.py",
        "operation-result:integrations/aws/shield.py",
    }


def test_load_baseline_missing_file_returns_empty_set(tmp_path, monkeypatch):
    monkeypatch.setattr(checker, "BASELINE_PATH", tmp_path / "does-not-exist.txt")

    assert checker.load_baseline() == set()


def test_find_current_violations_ignores_non_python_files_and_cache_directories(tmp_path, monkeypatch):
    """The cached .py file would violate both rules if scanned, so an empty result proves it was skipped."""
    _use_tree(
        tmp_path,
        monkeypatch,
        {
            **COMPLIANT_VENDOR,
            "vendor/README.md": "OperationResult\n",
            "vendor/__pycache__/mirror.py": "from infrastructure.operations.result import OperationResult\n",
        },
    )

    assert checker.find_current_violations() == set()


def test_real_baseline_lists_no_google_workspace_or_non_vendor_entries():
    """Widening the baseline is the only way around the check, so the cleaned vendor and utils/ must stay out of it."""
    baseline = checker.load_baseline()

    assert checker.BASELINE_PATH.exists()
    assert sorted(entry for entry in baseline if "integrations/google_workspace/" in entry) == []
    assert sorted(entry for entry in baseline if "integrations/utils/" in entry) == []
