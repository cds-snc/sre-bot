"""Behavior tests for the package-shape guard over app/features/ and app/capabilities/.

Each test writes a throwaway app tree under ``tmp_path`` and points the
checker's path constants at it, so no test depends on which packages the real
repository holds today. Rules are asserted through ``find_violations`` (one rule
per test, so a failure names the rule that broke) and the ratchet through
``main``, whose printed block and exit code are the whole interface the guard
presents to CI. One test runs the guard over the real tree to keep the seeded
baseline honest.
"""

from pathlib import Path

import pytest

from bin import check_package_shape as checker

PLUGIN_INIT = "from contracts.plugins.namespace import hookimpl\n\n\n@hookimpl\ndef register_requirements():\n    return []\n"
VALID_README = "# People\n\n## Classification\n\nsupporting\n\n## Feature consumers\n\n- features.incident\n"


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _pyproject(entry_points: dict[str, str]) -> str:
    lines = ["[project]", "name = 'fake'", "", "[project.entry-points.sre_bot]"]
    lines.extend(f'"{name}" = "{target}"' for name, target in entry_points.items())
    return "\n".join(lines) + "\n"


def _use_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str],
    entry_points: dict[str, str] | None = None,
    baseline: str = "# empty baseline\n",
) -> Path:
    """Write ``files`` under a fake app root and aim every checker constant at it."""
    app_root = tmp_path / "app"
    for relative_path, content in files.items():
        _write(app_root / relative_path, content)
    baseline_path = _write(app_root / "bin" / "baselines" / "package_shape.txt", baseline)
    pyproject_path = _write(app_root / "pyproject.toml", _pyproject(entry_points or {}))

    monkeypatch.setattr(checker, "APP_ROOT", app_root)
    monkeypatch.setattr(checker, "FEATURES_ROOT", app_root / "features")
    monkeypatch.setattr(checker, "CAPABILITIES_ROOT", app_root / "capabilities")
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(checker, "PYPROJECT_PATH", pyproject_path)
    return app_root


def _violations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str],
    entry_points: dict[str, str] | None = None,
) -> set[str]:
    _use_tree(tmp_path, monkeypatch, files, entry_points)
    return checker.find_violations()


def _feature(name: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    """A flat feature plugin in the full layout-table shape."""
    files = {
        f"features/{name}/__init__.py": PLUGIN_INIT,
        f"features/{name}/README.md": "# Feature\n",
        f"features/{name}/settings.py": "",
        f"features/{name}/service.py": "",
    }
    files.update(extra or {})
    return files


def _umbrella(subdomains: tuple[str, ...] = ("alpha", "beta")) -> dict[str, str]:
    """An umbrella named ``suite`` with plugin subdomains, a core/ and a common/."""
    files = {
        "features/suite/__init__.py": "",
        "features/suite/README.md": "# Suite\n",
        "features/suite/core/__init__.py": "",
        "features/suite/core/api.py": "",
        "features/suite/core/store.py": "",
        "features/suite/core/adapters/__init__.py": "",
        "features/suite/common/__init__.py": "",
        "features/suite/common/vocabulary.py": "",
    }
    for name in subdomains:
        files[f"features/suite/{name}/__init__.py"] = PLUGIN_INIT
        files[f"features/suite/{name}/service.py"] = ""
    return files


def _umbrella_entry_points(subdomains: tuple[str, ...] = ("alpha", "beta")) -> dict[str, str]:
    return {f"suite.{name}": f"features.suite.{name}" for name in subdomains}


class TestLayoutTable:
    """AC #1 and #2: only names from the amended layout table, at every package level."""

    def test_a_package_with_every_table_name_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _feature(
            "full",
            {
                "features/full/domain.py": "",
                "features/full/interfaces.py": "",
                "features/full/schemas.py": "",
                "features/full/store.py": "",
                "features/full/providers.py": "",
                "features/full/adapters/slack.py": "",
                "features/full/entrypoints/slack.py": "",
                "features/full/locales/en-US.yml": "",
            },
        )
        assert _violations(tmp_path, monkeypatch, files, {"full": "features.full"}) == set()

    def test_an_unknown_top_level_module_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _feature("rant", {"features/rant/helpers.py": ""})
        assert _violations(tmp_path, monkeypatch, files, {"rant": "features.rant"}) == {"features/rant/helpers.py"}

    def test_ports_is_not_a_table_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _feature("rant", {"features/rant/ports.py": ""})
        assert _violations(tmp_path, monkeypatch, files, {"rant": "features.rant"}) == {"features/rant/ports.py"}

    def test_a_legacy_platforms_directory_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _feature("rant", {"features/rant/platforms/slack.py": ""})
        assert _violations(tmp_path, monkeypatch, files, {"rant": "features.rant"}) == {"features/rant/platforms"}

    def test_service_and_domain_may_grow_into_packages(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _feature(
            "rant",
            {
                "features/rant/service/__init__.py": "",
                "features/rant/service/approval.py": "",
                "features/rant/domain/__init__.py": "",
                "features/rant/domain/form.py": "",
            },
        )
        assert _violations(tmp_path, monkeypatch, files, {"rant": "features.rant"}) == set()

    def test_pycache_is_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _feature("rant", {"features/rant/__pycache__/service.cpython-314.pyc": ""})
        assert _violations(tmp_path, monkeypatch, files, {"rant": "features.rant"}) == set()

    def test_api_and_hookspecs_fail_in_a_feature(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _feature("rant", {"features/rant/api.py": "", "features/rant/hookspecs.py": ""})
        assert _violations(tmp_path, monkeypatch, files, {"rant": "features.rant"}) == {
            "features/rant/api.py",
            "features/rant/hookspecs.py",
        }

    def test_api_and_hookspecs_pass_in_a_capability(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = {
            "capabilities/people/__init__.py": PLUGIN_INIT,
            "capabilities/people/README.md": VALID_README,
            "capabilities/people/api.py": "",
            "capabilities/people/hookspecs.py": "",
            "capabilities/people/service.py": "",
            "features/incident/__init__.py": PLUGIN_INIT,
        }
        entry_points = {"people": "capabilities.people", "incident": "features.incident"}
        assert _violations(tmp_path, monkeypatch, files, entry_points) == set()

    def test_a_settings_only_package_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = {"features/talent/__init__.py": "", "features/talent/settings.py": ""}
        assert _violations(tmp_path, monkeypatch, files) == set()


class TestPluginModule:
    """AC #2: plugin.py is allowed only where an entry point names it."""

    def test_plugin_named_by_an_entry_point_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = {
            "features/rant/__init__.py": '"""Rant."""\n',
            "features/rant/plugin.py": PLUGIN_INIT,
            "features/rant/settings.py": "",
        }
        assert _violations(tmp_path, monkeypatch, files, {"rant": "features.rant.plugin"}) == set()

    def test_plugin_no_entry_point_names_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _feature("rant", {"features/rant/plugin.py": ""})
        assert _violations(tmp_path, monkeypatch, files, {"rant": "features.rant"}) == {"features/rant/plugin.py:plugin-unnamed"}


class TestUmbrella:
    """AC #1: an umbrella holds no code; core/ is not a plugin; common/ does no I/O."""

    def test_a_well_formed_umbrella_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert _violations(tmp_path, monkeypatch, _umbrella(), _umbrella_entry_points()) == set()

    @pytest.mark.parametrize("content", ['"""The suite umbrella."""\n', "VALUE = 1\n"])
    def test_a_non_empty_umbrella_init_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str) -> None:
        files = _umbrella()
        files["features/suite/__init__.py"] = content
        assert _violations(tmp_path, monkeypatch, files, _umbrella_entry_points()) == {"features/suite/__init__.py:umbrella-init"}

    def test_a_module_at_the_umbrella_root_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _umbrella()
        files["features/suite/shared.py"] = ""
        violations = _violations(tmp_path, monkeypatch, files, _umbrella_entry_points())
        assert "features/suite/shared.py" in violations

    def test_an_unknown_name_in_a_subdomain_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _umbrella()
        files["features/suite/alpha/publisher.py"] = ""
        assert _violations(tmp_path, monkeypatch, files, _umbrella_entry_points()) == {"features/suite/alpha/publisher.py"}

    def test_a_nested_subdomain_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _umbrella()
        files["features/suite/alpha/deeper/__init__.py"] = ""
        assert _violations(tmp_path, monkeypatch, files, _umbrella_entry_points()) == {"features/suite/alpha/deeper"}

    def test_core_with_entrypoints_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _umbrella()
        files["features/suite/core/entrypoints/slack.py"] = ""
        assert _violations(tmp_path, monkeypatch, files, _umbrella_entry_points()) == {"features/suite/core:core-entrypoints"}

    def test_core_with_a_hookimpl_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _umbrella()
        files["features/suite/core/store.py"] = PLUGIN_INIT
        assert _violations(tmp_path, monkeypatch, files, _umbrella_entry_points()) == {"features/suite/core:core-hookimpl"}

    def test_core_named_by_an_entry_point_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        entry_points = {**_umbrella_entry_points(), "suite.core": "features.suite.core"}
        assert _violations(tmp_path, monkeypatch, _umbrella(), entry_points) == {"features/suite/core:core-entry-point"}

    @pytest.mark.parametrize("name", ["adapters/__init__.py", "store.py", "providers.py"])
    def test_common_doing_io_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        files = _umbrella()
        files[f"features/suite/common/{name}"] = ""
        expected = f"features/suite/common/{name.split('/')[0]}"
        assert _violations(tmp_path, monkeypatch, files, _umbrella_entry_points()) == {expected}

    def test_a_subdomain_without_an_entry_point_or_hookimpls_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        files = _umbrella()
        files["features/suite/meet/__init__.py"] = ""
        files["features/suite/meet/adapters/__init__.py"] = ""
        assert _violations(tmp_path, monkeypatch, files, _umbrella_entry_points()) == set()


class TestEntryPoints:
    """AC #3: hookimpls imply an entry point; subdomain entry points carry the dotted name."""

    def test_hookimpls_without_an_entry_point_fail(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert _violations(tmp_path, monkeypatch, _feature("rant")) == {"features/rant:no-entry-point"}

    def test_a_bare_subdomain_entry_point_name_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        entry_points = {"alpha": "features.suite.alpha", "suite.beta": "features.suite.beta"}
        assert _violations(tmp_path, monkeypatch, _umbrella(), entry_points) == {"alpha:entry-point-name"}

    def test_a_flat_feature_entry_point_with_another_name_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert _violations(tmp_path, monkeypatch, _feature("rant"), {"ranting": "features.rant"}) == {"ranting:entry-point-name"}

    def test_entry_points_outside_features_and_capabilities_are_not_checked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entry_points = {"rant": "features.rant", "geolocate": "packages.geolocate"}
        assert _violations(tmp_path, monkeypatch, _feature("rant"), entry_points) == set()


class TestCapabilityReadme:
    """AC #4: a capability states its classification and names a feature consumer."""

    def _capability(self, readme: str | None) -> dict[str, str]:
        files = {
            "capabilities/people/__init__.py": PLUGIN_INIT,
            "capabilities/people/api.py": "",
            "features/incident/__init__.py": PLUGIN_INIT,
        }
        if readme is not None:
            files["capabilities/people/README.md"] = readme
        return files

    def _run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, readme: str | None) -> set[str]:
        entry_points = {"people": "capabilities.people", "incident": "features.incident"}
        return _violations(tmp_path, monkeypatch, self._capability(readme), entry_points)

    def test_a_valid_readme_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(tmp_path, monkeypatch, VALID_README) == set()

    def test_a_missing_readme_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(tmp_path, monkeypatch, None) == {"capabilities/people:readme-missing"}

    @pytest.mark.parametrize(
        "readme",
        [
            "# People\n\n## Feature consumers\n\n- features.incident\n",
            "# People\n\n## Classification\n\ncore\n\n## Feature consumers\n\n- features.incident\n",
        ],
    )
    def test_a_missing_or_invalid_classification_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, readme: str
    ) -> None:
        assert self._run(tmp_path, monkeypatch, readme) == {"capabilities/people:readme-classification"}

    @pytest.mark.parametrize(
        "consumers",
        ["", "\n## Feature consumers\n\nNone yet.\n", "\n## Feature consumers\n\n- features.billing\n"],
    )
    def test_no_resolvable_consumer_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumers: str) -> None:
        readme = "# People\n\n## Classification\n\ngeneric\n" + consumers
        assert self._run(tmp_path, monkeypatch, readme) == {"capabilities/people:readme-consumers"}

    def test_features_need_no_classification(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _feature("rant", {"features/rant/README.md": "# Rant\n"})
        assert _violations(tmp_path, monkeypatch, files, {"rant": "features.rant"}) == set()


class TestRatchet:
    """AC #5: the baseline grandfathers known violations and only ratchets down."""

    def test_a_baselined_violation_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        files = _feature("rant", {"features/rant/ports.py": ""})
        _use_tree(tmp_path, monkeypatch, files, {"rant": "features.rant"}, baseline="features/rant/ports.py\n")
        assert checker.main() == 0
        assert "OK:" in capsys.readouterr().out

    def test_a_new_violation_fails_and_names_the_baseline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        files = _feature("rant", {"features/rant/ports.py": ""})
        _use_tree(tmp_path, monkeypatch, files, {"rant": "features.rant"})
        assert checker.main() == 1
        out = capsys.readouterr().out
        assert "features/rant/ports.py" in out
        assert "package_shape.txt" in out

    def test_a_fixed_violation_is_reported_stale_without_failing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _use_tree(tmp_path, monkeypatch, _feature("rant"), {"rant": "features.rant"}, baseline="features/rant/ports.py\n")
        assert checker.main() == 0
        assert "features/rant/ports.py" in capsys.readouterr().out

    def test_a_missing_capabilities_root_is_not_an_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert _violations(tmp_path, monkeypatch, _feature("rant"), {"rant": "features.rant"}) == set()


def test_the_repository_tree_matches_its_baseline(capsys: pytest.CaptureFixture[str]) -> None:
    """The real features/ and capabilities/ trees hold no violation the baseline does not name."""
    assert checker.main() == 0, capsys.readouterr().out
