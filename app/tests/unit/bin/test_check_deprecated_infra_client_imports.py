"""Tests for the deprecated infrastructure.clients import freeze-baseline checker."""

from bin import check_deprecated_infra_client_imports as checker


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_imports_deprecated_module_detects_plain_import(tmp_path):
    file_path = tmp_path / "consumer.py"
    _write(file_path, "import infrastructure.clients.aws.dynamodb\n")

    assert checker.imports_deprecated_module(file_path) is True


def test_imports_deprecated_module_detects_from_import(tmp_path):
    file_path = tmp_path / "consumer.py"
    _write(file_path, "from infrastructure.clients import aws\n")

    assert checker.imports_deprecated_module(file_path) is True


def test_imports_deprecated_module_ignores_unrelated_import(tmp_path):
    file_path = tmp_path / "consumer.py"
    _write(file_path, "import infrastructure.storage.service\n")

    assert checker.imports_deprecated_module(file_path) is False


def test_find_current_consumers_excludes_deprecated_tree_itself(tmp_path, monkeypatch):
    deprecated_tree = tmp_path / "infrastructure" / "clients"
    _write(
        deprecated_tree / "aws" / "facade.py",
        "from infrastructure.clients.aws.config import Config\n",
    )
    _write(
        tmp_path / "packages" / "geolocate" / "service.py",
        "from infrastructure.clients.maxmind import Client\n",
    )
    monkeypatch.setattr(checker, "APP_ROOT", tmp_path)
    monkeypatch.setattr(checker, "DEPRECATED_TREE", deprecated_tree)

    assert checker.find_current_consumers() == {"packages/geolocate/service.py"}


def test_load_baseline_ignores_blank_and_comment_lines(tmp_path, monkeypatch):
    baseline_path = tmp_path / "baseline.txt"
    _write(baseline_path, "# header\n\nfoo/bar.py\n  \n# another comment\nbaz/qux.py\n")
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)

    assert checker.load_baseline() == {"foo/bar.py", "baz/qux.py"}


def test_load_baseline_missing_file_returns_empty_set(tmp_path, monkeypatch):
    monkeypatch.setattr(checker, "BASELINE_PATH", tmp_path / "does-not-exist.txt")

    assert checker.load_baseline() == set()


def test_main_fails_on_net_new_violation(tmp_path, monkeypatch, capsys):
    deprecated_tree = tmp_path / "infrastructure" / "clients"
    deprecated_tree.mkdir(parents=True)
    _write(
        tmp_path / "packages" / "geolocate" / "service.py",
        "from infrastructure.clients.maxmind import Client\n",
    )
    baseline_path = tmp_path / "baseline.txt"
    _write(baseline_path, "# empty baseline\n")
    monkeypatch.setattr(checker, "APP_ROOT", tmp_path)
    monkeypatch.setattr(checker, "DEPRECATED_TREE", deprecated_tree)
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)

    exit_code = checker.main()

    assert exit_code == 1
    assert "packages/geolocate/service.py" in capsys.readouterr().out


def test_main_passes_when_baseline_has_stale_entries_only(tmp_path, monkeypatch, capsys):
    deprecated_tree = tmp_path / "infrastructure" / "clients"
    deprecated_tree.mkdir(parents=True)
    baseline_path = tmp_path / "baseline.txt"
    _write(baseline_path, "packages/already_migrated/service.py\n")
    monkeypatch.setattr(checker, "APP_ROOT", tmp_path)
    monkeypatch.setattr(checker, "DEPRECATED_TREE", deprecated_tree)
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)

    exit_code = checker.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "packages/already_migrated/service.py" in output
