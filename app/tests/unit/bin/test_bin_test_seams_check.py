"""Behavior tests for the test-seam guard over the strict zone and the legacy pin zone.

Each test writes a throwaway app tree under ``tmp_path`` (a few modules under
features/, modules/ and integrations/, and the test files that patch them) and
points the checker's path constants at it, so no test depends on which tests
the real repository holds today. Classification is asserted through
``strict_entries`` and ``legacy_entries`` (the entries a tree produces), and the
ratchet through ``main``, whose printed block and exit code are the whole
interface the guard presents to CI. One test runs the guard over the real tree
to keep the seeded baselines honest.
"""

from pathlib import Path

import pytest

from bin import check_test_seams as checker

APP_MODULES = {
    "features/__init__.py": "",
    "features/rant/__init__.py": "",
    "features/rant/service.py": (
        "import structlog\n"
        "from datetime import datetime\n"
        "from features.rant.providers import get_client\n"
        "from features.rant.settings import get_rant_settings\n"
        "from integrations.slack import client as slack_client\n"
        "logger = structlog.get_logger()\n"
        "def compose():\n    return get_client()\n"
        "def _now():\n    return datetime.now()\n"
        "class Composer:\n    def run(self):\n        return None\n"
    ),
    "features/rant/providers.py": "def get_client():\n    return None\ndef _private():\n    return None\n",
    "features/rant/settings.py": "def get_rant_settings():\n    return None\n",
    "modules/__init__.py": "",
    "modules/legacy.py": "def handler():\n    return None\n",
    "integrations/__init__.py": "",
    "integrations/slack/__init__.py": "",
    "integrations/slack/client.py": "def post():\n    return None\n",
}
STRICT_TEST = "tests/unit/features/rant/test_rant_compose.py"
PIN_TEST = "tests/integration/legacy_surface/test_legacy_pin.py"
CONFTEST = "tests/integration/legacy_surface/conftest.py"


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _use_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str],
    strict_baseline: str = "# empty\n",
    legacy_baseline: str = "# empty\n",
) -> Path:
    """Write the app modules plus ``files`` under a fake app root and aim every checker constant at it."""
    app_root = tmp_path / "app"
    for relative_path, content in {**APP_MODULES, **files}.items():
        _write(app_root / relative_path, content)
    tests_root = app_root / "tests"
    monkeypatch.setattr(checker, "APP_ROOT", app_root)
    monkeypatch.setattr(checker, "TESTS_ROOT", tests_root)
    monkeypatch.setattr(checker, "STRICT_ZONES", (tests_root / "unit" / "features", tests_root / "integration" / "features"))
    monkeypatch.setattr(checker, "LEGACY_ZONE", tests_root / "integration" / "legacy_surface")
    monkeypatch.setattr(checker, "STRICT_BASELINE_PATH", _write(app_root / "bin/baselines/strict.txt", strict_baseline))
    monkeypatch.setattr(checker, "LEGACY_BASELINE_PATH", _write(app_root / "bin/baselines/legacy.txt", legacy_baseline))
    return app_root


def _strict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> set[str]:
    _use_tree(tmp_path, monkeypatch, {STRICT_TEST: body})
    return checker.strict_entries()


def _entry(target: str) -> str:
    return f"{STRICT_TEST}::{target}"


class TestStrictZoneAllowed:
    """AC #5: edges, provider seams and test-local objects are never violations."""

    def test_a_tree_without_patches_is_clean(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert _strict(tmp_path, monkeypatch, "def test_x():\n    assert True\n") == set()

    def test_a_provider_function_patched_in_its_consumer_is_a_seam(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (
            "from features.rant import service\n"
            "def test_x(monkeypatch):\n"
            "    monkeypatch.setattr(service, 'get_client', lambda: None)\n"
            "    monkeypatch.setattr(service, 'get_rant_settings', lambda: None)\n"
        )
        assert _strict(tmp_path, monkeypatch, body) == set()

    def test_a_private_provider_function_is_internal(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = "from unittest.mock import patch\n@patch('features.rant.providers._private')\ndef test_x(_):\n    pass\n"
        assert _strict(tmp_path, monkeypatch, body) == {_entry("features.rant.providers._private")}

    def test_integrations_and_stdlib_origins_are_edges(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (
            "from features.rant import service\n"
            "def test_x(monkeypatch):\n"
            "    monkeypatch.setattr(service.slack_client, 'post', lambda: None)\n"
            "    monkeypatch.setattr('features.rant.service.datetime', object())\n"
            "    monkeypatch.setattr('integrations.slack.client.post', lambda: None)\n"
        )
        assert _strict(tmp_path, monkeypatch, body) == set()

    def test_a_test_local_object_is_not_a_target(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (
            "class Fake:\n    value = 1\n"
            "def test_x(monkeypatch, fixture_object):\n"
            "    monkeypatch.setattr(Fake, 'value', 2)\n"
            "    monkeypatch.setattr(fixture_object, 'value', 2)\n"
        )
        assert _strict(tmp_path, monkeypatch, body) == set()


class TestStrictZoneResolution:
    """AC #5: targets resolve statically through constants, imports and the app tree."""

    def test_constant_and_fstring_targets_are_folded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (
            "_MODULE = 'features.rant.service'\n"
            "_COMPOSE = _MODULE + '.compose'\n"
            "def test_x(monkeypatch):\n"
            "    monkeypatch.setattr(f'{_MODULE}._now', lambda: None)\n"
            "    monkeypatch.setattr(_COMPOSE, lambda: None)\n"
        )
        assert _strict(tmp_path, monkeypatch, body) == {
            _entry("features.rant.service._now"),
            _entry("features.rant.service.compose"),
        }

    def test_patch_decorators_and_context_managers_are_detected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (
            "from unittest import mock\n"
            "from unittest.mock import patch\n"
            "@mock.patch('features.rant.service.compose')\n"
            "def test_x(_):\n"
            "    with patch('modules.legacy.handler'):\n"
            "        pass\n"
        )
        assert _strict(tmp_path, monkeypatch, body) == {_entry("features.rant.service.compose"), _entry("modules.legacy.handler")}

    def test_patch_object_on_an_imported_feature_class_is_internal(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (
            "from unittest.mock import patch\n"
            "from features.rant.service import Composer\n"
            "def test_x():\n"
            "    with patch.object(Composer, 'run'):\n"
            "        pass\n"
        )
        assert _strict(tmp_path, monkeypatch, body) == {_entry("features.rant.service.Composer.run")}

    def test_patch_multiple_names_each_attribute(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (
            "from unittest.mock import patch\n"
            "from features.rant import service\n"
            "def test_x():\n"
            "    with patch.multiple(service, compose=None, get_client=None, autospec=True):\n"
            "        pass\n"
        )
        assert _strict(tmp_path, monkeypatch, body) == {_entry("features.rant.service.compose")}

    def test_monkeypatch_context_and_delattr_are_detected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (
            "import modules.legacy as legacy\n"
            "def test_x(monkeypatch):\n"
            "    with monkeypatch.context() as context:\n"
            "        context.setattr(legacy, 'handler', None)\n"
            "    monkeypatch.delattr('features.rant.service._now')\n"
        )
        assert _strict(tmp_path, monkeypatch, body) == {_entry("modules.legacy.handler"), _entry("features.rant.service._now")}

    def test_repeated_patches_of_one_target_collapse_to_one_entry(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = "".join(
            f"def test_{index}(monkeypatch):\n    monkeypatch.setattr('features.rant.service.compose', None)\n"
            for index in range(3)
        )
        assert _strict(tmp_path, monkeypatch, body) == {_entry("features.rant.service.compose")}


class TestStrictZoneViolations:
    """AC #5: internal targets fail, module-level variables included, and nothing unresolved passes."""

    def test_a_module_level_logger_is_internal(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = "from features.rant import service\ndef test_x(monkeypatch):\n    monkeypatch.setattr(service.logger, 'warning', None)\n"
        assert _strict(tmp_path, monkeypatch, body) == {_entry("features.rant.service.logger.warning")}

    def test_an_unknown_name_in_a_guarded_root_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = "def test_x(monkeypatch):\n    monkeypatch.setattr('features.rant.service.missing', None)\n"
        assert _strict(tmp_path, monkeypatch, body) == {_entry("?features.rant.service.missing")}

    def test_a_dynamic_attribute_on_a_guarded_module_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = "from features.rant import service\ndef test_x(monkeypatch, name):\n    monkeypatch.setattr(service, name, None)\n"
        assert _strict(tmp_path, monkeypatch, body) == {_entry("?features.rant.service.<name>")}

    def test_a_dynamic_attribute_on_an_edge_is_an_edge(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (
            "from integrations.slack import client\ndef test_x(monkeypatch, name):\n    monkeypatch.setattr(client, name, None)\n"
        )
        assert _strict(tmp_path, monkeypatch, body) == set()


def _legacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, str]) -> set[str]:
    _use_tree(tmp_path, monkeypatch, files)
    return checker.legacy_entries()


OWNED_SEAM = (
    "import pytest\n"
    "from modules import legacy\n"
    "@pytest.fixture\n"
    "def legacy_handler_seam(monkeypatch):\n"
    '    """Internal legacy seam. Owning rebuild task: TASK-145.7, which deletes it."""\n'
    "    monkeypatch.setattr(legacy, 'handler', None)\n"
)


class TestLegacyPinZone:
    """AC #1: modules/ and features/ patches live only in owned conftest seam fixtures."""

    def test_an_owned_seam_fixture_is_keyed_with_its_owner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert _legacy(tmp_path, monkeypatch, {CONFTEST: OWNED_SEAM}) == {
            "legacy_handler_seam::modules.legacy.handler  # TASK-145.7"
        }

    def test_an_inline_patch_in_a_pin_test_is_a_violation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pin = "def test_x(monkeypatch):\n    monkeypatch.setattr('features.rant.service.compose', None)\n"
        assert _legacy(tmp_path, monkeypatch, {PIN_TEST: pin}) == {f"inline:{PIN_TEST}::features.rant.service.compose"}

    def test_an_edge_patch_in_a_pin_test_is_allowed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pin = "def test_x(monkeypatch):\n    monkeypatch.setattr('integrations.slack.client.post', None)\n"
        assert _legacy(tmp_path, monkeypatch, {PIN_TEST: pin}) == set()

    def test_a_conftest_helper_that_is_not_a_fixture_is_unowned(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        conftest = (
            "from modules import legacy\n"
            "def build(monkeypatch):\n"
            '    """Owning rebuild task: TASK-145.7."""\n'
            "    monkeypatch.setattr(legacy, 'handler', None)\n"
        )
        assert _legacy(tmp_path, monkeypatch, {CONFTEST: conftest}) == {f"unowned:{CONFTEST}::build::modules.legacy.handler"}

    def test_a_fixture_without_an_owner_is_unowned(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        conftest = OWNED_SEAM.replace("Owning rebuild task: TASK-145.7, which deletes it.", "No owner.")
        assert _legacy(tmp_path, monkeypatch, {CONFTEST: conftest}) == {
            f"unowned:{CONFTEST}::legacy_handler_seam::modules.legacy.handler"
        }


class TestRatchet:
    """AC #1, #2, #5: baselines grandfather known entries, net-new fails, stale is reported."""

    def test_baselined_entries_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        strict_test = "def test_x(monkeypatch):\n    monkeypatch.setattr('features.rant.service.compose', None)\n"
        _use_tree(
            tmp_path,
            monkeypatch,
            {STRICT_TEST: strict_test, CONFTEST: OWNED_SEAM},
            strict_baseline=f"{_entry('features.rant.service.compose')}  # TASK-124 free text\n",
            legacy_baseline="legacy_handler_seam::modules.legacy.handler  # TASK-145.7 rebuilds the caller\n",
        )
        assert checker.main([]) == 0
        assert capsys.readouterr().out.count("OK:") == 2

    def test_a_net_new_strict_patch_fails_and_names_the_baseline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        strict_test = "def test_x(monkeypatch):\n    monkeypatch.setattr('features.rant.service.compose', None)\n"
        _use_tree(tmp_path, monkeypatch, {STRICT_TEST: strict_test})
        assert checker.main([]) == 1
        out = capsys.readouterr().out
        assert _entry("features.rant.service.compose") in out
        assert "strict.txt" in out

    @pytest.mark.parametrize(
        "baseline",
        ["legacy_handler_seam::modules.legacy.handler\n", "legacy_handler_seam::modules.legacy.handler  # TASK-145.8\n"],
        ids=["no-owner", "other-owner"],
    )
    def test_a_seam_entry_must_carry_its_fixtures_owner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], baseline: str
    ) -> None:
        _use_tree(tmp_path, monkeypatch, {CONFTEST: OWNED_SEAM}, legacy_baseline=baseline)
        assert checker.main([]) == 1
        assert "legacy_handler_seam::modules.legacy.handler  # TASK-145.7" in capsys.readouterr().out

    def test_a_removed_patch_is_reported_stale_without_failing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _use_tree(tmp_path, monkeypatch, {}, strict_baseline=f"{_entry('features.rant.service.compose')}\n")
        assert checker.main([]) == 0
        out = capsys.readouterr().out
        assert "INFO:" in out
        assert _entry("features.rant.service.compose") in out

    def test_print_entries_lists_both_zones_and_writes_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        app_root = _use_tree(tmp_path, monkeypatch, {CONFTEST: OWNED_SEAM})
        before = (app_root / "bin/baselines/legacy.txt").read_text(encoding="utf-8")
        assert checker.main(["--print-entries"]) == 0
        out = capsys.readouterr().out
        assert "# strict (0)" in out
        assert "legacy_handler_seam::modules.legacy.handler  # TASK-145.7" in out
        assert (app_root / "bin/baselines/legacy.txt").read_text(encoding="utf-8") == before


def test_the_repository_tests_match_their_baselines(capsys: pytest.CaptureFixture[str]) -> None:
    """The real strict zone and legacy pins hold no patch the baselines do not name."""
    assert checker.main([]) == 0, capsys.readouterr().out
