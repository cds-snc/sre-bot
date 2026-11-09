"""Behavior tests for the package-layout manifest and its loader.

The real manifest (app/bin/package_layout.toml) is loaded and its kinds are
asserted against the rules of decisions/feature-packages.md. Malformed
manifests are written under ``tmp_path`` and must be refused with a message
naming the offending key, so a bad edit fails loudly instead of silently
widening the shape check. A drift test compares the names in the record's
layout table with the manifest's, so the two can only change together.
"""

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from bin.package_layout import LAYOUT_PATH, Layout, LayoutError, load_layout

DECISION = Path(__file__).resolve().parents[4] / "decisions" / "feature-packages.md"

MINIMAL = """
roots = { features = "features", capabilities = "capabilities" }
reserved_subdomains = ["core"]
grows_into_package = ["service.py"]

[capability_readme]
classification_heading = "## Classification"
consumers_heading = "## Feature consumers"
classifications = ["generic"]

[kinds.feature]
required = ["__init__.py", "service.py"]
optional = ["adapters/"]
"""


def _load(tmp_path: Path, text: str) -> Layout:
    path = tmp_path / "layout.toml"
    path.write_text(text, encoding="utf-8")
    return load_layout(path)


def _table_names() -> set[str]:
    """Names in the layout code block of feature-packages.md, a directory keeping its trailing '/'."""
    text = DECISION.read_text(encoding="utf-8")
    block = text.split("```text\napp/features/<feature>/\n", 1)[1].split("```", 1)[0]
    return {match.group(1) for line in block.splitlines() if (match := re.search(r"── (\S+)", line))}


class TestRealManifest:
    """The checked-in manifest encodes the layout table's rules per kind."""

    def test_every_kind_requires_an_init(self) -> None:
        layout = load_layout(LAYOUT_PATH)

        assert {name for name, kind in layout.kinds.items() if "__init__.py" not in kind.required} == set()

    def test_a_capability_allows_api_and_hookspecs_and_a_feature_does_not(self) -> None:
        kinds = load_layout(LAYOUT_PATH).kinds

        assert {"api.py", "hookspecs.py"} <= kinds["capability"].allowed_files
        assert {"api.py", "hookspecs.py"} & kinds["feature"].allowed_files == set()
        assert kinds["subdomain"].allowed_files == kinds["feature"].allowed_files

    def test_core_has_api_and_no_plugin_module_or_entrypoints(self) -> None:
        core = load_layout(LAYOUT_PATH).kinds["core"]

        assert "api.py" in core.allowed_files
        assert "plugin.py" not in core.allowed_files
        assert "entrypoints" not in core.allowed_dirs

    def test_service_and_domain_may_be_modules_or_packages(self) -> None:
        feature = load_layout(LAYOUT_PATH).kinds["feature"]

        assert {"service.py", "domain.py"} <= feature.allowed_files
        assert {"service", "domain"} <= feature.allowed_dirs

    def test_common_is_open_except_for_io_names(self) -> None:
        common = load_layout(LAYOUT_PATH).kinds["common"]

        assert common.open
        assert common.forbidden_names == {"adapters", "store.py", "providers.py"}

    def test_an_umbrella_root_allows_only_its_init_and_readme(self) -> None:
        umbrella = load_layout(LAYOUT_PATH).kinds["umbrella"]

        assert umbrella.allowed_files == {"__init__.py", "README.md"}
        assert umbrella.allowed_dirs == frozenset()

    def test_the_layout_table_and_the_manifest_name_the_same_entries(self) -> None:
        declared = load_layout(LAYOUT_PATH).declared_names

        assert _table_names() == declared, (
            "decisions/feature-packages.md's layout table and app/bin/package_layout.toml differ; "
            "amend the record and the manifest together"
        )


class TestMalformedManifest:
    """A malformed manifest is refused, naming the key at fault."""

    def test_a_minimal_manifest_loads(self, tmp_path: Path) -> None:
        layout = _load(tmp_path, MINIMAL)

        assert layout.kinds["feature"].allowed_dirs == {"adapters", "service"}
        assert layout.classifications == ("generic",)

    @pytest.mark.parametrize(
        ("edit", "message"),
        [
            (lambda text: 'unknown = "x"\n' + text, "unknown"),
            (lambda text: text + '\n[kinds.extra]\nrequired = ["__init__.py"]\nsurplus = true\n', "surplus"),
            (lambda text: text.replace('optional = ["adapters/"]', 'optional = ["service.py"]'), "service.py"),
            (lambda text: text.replace('optional = ["adapters/"]', 'optional = ["adapters/x.py"]'), "adapters/x.py"),
            (lambda text: text + '\n[kinds.core]\nextends = "nowhere"\n', "nowhere"),
            (lambda text: text.replace('classifications = ["generic"]', "classifications = []"), "classifications"),
            (lambda text: text.replace('roots = { features = "features", capabilities = "capabilities" }', ""), "roots"),
            (lambda text: text + '\n[kinds.core]\nextends = "feature"\nexclude = ["api.py"]\n', "api.py"),
        ],
        ids=[
            "unknown-top-level-key",
            "unknown-kind-key",
            "required-and-optional",
            "nested-path",
            "unknown-base-kind",
            "empty-classifications",
            "missing-roots",
            "exclude-of-an-absent-name",
        ],
    )
    def test_a_malformed_manifest_is_refused(self, tmp_path: Path, edit: Callable[[str], str], message: str) -> None:
        with pytest.raises(LayoutError, match=re.escape(message)):
            _load(tmp_path, edit(MINIMAL))
