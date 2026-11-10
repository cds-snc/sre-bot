"""Behavior tests for the package generator over a throwaway app tree.

Each test copies the real pyproject.toml and config/base.toml into ``tmp_path``
and runs the generator there, so the real files are never written and the edits
start from today's contracts and enablement tables. A generated package is
judged by the same tools CI uses: the package-shape guard (its path constants
aimed at the copy, empty baseline), the plugin-enablement check, the rule that
the protected-plugins contract lists exactly the entry-point modules, ruff over
the generated files, and a pluggy PluginManager that registers the generated
``__init__.py`` (loaded from its file, so it cannot collide with the real
``features`` package) and calls ``register_requirements``. The optional
entries a kind may gain come from bin/package_layout.toml, so the option
matrix is checked against the shape guard for every capability combination.
"""

import importlib.util
import itertools
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pluggy
import pytest

from bin import check_package_shape as checker
from bin import new_package
from bin.new_package import GeneratorError
from bin.package_layout import layout
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from server.plugins.settings import PluginsSettings, check_plugin_enablement

APP_ROOT = Path(__file__).resolve().parents[3]
AREA = "workplace_utilities"


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake app root holding copies of the real configuration files and an empty features/ tree."""
    app_root = tmp_path / "app"
    (app_root / "config").mkdir(parents=True)
    (app_root / "features").mkdir()
    (app_root / "features" / "__init__.py").touch()
    shutil.copy(APP_ROOT / "pyproject.toml", app_root / "pyproject.toml")
    shutil.copy(APP_ROOT / "config" / "base.toml", app_root / "config" / "base.toml")
    baseline = app_root / "bin" / "baselines" / "package_shape.txt"
    baseline.parent.mkdir(parents=True)
    baseline.write_text("# empty baseline\n", encoding="utf-8")

    monkeypatch.setattr(checker, "APP_ROOT", app_root)
    monkeypatch.setattr(checker, "FEATURES_ROOT", app_root / "features")
    monkeypatch.setattr(checker, "CAPABILITIES_ROOT", app_root / "capabilities")
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline)
    monkeypatch.setattr(checker, "PYPROJECT_PATH", app_root / "pyproject.toml")
    return app_root


def _run(root: Path, *argv: str) -> None:
    assert new_package.main([*argv, "--root", str(root)]) == 0


def _pyproject(root: Path) -> dict[str, Any]:
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))


def _base(root: Path) -> dict[str, Any]:
    return tomllib.loads((root / "config" / "base.toml").read_text(encoding="utf-8"))


def _contract(root: Path, contract_id: str) -> dict[str, Any]:
    return next(c for c in _pyproject(root)["tool"]["importlinter"]["contracts"] if c.get("id") == contract_id)


def _entry_points(root: Path) -> dict[str, str]:
    group: dict[str, str] = _pyproject(root)["project"]["entry-points"][PLUGIN_NAMESPACE]
    return group


def _assert_consistent(root: Path) -> None:
    """The guards CI runs over a real tree all pass over the generated one."""
    assert checker.find_violations() == set()
    assert set(_contract(root, "protected-plugins")["protected_modules"]) == set(_entry_points(root).values())
    check_plugin_enablement(PluginsSettings.model_construct(**_base(root)["plugins"]), _entry_points(root))
    ruff = subprocess.run(  # noqa: S603 - fixed argv over a test-owned directory
        [sys.executable, "-m", "ruff", "check", "--no-cache", str(root / "features"), *_capabilities(root)],
        capture_output=True,
        text=True,
        check=False,
        cwd=root,
    )
    assert ruff.returncode == 0, ruff.stdout


def _capabilities(root: Path) -> list[str]:
    path = root / "capabilities"
    return [str(path)] if path.is_dir() else []


def _registered_requirements(package: Path) -> list[Any]:
    """Register the generated plugin module on a fresh manager and collect register_requirements."""
    spec = importlib.util.spec_from_file_location(
        f"generated_{package.name}", package / "__init__.py", submodule_search_locations=[str(package)]
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    manager.add_hookspecs(FeatureLifecycleSpecs)
    manager.register(module)
    results: list[Any] = manager.hook.register_requirements()
    return results


def test_a_feature_is_a_registrable_plugin_with_its_key_and_contracts(root: Path) -> None:
    _run(root, "feature", "shop", "--area", AREA)

    package = root / "features" / "shop"
    assert {path.name for path in package.iterdir()} == {"__init__.py", "README.md", "service.py", "entrypoints"}
    assert _entry_points(root)["shop"] == "features.shop"
    assert "features.shop" in _contract(root, "feature-independence")["modules"]
    assert _base(root)["plugins"][AREA]["shop"] is True
    assert _registered_requirements(package) == [[]]
    _assert_consistent(root)


def test_a_feature_with_settings_gets_a_slice_and_its_table(root: Path) -> None:
    _run(root, "feature", "shop", "--area", AREA, "--settings")

    settings = (root / "features" / "shop" / "settings.py").read_text(encoding="utf-8")
    assert 'toml_table_header=("shop",)' in settings
    assert 'env_prefix="SHOP__"' in settings
    assert _base(root)["shop"] == {}
    _assert_consistent(root)


def test_the_first_capability_creates_the_capabilities_root(root: Path) -> None:
    _run(root, "feature", "shop", "--area", AREA)
    _run(
        root,
        "capability",
        "pricing",
        "--area",
        AREA,
        "--classification",
        "supporting",
        "--consumer",
        "features.shop",
        "--hookspecs",
    )

    package = root / "capabilities" / "pricing"
    assert (root / "capabilities" / "__init__.py").is_file()
    assert {"api.py", "hookspecs.py", "README.md"} <= {path.name for path in package.iterdir()}
    readme = (package / "README.md").read_text(encoding="utf-8")
    assert "## Classification\n\nsupporting\n" in readme
    assert "## Feature consumers\n\n- features.shop\n" in readme
    assert "capabilities" in _pyproject(root)["tool"]["importlinter"]["root_packages"]
    assert "capabilities" in _pyproject(root)["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert _entry_points(root)["pricing"] == "capabilities.pricing"
    assert _registered_requirements(package) == [[]]
    _assert_consistent(root)


def test_a_later_capability_leaves_the_capabilities_bootstrap_alone(root: Path) -> None:
    _run(root, "feature", "shop", "--area", AREA)
    _run(root, "capability", "pricing", "--area", AREA, "--classification", "generic", "--consumer", "features.shop")
    before = _pyproject(root)

    _run(root, "capability", "tax", "--area", AREA, "--classification", "generic", "--consumer", "features.shop")

    after = _pyproject(root)
    assert after["tool"]["importlinter"]["root_packages"] == before["tool"]["importlinter"]["root_packages"]
    assert after["tool"]["hatch"] == before["tool"]["hatch"]
    _assert_consistent(root)


def test_an_umbrella_with_a_subdomain_core_and_common_matches_the_umbrella_rules(root: Path) -> None:
    _run(root, "umbrella", "shop", "--area", AREA)
    _run(root, "subdomain", "shop.cart", "--area", AREA)
    _run(root, "core", "shop")
    _run(root, "common", "shop", "--settings")

    umbrella = root / "features" / "shop"
    assert (umbrella / "__init__.py").read_text(encoding="utf-8") == ""
    assert not (umbrella / "core" / "entrypoints").exists()
    assert (umbrella / "core" / "api.py").is_file()
    assert (umbrella / "core" / "README.md").is_file()
    assert (umbrella / "common" / "README.md").is_file()
    assert _entry_points(root)["shop.cart"] == "features.shop.cart"
    assert "shop" not in _entry_points(root)
    assert "features.shop" in _contract(root, "feature-independence")["modules"]
    assert _contract(root, "shop-umbrella")["layers"] == ["cart", "core", "common"]
    assert _base(root)["plugins"][AREA]["shop.cart"] is True
    assert 'toml_table_header=("shop",)' in (umbrella / "common" / "settings.py").read_text(encoding="utf-8")
    assert _registered_requirements(umbrella / "cart") == [[]]
    _assert_consistent(root)


def test_a_capability_takes_its_consumers_area_without_an_area_flag(root: Path) -> None:
    _run(root, "feature", "shop", "--area", AREA)

    _run(root, "capability", "pricing", "--classification", "generic", "--consumer", "features.shop")

    assert _base(root)["plugins"][AREA]["pricing"] is True
    _assert_consistent(root)


def test_a_capability_whose_consumers_span_areas_needs_the_shared_table(root: Path) -> None:
    _run(root, "feature", "shop", "--area", AREA)
    _run(root, "feature", "orders", "--area", "incident_response")

    with pytest.raises(GeneratorError, match=r"\[plugins.shared\]"):
        new_package.generate(
            new_package.parse_request(
                [
                    "capability",
                    "pricing",
                    "--classification",
                    "generic",
                    "--consumer",
                    "features.shop",
                    "--consumer",
                    "features.orders",
                    "--root",
                    str(root),
                ]
            )
        )
    assert not (root / "capabilities").exists()


def test_a_capability_area_that_contradicts_its_consumers_is_refused(root: Path) -> None:
    _run(root, "feature", "shop", "--area", AREA)

    with pytest.raises(GeneratorError, match=f"plugins.{AREA}"):
        new_package.generate(
            new_package.parse_request(
                [
                    "capability",
                    "pricing",
                    "--area",
                    "incident_response",
                    "--classification",
                    "generic",
                    "--consumer",
                    "features.shop",
                    "--root",
                    str(root),
                ]
            )
        )


def test_the_printed_next_steps_name_the_product_scope_row(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scope = root.parent / "decisions" / "product-scope.md"
    scope.parent.mkdir()
    scope.write_text("| Area | Packages |\n| --- | --- |\n| Workplace utilities | `talent`, `rant` |\n", encoding="utf-8")

    _run(root, "feature", "shop", "--area", AREA)

    assert "| Workplace utilities | `talent`, `rant`, `shop` |" in capsys.readouterr().out


CAPABILITY_OPTIONS = ("hookspecs", "service", "entrypoints", "interfaces", "adapters", "settings")
ENTRY = {
    "hookspecs": "hookspecs.py",
    "service": "service.py",
    "entrypoints": "entrypoints",
    "interfaces": "interfaces.py",
    "adapters": "adapters",
    "settings": "settings.py",
}
CAPABILITY_COMBINATIONS = [
    combination
    for size in range(len(CAPABILITY_OPTIONS) + 1)
    for combination in itertools.combinations(CAPABILITY_OPTIONS, size)
    if "interfaces" not in combination or "service" in combination
]


def _names(directory: Path) -> set[str]:
    return {path.name for path in directory.iterdir() if path.name != "__pycache__"}


@pytest.mark.parametrize("options", CAPABILITY_COMBINATIONS, ids=lambda options: "+".join(options) or "none")
def test_a_capability_holds_its_required_entries_plus_exactly_the_options_given(root: Path, options: tuple[str, ...]) -> None:
    _run(root, "feature", "shop", "--area", AREA)

    _run(
        root, "capability", "pricing", "--classification", "generic", "--consumer", "features.shop", *(f"--{o}" for o in options)
    )

    package = root / "capabilities" / "pricing"
    assert _names(package) == {"__init__.py", "README.md", "api.py"} | {ENTRY[option] for option in options}
    for directory in ("entrypoints", "adapters"):
        if directory in _names(package):
            assert (package / directory / "__init__.py").is_file()
    assert checker.find_violations() == set()
    if len(options) == len(CAPABILITY_OPTIONS):
        _assert_consistent(root)


@pytest.mark.parametrize(
    ("kind", "target", "options", "expected"),
    [
        ("feature", "shop", (), {"__init__.py", "README.md", "service.py", "entrypoints"}),
        (
            "feature",
            "shop",
            ("interfaces", "adapters", "settings"),
            {"__init__.py", "README.md", "service.py", "entrypoints", "interfaces.py", "adapters", "settings.py"},
        ),
        ("subdomain", "mall.cart", (), {"__init__.py", "README.md", "service.py", "entrypoints"}),
        (
            "subdomain",
            "mall.cart",
            ("interfaces", "adapters", "settings"),
            {"__init__.py", "README.md", "service.py", "entrypoints", "interfaces.py", "adapters", "settings.py"},
        ),
        ("core", "mall", (), {"__init__.py", "README.md", "api.py", "service.py"}),
        (
            "core",
            "mall",
            ("interfaces", "adapters"),
            {"__init__.py", "README.md", "api.py", "service.py", "interfaces.py", "adapters"},
        ),
        ("common", "mall", (), {"__init__.py", "README.md"}),
        ("common", "mall", ("settings",), {"__init__.py", "README.md", "settings.py"}),
    ],
)
def test_a_kind_holds_its_required_entries_plus_exactly_the_options_given(
    root: Path, kind: str, target: str, options: tuple[str, ...], expected: set[str]
) -> None:
    _run(root, "umbrella", "mall", "--area", AREA)
    area = ["--area", AREA] if kind in ("feature", "subdomain") else []

    _run(root, kind, target, *area, *(f"--{option}" for option in options))

    directory = (
        root / "features" / target.replace(".", "/") if kind != "core" and kind != "common" else root / "features" / target / kind
    )
    assert _names(directory) == expected
    _assert_consistent(root)


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["feature", "Shop", "--area", AREA], "lower snake_case"),
        (["feature", "shop", "--area", "marketing"], "incident_response"),
        (["feature", "rant", "--area", AREA], "rant"),
        (["subdomain", "shop.cart", "--area", AREA], "umbrella"),
        (["subdomain", "shop", "--area", AREA], "<umbrella>.<subdomain>"),
        (["capability", "pricing", "--area", AREA, "--classification", "core", "--consumer", "features.shop"], "classification"),
        (
            ["capability", "pricing", "--area", AREA, "--classification", "generic", "--consumer", "features.none"],
            "features.none",
        ),
        (["feature", "shop"], "--area"),
        (["feature", "shop", "--area", AREA, "--hookspecs"], "--hookspecs is not an option of a feature"),
        (["feature", "shop", "--area", AREA, "--service"], "--service is not an option of a feature"),
        (["umbrella", "shop", "--area", AREA, "--settings"], "an umbrella takes no option"),
        (
            [
                "capability",
                "pricing",
                "--area",
                AREA,
                "--classification",
                "generic",
                "--consumer",
                "features.shop",
                "--interfaces",
            ],
            "--interfaces needs --service on a capability",
        ),
        (["promote", "shop", "--subdomain", "cart", "--settings"], "promote takes no option"),
    ],
)
def test_an_invalid_request_writes_nothing(root: Path, argv: list[str], message: str) -> None:
    pyproject_before = (root / "pyproject.toml").read_text(encoding="utf-8")
    base_before = (root / "config" / "base.toml").read_text(encoding="utf-8")

    with pytest.raises(GeneratorError, match=message):
        new_package.generate(new_package.parse_request([*argv, "--root", str(root)]))

    assert (root / "pyproject.toml").read_text(encoding="utf-8") == pyproject_before
    assert (root / "config" / "base.toml").read_text(encoding="utf-8") == base_before
    assert sorted(path.name for path in (root / "features").iterdir()) == ["__init__.py"]
    assert not (root / "capabilities").exists()


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["subdomain", "mall.cart", "--area", AREA, "--entrypoints"], "--entrypoints is not an option of a subdomain"),
        (["core", "mall", "--entrypoints"], "--entrypoints is not an option of a core"),
        (["core", "mall", "--hookspecs"], "--hookspecs is not an option of a core"),
        (["common", "mall", "--interfaces"], "--interfaces is not an option of a common"),
    ],
)
def test_an_option_outside_an_umbrella_members_kind_writes_nothing(root: Path, argv: list[str], message: str) -> None:
    _run(root, "umbrella", "mall", "--area", AREA)
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts}

    with pytest.raises(GeneratorError, match=f"{message}.*feature-packages.md"):
        new_package.generate(new_package.parse_request([*argv, "--root", str(root)]))

    after = {path: path.read_bytes() for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts}
    assert after == before


def test_an_existing_package_path_is_refused(root: Path) -> None:
    _run(root, "feature", "shop", "--area", AREA)

    with pytest.raises(GeneratorError, match="already exists"):
        new_package.generate(new_package.parse_request(["feature", "shop", "--area", AREA, "--root", str(root)]))


def test_main_reports_a_refused_request_and_exits_non_zero(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert new_package.main(["feature", "Shop", "--area", AREA, "--root", str(root)]) == 1

    assert "lower snake_case" in capsys.readouterr().err


def test_the_interactive_prompt_asks_for_the_same_values_the_flags_take(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(
        ["capability", "pricing", AREA, "generic", "features.shop, features.incident.response", "n", "y", "n", "y", "", "y"]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    assert new_package.prompt_arguments() == [
        "capability",
        "pricing",
        "--area",
        AREA,
        "--classification",
        "generic",
        "--consumer",
        "features.shop",
        "--consumer",
        "features.incident.response",
        "--service",
        "--interfaces",
        "--settings",
    ]


@pytest.mark.parametrize(
    ("answers", "entries"),
    [
        (
            ["capability", "pricing", AREA, "generic", "features.shop"],
            ["hookspecs", "service", "entrypoints", "interfaces", "adapters", "settings"],
        ),
        (["core", "shop"], ["interfaces", "adapters", "settings"]),
        (["common", "shop"], ["settings"]),
        (["umbrella", "shop", AREA], []),
        (["promote", "shop", "cart"], []),
    ],
)
def test_the_interactive_prompt_asks_each_option_the_kind_takes(
    monkeypatch: pytest.MonkeyPatch, answers: list[str], entries: list[str]
) -> None:
    prompts: list[str] = []
    replies = iter(answers)

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        return next(replies, "n")

    monkeypatch.setattr("builtins.input", answer)

    new_package.prompt_arguments()

    assert [prompt for prompt in prompts if prompt.startswith("Include ")] == [
        f"Include {layout().options[name].entry}? (y/N): " for name in entries
    ]


def _flat_feature_with_importers(root: Path) -> None:
    """A flat plugin feature with settings, imported by host code and a test, and switched off in ci.toml."""
    _run(root, "feature", "shop", "--area", AREA, "--settings", "--interfaces")
    (root / "features" / "shop" / "domain.py").write_text('"""Shop domain."""\n\nCURRENCY = "CAD"\n', encoding="utf-8")
    host = root / "server" / "host.py"
    host.parent.mkdir()
    host.write_text(
        '"""Host wiring."""\n\nfrom features.shop.domain import CURRENCY\nfrom features.shop.settings import get_shop_settings\n\n'
        'OWNER = "features.shop"\nOTHER = "features.shopping"\n__all__ = ["CURRENCY", "get_shop_settings"]\n',
        encoding="utf-8",
    )
    (root / "config" / "ci.toml").write_text(f"[plugins.{AREA}]\n# off in ci\nshop = false\n", encoding="utf-8")


def test_promote_turns_a_flat_feature_into_an_umbrella_with_it_as_the_first_subdomain(root: Path) -> None:
    _flat_feature_with_importers(root)

    _run(root, "promote", "shop", "--subdomain", "cart")

    umbrella = root / "features" / "shop"
    assert (umbrella / "__init__.py").read_text(encoding="utf-8") == ""
    assert {path.name for path in umbrella.iterdir()} == {"__init__.py", "README.md", "cart", "common"}
    assert {"__init__.py", "README.md", "service.py", "interfaces.py", "domain.py", "entrypoints"} <= {
        path.name for path in (umbrella / "cart").iterdir()
    }
    assert 'toml_table_header=("shop",)' in (umbrella / "common" / "settings.py").read_text(encoding="utf-8")
    assert "shop" not in _entry_points(root)
    assert _entry_points(root)["shop.cart"] == "features.shop.cart"
    assert "features.shop" in _contract(root, "feature-independence")["modules"]
    assert _contract(root, "shop-umbrella")["layers"] == ["cart", "common"]
    assert "shop" not in _base(root)["plugins"][AREA]
    assert _base(root)["plugins"][AREA]["shop.cart"] is True
    assert _base(root)["shop"] == {}
    ci = (root / "config" / "ci.toml").read_text(encoding="utf-8")
    assert tomllib.loads(ci)["plugins"][AREA] == {"shop.cart": False}
    assert "# off in ci" in ci
    host = (root / "server" / "host.py").read_text(encoding="utf-8")
    assert "from features.shop.cart.domain import CURRENCY" in host
    assert "from features.shop.common.settings import get_shop_settings" in host
    assert 'OWNER = "features.shop.cart"' in host
    assert 'OTHER = "features.shopping"' in host
    assert "features.shop.cart" in (umbrella / "cart" / "README.md").read_text(encoding="utf-8")
    assert (umbrella / "common" / "README.md").is_file()
    assert _registered_requirements(umbrella / "cart") == [[]]
    _assert_consistent(root)


def test_promote_without_settings_adds_no_common(root: Path) -> None:
    _run(root, "feature", "shop", "--area", AREA)

    _run(root, "promote", "shop", "--subdomain", "cart")

    assert not (root / "features" / "shop" / "common").exists()
    assert _contract(root, "shop-umbrella")["layers"] == ["cart"]
    _assert_consistent(root)


@pytest.mark.parametrize(
    ("setup", "argv", "message"),
    [
        ([], ["promote", "shop", "--subdomain", "cart"], "no feature"),
        ([["umbrella", "shop", "--area", AREA]], ["promote", "shop", "--subdomain", "cart"], "entry point"),
        ([["feature", "shop", "--area", AREA]], ["promote", "shop"], "--subdomain"),
        ([["feature", "shop", "--area", AREA]], ["promote", "shop", "--subdomain", "core"], "reserved"),
    ],
)
def test_a_refused_promotion_changes_nothing(root: Path, setup: list[list[str]], argv: list[str], message: str) -> None:
    for step in setup:
        _run(root, *step)
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts}

    with pytest.raises(GeneratorError, match=message):
        new_package.generate(new_package.parse_request([*argv, "--root", str(root)]))

    after = {path: path.read_bytes() for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts}
    assert after == before
